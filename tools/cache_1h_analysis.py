"""Compare 5-minute vs 1-hour cache TTL for batch vision pipeline.

Models cross-batch reuse and scaling to larger batch sizes.
"""
import json
from pathlib import Path

cost_file = Path(__file__).resolve().parent.parent / "_vision_stage_costs.json"
with open(cost_file) as f:
    entries = json.load(f)

# ── Per-stage aggregates ──────────────────────────────────────────────
stages: dict[str, dict] = {}
for e in entries:
    r = e["agent_role"]
    stages.setdefault(r, {"n": 0, "inp": 0, "out": 0, "cw": 0, "cr": 0})
    stages[r]["n"] += 1
    stages[r]["inp"] += e["input_tokens"]
    stages[r]["out"] += e["output_tokens"]
    stages[r]["cw"] += e["cache_write_tokens"]
    stages[r]["cr"] += e["cache_read_tokens"]

CACHEABLE_PER_REQ = 6_512  # system (~4900) + image (~1600)
SYS_TOKENS = 4_900         # system prompt portion
IMG_TOKENS = CACHEABLE_PER_REQ - SYS_TOKENS  # image portion (~1612)

# ── Batch pricing rates (per MTok) ───────────────────────────────────
# Batch discount = 50% on everything (input, output, cache)
BASE_INPUT = 1.00   # Haiku 4.5 input
BASE_OUTPUT = 5.00  # Haiku 4.5 output

B_INPUT  = BASE_INPUT * 0.50     # $0.50
B_OUTPUT = BASE_OUTPUT * 0.50    # $2.50

# 5-minute (ephemeral) cache: 1.25× base
B5_WRITE = BASE_INPUT * 1.25 * 0.50   # $0.625
B5_READ  = BASE_INPUT * 0.10 * 0.50   # $0.05

# 1-hour cache: 2.0× base (for writes only; reads same rate)
B1H_WRITE = BASE_INPUT * 2.00 * 0.50  # $1.00
B1H_READ  = BASE_INPUT * 0.10 * 0.50  # $0.05  (same as 5-min)

ROLES = ["transcriber", "y_verifier", "x_verifier", "synthesizer"]

# ── ACTUAL 5-MIN COSTS (from data) ───────────────────────────────────
print("=" * 80)
print("ACTUAL 5-MINUTE CACHE (41 tables, batch sizes: 41, 4, 82, 41)")
print("=" * 80)

total_5m = 0.0
for role in ROLES:
    s = stages[role]
    cost = (s["inp"] * B_INPUT + s["out"] * B_OUTPUT +
            s["cw"] * B5_WRITE + s["cr"] * B5_READ) / 1e6
    total_5m += cost
    hit = s["cr"] / (s["cw"] + s["cr"]) * 100
    print(f"  {role:<15} writes={s['cw']:>8,}  reads={s['cr']:>8,}  "
          f"hit={hit:>5.1f}%  cost=${cost:.4f}")
print(f"  {'TOTAL':<15} {'':>8}  {'':>8}  {'':>6}  cost=${total_5m:.4f}")

# ── MODEL: 1-HOUR CACHE (cross-batch reuse) ──────────────────────────
# With 1-hour TTL, cache from transcriber batch survives to verifier
# and synthesizer batches.
#
# What changes for verifier/synthesizer:
#   - System prompt: written by transcriber batch, still alive -> READ
#   - Image (per-table): written by transcriber for that table -> READ
#   - Both currently show as "writes" for the concurrent-first requests
#     within each batch. With 1h, those become reads too.
#
# NOT all writes convert: some are genuinely new content or concurrent
# races within the transcriber batch itself.

print()
print("=" * 80)
print("MODELED 1-HOUR CACHE (cross-batch reuse)")
print("=" * 80)

# Transcriber: FIRST batch — no prior cache to read from.
# Within-batch behavior unchanged (same concurrency pattern).
# Only difference: writes cost more ($1.00 vs $0.625).
t = stages["transcriber"]
t_cost_1h = (t["inp"] * B_INPUT + t["out"] * B_OUTPUT +
             t["cw"] * B1H_WRITE + t["cr"] * B1H_READ) / 1e6
