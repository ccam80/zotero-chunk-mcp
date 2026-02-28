"""Comprehensive cache TTL analysis across all BP configurations.

Each breakpoint can be: off (0), 5-minute, or 1-hour.
Constraint: among active BPs, TTLs must be non-increasing.

Content structure per stage:
  Transcriber:  [SYS] [IMG] [ROLE_T]
  Verifier:     [SYS] [IMG] [TRES] [ROLE_V]
  Synthesizer:  [SYS] [IMG] [TRES] [VRES] [ROLE_S]

Breakpoint positions:
  BP1: after SYS
  BP2: after IMG
  BP3: after TRES (verifiers + synthesizer only)
  BP4: after VRES (synthesizer only)

Active BPs divide content into cached blocks + uncached tail.
Skipping a BP merges its tokens into the next active block.
"""
import json
from pathlib import Path

cost_file = Path(__file__).resolve().parent.parent / "_vision_stage_costs.json"
with open(cost_file) as f:
    entries = json.load(f)

# ---- Token constants (from actual data) ----
SYS = 4_900
IMG = 1_612
TRES = 1_002
VRES = 656
ROLE_T = 45
ROLE_YV = 463
ROLE_XV = 200
ROLE_S = 725

OUT_T = 523
OUT_YV = 686
OUT_XV = 701
OUT_S = 697

K_CONCURRENT = 31  # concurrent writes before system cache established
N = 2_480

# ---- Pricing (batch, per MTok) ----
INPUT = 0.50
OUTPUT = 2.50
W5 = 0.625
W1H = 1.00
RD = 0.05


def ttl_val(t):
    return {"off": 0, "5m": 1, "1h": 2}[t]


def write_rate(t):
    return {"5m": W5, "1h": W1H}[t]


def survives(ttl, hops, mode):
    """Does cache survive cross-batch?"""
    if ttl == "1h":
        return True
    if ttl == "5m":
        if mode == "all":
            return True
        if mode == "adjacent" and hops <= 1:
            return True
    return False


def build_blocks(segments, bp_config):
    """Build cache blocks from content segments and BP config.

    segments: list of (name, size) in order. e.g. [("SYS",4900), ("IMG",1612), ...]
    bp_config: dict mapping BP position index -> ttl ("5m"/"1h"/"off")
               BP positions are 0-indexed: BP1=0 (after seg 0), BP2=1 (after seg 1), etc.

    Returns: list of (block_tokens, ttl_or_None) where None = uncached tail.
    """
    n = len(segments)
    # Active BP positions and their TTLs
    active = [(pos, bp_config[pos]) for pos in sorted(bp_config)
              if bp_config[pos] != "off" and pos < n]

    blocks = []
    seg_idx = 0
    for bp_pos, ttl in active:
        # Accumulate segments from seg_idx to bp_pos (inclusive)
        tok = sum(segments[i][1] for i in range(seg_idx, bp_pos + 1))
        blocks.append((tok, ttl))
        seg_idx = bp_pos + 1

    # Remaining segments form the uncached tail
    if seg_idx < n:
        tok = sum(segments[i][1] for i in range(seg_idx, n))
        blocks.append((tok, None))  # uncached

    return blocks


