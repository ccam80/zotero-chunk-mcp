"""Detailed token breakdown for candidate configs with pessimistic cross-batch.

Shows per-stage, per-block write/read/uncached counts and costs.
All 5m cross-batch = expired (pessimistic: >5m between batches).
"""
import json
from pathlib import Path

cost_file = Path(__file__).resolve().parent.parent / "_vision_stage_costs.json"
with open(cost_file) as f:
    entries = json.load(f)

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

K = 31
N = 2_480

INPUT = 0.50
OUTPUT = 2.50
W5 = 0.625
W1H = 1.00
RD = 0.05


def wr(ttl):
    return {"5m": W5, "1h": W1H}[ttl]


def build_blocks(segs, bps):
    """segs: [(name, size)], bps: {pos: ttl}. Returns [(name, size, ttl|None)]."""
    active = [(p, bps[p]) for p in sorted(bps) if bps[p] != "off" and p < len(segs)]
    blocks = []
    idx = 0
    for bp_pos, ttl in active:
        names = [segs[i][0] for i in range(idx, bp_pos + 1)]
        tok = sum(segs[i][1] for i in range(idx, bp_pos + 1))
        blocks.append(("+".join(names), tok, ttl))
        idx = bp_pos + 1
    if idx < len(segs):
        names = [segs[i][0] for i in range(idx, len(segs))]
        tok = sum(segs[i][1] for i in range(idx, len(segs)))
        blocks.append(("+".join(names), tok, None))
    return blocks


def survives_1h_only(ttl, hops):
    """Pessimistic: only 1h survives cross-batch."""
    return ttl == "1h"