t_cost_5m = (t["inp"] * B_INPUT + t["out"] * B_OUTPUT +
             t["cw"] * B5_WRITE + t["cr"] * B5_READ) / 1e6
print(f"  transcriber    writes={t['cw']:>8,}  reads={t['cr']:>8,}  "
      f"cost=${t_cost_1h:.4f}  (5m was ${t_cost_5m:.4f}, delta=${t_cost_1h - t_cost_5m:+.4f})")
print(f"    writes unchanged (first batch), but cost {B1H_WRITE:.3f} vs {B5_WRITE:.3f}/MTok")

total_1h = t_cost_1h

# Verifiers & Synthesizer: cross-batch cache means their writes -> reads.
# The current writes are from concurrent-first requests that beat the cache.
# With 1h cache, transcriber already wrote everything -> all reads.
#
# BUT: not 100% conversion. Some writes may be from content that differs
# slightly. Conservatively model 90% of current writes converting to reads.
CONVERSION_RATE = 0.90

for role in ["y_verifier", "x_verifier", "synthesizer"]:
    s = stages[role]
    converted = int(s["cw"] * CONVERSION_RATE)
    remaining_writes = s["cw"] - converted
    new_reads = s["cr"] + converted

    cost = (s["inp"] * B_INPUT + s["out"] * B_OUTPUT +
            remaining_writes * B1H_WRITE + new_reads * B1H_READ) / 1e6
    cost_5m = (s["inp"] * B_INPUT + s["out"] * B_OUTPUT +
               s["cw"] * B5_WRITE + s["cr"] * B5_READ) / 1e6
    total_1h += cost
    print(f"  {role:<15} writes={remaining_writes:>8,}  reads={new_reads:>8,}  "
          f"cost=${cost:.4f}  (5m was ${cost_5m:.4f}, delta=${cost - cost_5m:+.4f})")
    print(f"    {converted:,} write tok converted to reads ({CONVERSION_RATE*100:.0f}%)")

print(f"\n  {'TOTAL 1h':<15} {'':>8}  {'':>8}  {'':>6}  cost=${total_1h:.4f}")
print(f"  {'TOTAL 5m':<15} {'':>8}  {'':>8}  {'':>6}  cost=${total_5m:.4f}")
saving = total_5m - total_1h
print(f"  {'SAVING':<15} {'':>8}  {'':>8}  {'':>6}  ${saving:.4f}/run ({saving/total_5m*100:.1f}%)")

# ── SCALING: larger batch sizes ──────────────────────────────────────
print()
print("=" * 80)
print("SCALING: HIT RATE vs BATCH SIZE")
print("=" * 80)
print()
print("Within a batch of N, concurrent execution means ~K requests write")
print("before cache is established. Remaining N-K read. K is roughly constant")
print("(depends on processing speed, not batch size).")
print()

# From transcriber data: 41 requests, 19% hit -> ~33 writes, ~8 reads
# -> K ≈ 33 concurrent writers for system prompt
t_writes_n = t["cw"]  # 216,298
t_reads_n = t["cr"]   # 50,700
n_tables = 41

# System writes: requests that wrote system prompt
# Image writes: every request writes its unique image (1 write per table)
# System reads: requests that read system prompt
# Image reads: 0 within transcriber (each image unique)
#
# Total writes = sys_writes * SYS + n * IMG = 216,298
# Total reads  = sys_reads * SYS = 50,700
# sys_reads = 50,700 / 4900 ≈ 10.3 -> ~10 requests got system cache hit
# sys_writes = 41 - 10 = 31 requests wrote system cache
# Check: 31 * 4900 + 41 * 1612 = 151,900 + 66,092 = 217,992 ≈ 216,298 ✓ (close)

sys_reads_count = round(t_reads_n / SYS_TOKENS)
sys_writes_count = n_tables - sys_reads_count
print(f"From 41-table transcriber batch:")
print(f"  System cache: {sys_writes_count} writes, {sys_reads_count} reads")
print(f"  Image cache:  {n_tables} writes, 0 reads (each unique)")
print(f"  -> ~{sys_writes_count} concurrent requests process before system cache established")