def stage_cost(segments, bp_config, n_requests, output_tok,
               prior_writes, cross_batch_mode):
    """Compute cost for one batch stage.

    segments: content segments for this stage
    bp_config: BP TTL config
    n_requests: number of requests in this batch
    output_tok: output tokens per request
    prior_writes: list of (block_index, ttl, batch_hops_ago) for blocks
                  written by prior batches. Used for cross-batch cache hits.
    cross_batch_mode: "adjacent", "all", or "none"

    Returns: (total_cost, block_details)
    """
    blocks = build_blocks(segments, bp_config)
    total = 0.0
    details = []

    for bi, (tok, ttl) in enumerate(blocks):
        if ttl is None:
            # Uncached tail: always input rate
            cost = tok * n_requests * INPUT / 1e6
            details.append(("uncached", tok, n_requests, 0, cost))
            total += cost
            continue

        # Check if this block has a cross-batch cache hit
        cross_hit = False
        for pw_bi, pw_ttl, pw_hops in prior_writes:
            if pw_bi == bi and survives(pw_ttl, pw_hops, cross_batch_mode):
                cross_hit = True
                break

        if cross_hit:
            # All requests read from cross-batch cache
            n_w = 0
            n_r = n_requests
        else:
            # Within-batch: first K concurrent requests write (for shared content)
            # For per-table unique content, every request writes
            # Heuristic: if block includes SYS (block 0), K concurrent write
            # Otherwise (per-table), each unique table writes once
            if bi == 0:
                # System-containing block: K concurrent writes
                n_w = min(K_CONCURRENT, n_requests)
                n_r = n_requests - n_w
            else:
                # Per-table content: depends on within-batch pairing
                # This is handled by the caller via n_requests adjustment
                # Default: all write (unique per request)
                n_w = n_requests
                n_r = 0

        wr = write_rate(ttl)
        cost = (tok * n_w * wr + tok * n_r * RD) / 1e6
        details.append((ttl, tok, n_w, n_r, cost))
        total += cost

    # Output cost
    out_cost = output_tok * n_requests * OUTPUT / 1e6
    total += out_cost

    return total, blocks