def analyze_config(bp1, bp2, bp3, bp4):
    label = f"{bp1}/{bp2}/{bp3}/{bp4}"
    print()
    print("=" * 90)
    print(f"  CONFIG: {label}")
    print("=" * 90)

    grand_total = 0.0

    # ---- TRANSCRIBER ----
    t_segs = [("SYS", SYS), ("IMG", IMG), ("ROLE_T", ROLE_T)]
    t_bps = {0: bp1, 1: bp2}
    t_blocks = build_blocks(t_segs, t_bps)

    print(f"\n  TRANSCRIBER BATCH ({N} requests, each table unique)")
    print(f"  {'Block':<20} {'Tokens':>7} {'TTL':>5} {'Writes':>8} {'Reads':>8} {'Uncached':>9} {'Cost':>10}")
    print(f"  {'-'*20} {'-'*7} {'-'*5} {'-'*8} {'-'*8} {'-'*9} {'-'*10}")

    t_cost = 0.0
    t_written = {}  # block_idx -> ttl

    for bi, (name, tok, ttl) in enumerate(t_blocks):
        if ttl is None:
            c = tok * N * INPUT / 1e6
            print(f"  {name:<20} {tok:>7,} {'---':>5} {'':>8} {'':>8} {N:>9,} ${c:>9.4f}")
        elif bi == 0:
            n_w = min(K, N)
            n_r = N - n_w
            c = (tok * n_w * wr(ttl) + tok * n_r * RD) / 1e6
            print(f"  {name:<20} {tok:>7,} {ttl:>5} {n_w:>8,} {n_r:>8,} {'':>9} ${c:>9.4f}")
            t_written[bi] = ttl
        else:
            # Per-table unique: all write
            c = tok * N * wr(ttl) / 1e6
            print(f"  {name:<20} {tok:>7,} {ttl:>5} {N:>8,} {0:>8} {'':>9} ${c:>9.4f}")
            t_written[bi] = ttl

    out_c = OUT_T * N * OUTPUT / 1e6
    print(f"  {'output':<20} {OUT_T:>7,} {'':>5} {'':>8} {'':>8} {'':>9} ${out_c:>9.4f}")
    t_cost = sum(
        (tok * min(K, N) * wr(ttl) + tok * (N - min(K, N)) * RD) / 1e6
        if ttl is not None and bi == 0
        else tok * N * wr(ttl) / 1e6 if ttl is not None
        else tok * N * INPUT / 1e6
        for bi, (name, tok, ttl) in enumerate(t_blocks)
    ) + out_c
    print(f"  {'STAGE TOTAL':<20} {'':>7} {'':>5} {'':>8} {'':>8} {'':>9} ${t_cost:>9.4f}")
    grand_total += t_cost

    # ---- VERIFIERS ----
    v_segs = [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_V", 0)]  # role handled separately
    v_bps = {0: bp1, 1: bp2, 2: bp3}
    v_blocks_raw = build_blocks(v_segs, v_bps)
    # Remove zero-size tail if role is 0
    v_blocks = [(n, t, ttl) for n, t, ttl in v_blocks_raw if t > 0 or ttl is None]

    print(f"\n  VERIFIER BATCH ({2*N} requests: {N} y_ver + {N} x_ver, paired)")
    print(f"  {'Block':<20} {'Tokens':>7} {'TTL':>5} {'Writes':>8} {'Reads':>8} {'Uncached':>9} {'Cost':>10} {'Note'}")
    print(f"  {'-'*20} {'-'*7} {'-'*5} {'-'*8} {'-'*8} {'-'*9} {'-'*10} {'-'*20}")

    v_cost = 0.0
    v_written = {}

    for bi, (name, tok, ttl) in enumerate(v_blocks):
        if ttl is None:
            continue  # handle role separately below

        # Cross-batch from transcriber?
        cross = False
        if bi in t_written and survives_1h_only(t_written[bi], 1):
            cross = True

        if cross:
            n_w = 0
            n_r = 2 * N
            note = "cross-batch read (transcriber)"
        elif bi == 0:
            n_w = min(K, 2 * N)
            n_r = 2 * N - n_w
            note = f"K={K} concurrent writes"
        else:
            # y+x paired: one writes, one reads per table
            n_w = N
            n_r = N
            note = "y writes, x reads (paired)"

        c = (tok * n_w * wr(ttl) + tok * n_r * RD) / 1e6
        v_cost += c
        v_written[bi] = ttl
        print(f"  {name:<20} {tok:>7,} {ttl:>5} {n_w:>8,} {n_r:>8,} {'':>9} ${c:>9.4f} {note}")

    # Uncached role text (different for y vs x)
    # What's in the tail depends on which BPs are active
    y_full = build_blocks(
        [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_YV", ROLE_YV)], v_bps)
    x_full = build_blocks(
        [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("ROLE_XV", ROLE_XV)], v_bps)
    y_tail = y_full[-1][1] if y_full[-1][2] is None else 0
    x_tail = x_full[-1][1] if x_full[-1][2] is None else 0

    y_c = y_tail * N * INPUT / 1e6
    x_c = x_tail * N * INPUT / 1e6
    v_cost += y_c + x_c
    print(f"  {'y_ver tail':<20} {y_tail:>7,} {'---':>5} {'':>8} {'':>8} {N:>9,} ${y_c:>9.4f}")
    print(f"  {'x_ver tail':<20} {x_tail:>7,} {'---':>5} {'':>8} {'':>8} {N:>9,} ${x_c:>9.4f}")

    out_c = (OUT_YV * N + OUT_XV * N) * OUTPUT / 1e6
    v_cost += out_c
    print(f"  {'output (y+x)':<20} {OUT_YV+OUT_XV:>7,} {'':>5} {'':>8} {'':>8} {'':>9} ${out_c:>9.4f}")
    print(f"  {'STAGE TOTAL':<20} {'':>7} {'':>5} {'':>8} {'':>8} {'':>9} ${v_cost:>9.4f}")
    grand_total += v_cost

    # ---- SYNTHESIZER ----
    s_segs = [("SYS", SYS), ("IMG", IMG), ("TRES", TRES), ("VRES", VRES), ("ROLE_S", ROLE_S)]
    s_bps = {0: bp1, 1: bp2, 2: bp3, 3: bp4}
    s_blocks = build_blocks(s_segs, s_bps)

    print(f"\n  SYNTHESIZER BATCH ({N} requests, one per table)")
    print(f"  {'Block':<20} {'Tokens':>7} {'TTL':>5} {'Writes':>8} {'Reads':>8} {'Uncached':>9} {'Cost':>10} {'Note'}")
    print(f"  {'-'*20} {'-'*7} {'-'*5} {'-'*8} {'-'*8} {'-'*9} {'-'*10} {'-'*20}")

    s_cost = 0.0

    for bi, (name, tok, ttl) in enumerate(s_blocks):
        if ttl is None:
            c = tok * N * INPUT / 1e6
            s_cost += c
            print(f"  {name:<20} {tok:>7,} {'---':>5} {'':>8} {'':>8} {N:>9,} ${c:>9.4f}")
            continue

        # Cross-batch from verifier?
        cross = False
        note = ""
        if bi in v_written and survives_1h_only(v_written[bi], 1):
            cross = True
            note = "cross-batch read (verifier)"
        elif bi == 0 and 0 in t_written and survives_1h_only(t_written[0], 2):
            cross = True
            note = "cross-batch read (transcriber, 2 hops)"

        if cross:
            c = tok * N * RD / 1e6
            s_cost += c
            print(f"  {name:<20} {tok:>7,} {ttl:>5} {0:>8} {N:>8,} {'':>9} ${c:>9.4f} {note}")
        elif bi == 0:
            n_w = min(K, N)
            n_r = N - n_w
            c = (tok * n_w * wr(ttl) + tok * n_r * RD) / 1e6
            s_cost += c
            note = f"K={K} concurrent writes"
            print(f"  {name:<20} {tok:>7,} {ttl:>5} {n_w:>8,} {n_r:>8,} {'':>9} ${c:>9.4f} {note}")
        else:
            # Per-table unique, all write (BP4 content never seen before)
            c = tok * N * wr(ttl) / 1e6
            s_cost += c
            note = "all write (unique per table)"
            if "VRES" in name:
                note = "all write (both ver outputs, never cached)"
            print(f"  {name:<20} {tok:>7,} {ttl:>5} {N:>8,} {0:>8} {'':>9} ${c:>9.4f} {note}")

    out_c = OUT_S * N * OUTPUT / 1e6
    s_cost += out_c
    print(f"  {'output':<20} {OUT_S:>7,} {'':>5} {'':>8} {'':>8} {'':>9} ${out_c:>9.4f}")
    print(f"  {'STAGE TOTAL':<20} {'':>7} {'':>5} {'':>8} {'':>8} {'':>9} ${s_cost:>9.4f}")
    grand_total += s_cost

    print(f"\n  {'GRAND TOTAL':<20} {'':>7} {'':>5} {'':>8} {'':>8} {'':>9} ${grand_total:>9.4f}")
    return grand_total


# ---- Run the three candidates ----
results = {}
for cfg in [("1h", "1h", "1h", "off"),
            ("1h", "1h", "1h", "5m"),
            ("1h", "1h", "5m", "5m"),
            ("1h", "1h", "5m", "off"),
            ("5m", "5m", "off", "off")]:  # current for reference
    cost = analyze_config(*cfg)
    results["/".join(cfg)] = cost

print("\n")
print("=" * 90)
print("COMPARISON SUMMARY (pessimistic: no 5m cross-batch)")
print("=" * 90)
print(f"\n  {'Config':<20} {'Cost':>10} {'vs Current':>12} {'vs None':>10}")
print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*10}")
none_cost = 54.78  # from earlier analysis
curr_cost = results["5m/5m/off/off"]
for label, cost in sorted(results.items(), key=lambda x: x[1]):
    print(f"  {label:<20} ${cost:>9.2f} ${curr_cost - cost:>+11.2f} ${none_cost - cost:>9.2f}")