K_sys = sys_writes_count  # concurrent writers ≈ 31

print(f"\nProjected hit rates for transcriber at different batch sizes:")
print(f"  {'Batch N':>10}  {'Sys writes':>12}  {'Sys reads':>12}  {'Overall hit%':>14}  {'Cost/table':>12}")
print(f"  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*14}  {'-'*12}")

for N in [41, 100, 500, 1000, 2480]:
    # System: K_sys write, N-K_sys read (K capped at N)
    sw = min(K_sys, N)
    sr = N - sw
    # Image: all N write (unique per table)
    iw = N
    ir = 0
    total_w = sw * SYS_TOKENS + iw * IMG_TOKENS
    total_r = sr * SYS_TOKENS + ir * IMG_TOKENS
    hit = total_r / (total_w + total_r) * 100 if (total_w + total_r) > 0 else 0

    # Cost per table (5-min)
    avg_inp = t["inp"] / n_tables  # non-cached input per request
    avg_out = t["out"] / n_tables
    avg_w = total_w / N
    avg_r = total_r / N
    cost_per = (avg_inp * B_INPUT + avg_out * B_OUTPUT +
                avg_w * B5_WRITE + avg_r * B5_READ) / 1e6
    print(f"  {N:>10,}  {sw * SYS_TOKENS:>12,}  {sr * SYS_TOKENS:>12,}  "
          f"{hit:>13.1f}%  ${cost_per:.6f}")

# ── Same for verifier batch (paired y+x for same table) ──────────────
print()
print("Verifier batch (y+x paired, size 2N):")
# In the 82-request verifier batch, both system AND image can hit:
# - System: first K write, rest read (same as transcriber)
# - Image: y and x share same image -> one writes, other reads
# From data: y_verifier 89,457 writes, 177,541 reads (41 requests)
#            x_verifier 74,187 writes, 192,811 reads (41 requests)
# Combined: 163,644 writes, 370,352 reads across 82 requests
v_total_w = stages["y_verifier"]["cw"] + stages["x_verifier"]["cw"]
v_total_r = stages["y_verifier"]["cr"] + stages["x_verifier"]["cr"]
v_hit = v_total_r / (v_total_w + v_total_r) * 100
print(f"  Current (82 reqs): writes={v_total_w:,}  reads={v_total_r:,}  hit={v_hit:.1f}%")

# At 2N requests: K_sys system writes, 2N-K_sys system reads
# For images: N unique images, each written once and read once (y writes, x reads or vice versa)
# -> N image writes + N image reads
print(f"\n  {'Batch 2N':>10}  {'Sys hit%':>10}  {'Img hit%':>10}  {'Overall hit%':>14}")
print(f"  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*14}")
for N in [41, 100, 500, 1000, 2480]:
    batch_2n = 2 * N
    sw = min(K_sys, batch_2n)
    sr = batch_2n - sw
    sys_hit = sr / batch_2n * 100
    # Image: N unique, each appears twice (y+x), first writes second reads
    img_w = N
    img_r = N
    img_hit = 50.0  # always 50% for paired
    total_w = sw * SYS_TOKENS + img_w * IMG_TOKENS
    total_r = sr * SYS_TOKENS + img_r * IMG_TOKENS
    overall_hit = total_r / (total_w + total_r) * 100
    print(f"  {batch_2n:>10,}  {sys_hit:>9.1f}%  {img_hit:>9.1f}%  {overall_hit:>13.1f}%")

# ── EXTRAPOLATION TO 800 PAPERS ──────────────────────────────────────
print()
print("=" * 80)
print("EXTRAPOLATION: 800 PAPERS (~2,480 TABLES)")
print("=" * 80)

N = 2480
scale = N / n_tables