def compute_config(bp1, bp2, bp3, bp4, cross_mode="adjacent"):
    """Compute total cost for a full pipeline run with given BP config."""

    # Validate TTL ordering among active BPs
    active_ttls = [ttl_val(t) for t in [bp1, bp2, bp3, bp4] if t != "off"]
    for i in range(len(active_ttls) - 1):
        if active_ttls[i] < active_ttls[i + 1]:
            return None

    total = 0.0

    # ==== STAGE 1: Transcriber (N requests, each table unique) ====
    # Content: [SYS] [IMG] [ROLE_T]
    t_segs = [("SYS", SYS), ("IMG", IMG), ("ROLE_T", ROLE_T)]
    t_bps = {0: bp1, 1: bp2}  # BP3/BP4 don't apply
    # No prior writes (first batch)
    t_cost, t_blocks = stage_cost(t_segs, t_bps, N, OUT_T, [], cross_mode)
    total += t_cost

    # Track what transcriber batch wrote for cross-batch
    t_writes = []
    for bi, (tok, ttl) in enumerate(t_blocks):
        if ttl is not None:
            t_writes.append((bi, ttl, 1))  # 1 hop ago for next batch

    # ==== STAGE 2: Verifiers (2N requests, y+x paired per table) ====
    # Content: [SYS] [IMG] [TRES] [ROLE_V]
    # y and x verifiers have same SYS+IMG+TRES but different ROLE_V
    # They're in the same batch, so one writes per-table blocks, other reads

    v_bps = {0: bp1, 1: bp2, 2: bp3}

    # Build block structure to understand which blocks are per-table
    v_blocks = build_blocks(
        [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_V", ROLE_YV)],
        v_bps)

    # For cross-batch: transcriber wrote blocks at their positions
    # But verifier blocks may be different (if BP3 is added)
    # Cross-batch hits work on prefix matching, so block 0 of verifier
    # matches block 0 of transcriber if content is same up to that BP.
    # Block 0 (system): always matches
    # Block 1 (image, maybe + TRES): matches if same table AND same content
    #   Transcriber had [IMG] or [IMG+ROLE_T] depending on BP2
    #   Verifier has [IMG] or [IMG+TRES] depending on BP2 and BP3
    #   Cross-batch hit only if the prefix is byte-identical
    #   BP2 in transcriber caches [SYS+IMG], BP2 in verifier also [SYS+IMG] -> match!
    #   But if verifier has no BP2 and uses BP3 to cache [SYS+IMG+TRES],
    #   that won't match transcriber's [SYS+IMG] prefix.

    # Simplification: cross-batch hits work per-block at matching positions
    # Block 0 (SYS-containing): always matches across stages
    # Block 1+ (per-table): matches if BP structure is compatible

    # Detailed verifier cost computation
    v_total = 0.0

    # Block 0: SYS (or SYS+more if BP1 is the only active BP before per-table content)
    # Cross-batch from transcriber for block 0
    v_prior = []
    if t_blocks and t_blocks[0][1] is not None:
        v_prior.append((0, t_blocks[0][1], 1))

    # For per-table blocks in verifier batch:
    # y and x verifiers for same table have identical prefix up to BP3
    # So within the batch, one writes, the other reads.
    # Also, transcriber wrote the image for each table (if BP2 active).

    # Process block by block
    for bi, (tok, ttl) in enumerate(v_blocks):
        if ttl is None:
            # Uncached tail: y_ver and x_ver have different role text sizes
            y_tail = sum(s for _, s in build_blocks(
                [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_V", ROLE_YV)],
                v_bps)[bi:] if build_blocks(
                [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_V", ROLE_YV)],
                v_bps)[bi][1] is None) if False else 0
            # Simpler: non-cached = ROLE tokens
            # With BP3: only ROLE is uncached
            # Without BP3: TRES + ROLE is uncached (but BP3 off means TRES was merged into prior block or is uncached)
            # This is already handled by build_blocks - the uncached tail is correct
            v_total += tok * N * INPUT / 1e6  # y_ver role
            # x_ver has different role size - adjust
            x_blocks = build_blocks(
                [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_V", ROLE_XV)],
                v_bps)
            x_tail = x_blocks[-1][0] if x_blocks[-1][1] is None else 0
            v_total += x_tail * N * INPUT / 1e6  # x_ver role
            # Subtract the double-counted y tail (we'll add both separately)
            v_total -= tok * N * INPUT / 1e6  # remove the generic one
            v_total += tok * N * INPUT / 1e6  # add back y_ver tail
            continue

        # Check cross-batch hit from transcriber
        cross_hit = False
        if bi == 0:
            # Block 0 (system-containing): check transcriber wrote compatible block
            for pw_bi, pw_ttl, pw_hops in v_prior:
                if pw_bi == 0 and survives(pw_ttl, pw_hops, cross_mode):
                    cross_hit = True
                    break
        elif bi == 1 and bp2 != "off":
            # Block 1 with BP2 active: image block. Transcriber wrote this for each table.
            # Check if transcriber had BP2 active too (same block structure)
            if bp2 != "off":
                for pw_bi, pw_ttl, pw_hops in t_writes:
                    if pw_bi == 1 and survives(pw_ttl, pw_hops, cross_mode):
                        cross_hit = True
                        break

        wr = write_rate(ttl)
        if cross_hit and bi == 0:
            # All 2N requests read system from cross-batch
            v_total += tok * 2 * N * RD / 1e6
        elif cross_hit and bi >= 1:
            # Per-table: transcriber wrote, both verifiers read
            v_total += tok * 2 * N * RD / 1e6
        elif bi == 0:
            # System block, within-batch: K write, rest read
            n_w = min(K_CONCURRENT, 2 * N)
            n_r = 2 * N - n_w
            v_total += (tok * n_w * wr + tok * n_r * RD) / 1e6
        else:
            # Per-table block, within-batch: y writes, x reads (paired)
            v_total += (tok * N * wr + tok * N * RD) / 1e6

    # Verifier output cost
    v_total += (OUT_YV * N + OUT_XV * N) * OUTPUT / 1e6

    # Handle y/x different tail sizes properly
    # Recalculate uncached tails
    y_blocks = build_blocks(
        [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_V", ROLE_YV)], v_bps)
    x_blocks = build_blocks(
        [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_V", ROLE_XV)], v_bps)
    y_tail = y_blocks[-1][0] if y_blocks[-1][1] is None else 0
    x_tail = x_blocks[-1][0] if x_blocks[-1][1] is None else 0

    # Remove the generic uncached tail from v_total and add correct ones
    # Actually this got messy. Let me recompute cleanly.

    # ---- CLEAN VERIFIER COMPUTATION ----
    v_total = 0.0
    # Cached blocks (all except tail) - same for y and x since prefix is identical
    cached_blocks = [(tok, ttl) for tok, ttl in v_blocks if ttl is not None]

    for bi, (tok, ttl) in enumerate(cached_blocks):
        wr = write_rate(ttl)
        cross_hit = False

        if bi == 0:
            for pw_bi, pw_ttl, pw_hops in v_prior:
                if pw_bi == 0 and survives(pw_ttl, pw_hops, cross_mode):
                    cross_hit = True
                    break
        elif bp2 != "off" and bi == 1:
            for pw_bi, pw_ttl, pw_hops in t_writes:
                if pw_bi == 1 and survives(pw_ttl, pw_hops, cross_mode):
                    cross_hit = True
                    break

        if cross_hit:
            v_total += tok * 2 * N * RD / 1e6
        elif bi == 0:
            n_w = min(K_CONCURRENT, 2 * N)
            v_total += (tok * n_w * wr + tok * (2 * N - n_w) * RD) / 1e6
        else:
            # y+x paired: one writes, one reads per table
            v_total += (tok * N * wr + tok * N * RD) / 1e6

    # Uncached tails (different for y vs x)
    v_total += y_tail * N * INPUT / 1e6
    v_total += x_tail * N * INPUT / 1e6
    # Output
    v_total += (OUT_YV * N + OUT_XV * N) * OUTPUT / 1e6

    total += v_total

    # Track verifier writes for synthesizer cross-batch
    v_writes = []
    for bi, (tok, ttl) in enumerate(v_blocks):
        if ttl is not None:
            v_writes.append((bi, ttl, 1))

    # ==== STAGE 3: Synthesizer (N requests, one per table) ====
    s_segs = [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("VRES", VRES), ("ROLE_S", ROLE_S)]
    s_bps = {0: bp1, 1: bp2, 2: bp3, 3: bp4}
    s_blocks = build_blocks(s_segs, s_bps)

    # Cross-batch sources: verifier (1 hop), transcriber (2 hops)
    s_prior = []
    # Block 0 (system): from verifier or transcriber
    if v_blocks and v_blocks[0][1] is not None:
        s_prior.append((0, v_blocks[0][1], 1))
    elif t_blocks and t_blocks[0][1] is not None:
        s_prior.append((0, t_blocks[0][1], 2))

    # Block 1 (image): from verifier (1 hop)
    # Only if synthesizer block structure matches verifier at this position
    # If both have BP2 active, block 1 is [IMG] in both -> match
    if bp2 != "off":
        for pw_bi, pw_ttl, pw_hops in v_writes:
            if pw_bi == 1:
                s_prior.append((1, pw_ttl, 1))
                break

    # Block with TRES: verifier wrote this (if BP3 active in verifier)
    # Synthesizer's BP3 block is the same TRES content -> matches
    if bp3 != "off":
        for pw_bi, pw_ttl, pw_hops in v_writes:
            # Find the block that corresponds to TRES in verifier
            # In verifier, if BP3 active, TRES is its own block after IMG
            if pw_bi == 2:  # BP3 position
                s_prior.append((2, pw_ttl, 1))
                break

    # BP4 block: synthesizer has [VRES] (or [TRES+VRES] etc.)
    # This content (both verifier outputs) was NEVER in any prior request
    # So NO cross-batch hit for BP4. Always writes.

    s_total = 0.0
    s_cached = [(tok, ttl) for tok, ttl in s_blocks if ttl is not None]
    s_tail = s_blocks[-1][0] if s_blocks[-1][1] is None else 0

    for bi, (tok, ttl) in enumerate(s_cached):
        wr = write_rate(ttl)
        cross_hit = False

        for pw_bi, pw_ttl, pw_hops in s_prior:
            if pw_bi == bi and survives(pw_ttl, pw_hops, cross_mode):
                cross_hit = True
                break

        if cross_hit:
            s_total += tok * N * RD / 1e6
        elif bi == 0:
            n_w = min(K_CONCURRENT, N)
            s_total += (tok * n_w * wr + tok * (N - n_w) * RD) / 1e6
        else:
            # Per-table unique in synthesizer batch: all write
            s_total += tok * N * wr / 1e6

    s_total += s_tail * N * INPUT / 1e6
    s_total += OUT_S * N * OUTPUT / 1e6
    total += s_total

    return total


# ---- Enumerate valid configurations ----
ttls = ["off", "5m", "1h"]
configs = []

for b1 in ttls:
    for b2 in ttls:
        for b3 in ttls:
            for b4 in ttls:
                # Validate: active TTLs must be non-increasing
                active = [ttl_val(t) for t in [b1, b2, b3, b4] if t != "off"]
                valid = all(active[i] >= active[i + 1] for i in range(len(active) - 1))
                if not valid:
                    continue
                # Skip impractical: deep BPs without BP1
                if b1 == "off" and any(t != "off" for t in [b2, b3, b4]):
                    continue

                cost = compute_config(b1, b2, b3, b4, cross_mode="adjacent")
                if cost is not None:
                    configs.append((b1, b2, b3, b4, cost))

configs.sort(key=lambda x: x[4])

baseline = next(c[4] for c in configs if c[:4] == ("off", "off", "off", "off"))
current = next(c[4] for c in configs if c[:4] == ("5m", "5m", "off", "off"))

print(f"Cache TTL Analysis: {N:,} tables (800 papers)")
print(f"Cross-batch: 5m survives adjacent batch, 1h survives all")
print()
print(f"{'BP1':>5} {'BP2':>5} {'BP3':>5} {'BP4':>5} {'Cost':>10} {'vs None':>10} {'vs Curr':>10}")
print("-" * 65)
for b1, b2, b3, b4, cost in configs:
    vs_n = baseline - cost
    vs_c = current - cost
    tag = ""
    if (b1, b2, b3, b4) == ("off", "off", "off", "off"):
        tag = " <-- no cache"
    elif (b1, b2, b3, b4) == ("5m", "5m", "off", "off"):
        tag = " <-- CURRENT"
    print(f"{b1:>5} {b2:>5} {b3:>5} {b4:>5} ${cost:>9.2f} ${vs_n:>9.2f} ${vs_c:>+9.2f}{tag}")

# ---- Top 10 ----
print()
print("TOP 10 CHEAPEST:")
print(f"{'#':>3} {'BP1':>5} {'BP2':>5} {'BP3':>5} {'BP4':>5} {'Cost':>10} {'Save%':>7}")
print("-" * 45)
for i, (b1, b2, b3, b4, cost) in enumerate(configs[:10], 1):
    pct = (baseline - cost) / baseline * 100
    print(f"{i:>3} {b1:>5} {b2:>5} {b3:>5} {b4:>5} ${cost:>9.2f} {pct:>6.1f}%")

# ---- BP4 impact ----
print()
print("BP4 IMPACT (adds verifier results cache for synthesizer):")
for b1, b2, b3, b4, cost in configs:
    if b4 == "off":
        continue
    no4 = next((c[4] for c in configs if c[:3] == (b1, b2, b3) and c[3] == "off"), None)
    if no4 is not None:
        delta = cost - no4
        print(f"  {b1}/{b2}/{b3}/{b4}: ${cost:.2f}  BP4 adds ${delta:+.2f}")

# ---- Pessimistic (no 5m cross-batch) ----
print()
print("=" * 65)
print("PESSIMISTIC: 5m = within-batch only (no cross-batch)")
print("=" * 65)
pess = []
for b1, b2, b3, b4, _ in configs:
    cost = compute_config(b1, b2, b3, b4, cross_mode="none")
    if cost is not None:
        pess.append((b1, b2, b3, b4, cost))
pess.sort(key=lambda x: x[4])
p_base = next(c[4] for c in pess if c[:4] == ("off", "off", "off", "off"))
p_curr = next(c[4] for c in pess if c[:4] == ("5m", "5m", "off", "off"))

print(f"{'BP1':>5} {'BP2':>5} {'BP3':>5} {'BP4':>5} {'Cost':>10} {'vs None':>10} {'vs Curr':>10}")
print("-" * 65)
for b1, b2, b3, b4, cost in pess[:15]:
    tag = ""
    if (b1, b2, b3, b4) == ("5m", "5m", "off", "off"):
        tag = " <-- CURRENT"
    print(f"{b1:>5} {b2:>5} {b3:>5} {b4:>5} ${cost:>9.2f} ${p_base - cost:>9.2f} ${p_curr - cost:>+9.2f}{tag}")