# Model each stage at scale
def model_stage_cost(role, batch_size, has_cross_batch, ttl, paired_images=False):
    """Model cost for a stage at given batch size and TTL."""
    s = stages[role]
    avg_inp = s["inp"] / s["n"]
    avg_out = s["out"] / s["n"]

    w_rate = B1H_WRITE if ttl == "1h" else B5_WRITE
    r_rate = B1H_READ if ttl == "1h" else B5_READ

    n_req = batch_size

    if has_cross_batch and ttl == "1h":
        # System + image already cached from prior batch -> all reads
        # Only truly new concurrent writes within this batch are ~0
        # because cross-batch cache is guaranteed alive
        sys_w = 0
        sys_r = n_req
        if paired_images:
            img_w = n_req // 2  # half the tables write
            img_r = n_req // 2  # other half reads
        else:
            img_w = 0  # images cached from transcriber
            img_r = n_req
    else:
        # First batch or no cross-batch: within-batch only
        sys_w = min(K_sys, n_req)
        sys_r = n_req - sys_w
        if paired_images:
            img_w = n_req // 2
            img_r = n_req // 2
        else:
            img_w = n_req  # each unique
            img_r = 0

    total_w = sys_w * SYS_TOKENS + img_w * IMG_TOKENS
    total_r = sys_r * SYS_TOKENS + img_r * IMG_TOKENS
    cost = (avg_inp * n_req * B_INPUT + avg_out * n_req * B_OUTPUT +
            total_w * w_rate + total_r * r_rate) / 1e6
    hit = total_r / (total_w + total_r) * 100 if (total_w + total_r) > 0 else 0
    return cost, hit, total_w, total_r

print(f"\n{'':>15} {'5-min cache':>30}  {'1-hour cache':>30}  {'Delta':>8}")
print(f"{'Stage':<15} {'Cost':>12} {'Hit%':>8} {'Writes':>9}  {'Cost':>12} {'Hit%':>8} {'Writes':>9}  {'':>8}")
print("-" * 110)

total_5m_scaled = 0
total_1h_scaled = 0

configs = [
    ("transcriber", N, False, False),
    ("y_verifier", N, True, False),   # cross-batch from transcriber
    ("x_verifier", N, True, False),
    ("synthesizer", N, True, False),  # cross-batch from verifiers
]

# Note: in the actual batch, y+x go in ONE batch of 2N.
# But cost logging separates them. Model them individually for simplicity.

for role, batch_n, cross_batch, paired in configs:
    c5, h5, w5, r5 = model_stage_cost(role, batch_n, has_cross_batch=False,
                                        ttl="5m", paired_images=paired)
    c1h, h1h, w1h, r1h = model_stage_cost(role, batch_n, has_cross_batch=cross_batch,
                                            ttl="1h", paired_images=paired)
    total_5m_scaled += c5
    total_1h_scaled += c1h
    delta = c1h - c5
    print(f"{role:<15} ${c5:>11.2f} {h5:>7.1f}% {w5:>9,}  "
          f"${c1h:>11.2f} {h1h:>7.1f}% {w1h:>9,}  ${delta:>+7.2f}")

print("-" * 110)
saving_scaled = total_5m_scaled - total_1h_scaled
print(f"{'TOTAL':<15} ${total_5m_scaled:>11.2f} {'':>8} {'':>9}  "
      f"${total_1h_scaled:>11.2f} {'':>8} {'':>9}  ${-saving_scaled:>+7.2f}")
print(f"\n  1-hour saves ${saving_scaled:.2f} vs 5-minute ({saving_scaled/total_5m_scaled*100:.1f}%)")
print(f"  5-min:  ${total_5m_scaled:.2f}")
print(f"  1-hour: ${total_1h_scaled:.2f}")

# Also: what about no cache at all?
total_nocache = 0
for role in ROLES:
    s = stages[role]
    avg_inp = s["inp"] / s["n"]
    avg_out = s["out"] / s["n"]
    avg_cacheable = CACHEABLE_PER_REQ  # would all be input without cache
    cost = (avg_inp + avg_cacheable) * N * B_INPUT / 1e6 + avg_out * N * B_OUTPUT / 1e6
    total_nocache += cost
print(f"  No cache: ${total_nocache:.2f}")
print(f"  5-min saves ${total_nocache - total_5m_scaled:.2f} vs no-cache ({(total_nocache - total_5m_scaled)/total_nocache*100:.1f}%)")
print(f"  1-hour saves ${total_nocache - total_1h_scaled:.2f} vs no-cache ({(total_nocache - total_1h_scaled)/total_nocache*100:.1f}%)")
