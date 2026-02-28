"""Analyze batch API cache cost/benefit from vision stage cost log."""
import json
import sys
from pathlib import Path

cost_file = Path(__file__).resolve().parent.parent / "_vision_stage_costs.json"
if not cost_file.exists():
    print(f"Cost log not found: {cost_file}")
    sys.exit(1)

with open(cost_file) as f:
    entries = json.load(f)

print(f"Total entries: {len(entries)}")

# Haiku 4.5 batch pricing (per MTok) — 50% discount on everything
B_INPUT = 0.50
B_OUTPUT = 2.50
B_CACHE_WRITE = 0.625  # 1.25 * 0.50
B_CACHE_READ = 0.05    # 0.10 * 0.50

# Aggregate
inp = sum(e["input_tokens"] for e in entries)
out = sum(e["output_tokens"] for e in entries)
cw = sum(e["cache_write_tokens"] for e in entries)
cr = sum(e["cache_read_tokens"] for e in entries)

# Scenario A: Batch + Cache (actual)
cost_a = inp * B_INPUT/1e6 + out * B_OUTPUT/1e6 + cw * B_CACHE_WRITE/1e6 + cr * B_CACHE_READ/1e6

# Scenario B: Batch WITHOUT cache
total_inp_nocache = inp + cw + cr
cost_b = total_inp_nocache * B_INPUT/1e6 + out * B_OUTPUT/1e6

# Scenario C: Batch + Cache with 0% hit (all writes, no reads)
cost_c = inp * B_INPUT/1e6 + out * B_OUTPUT/1e6 + (cw + cr) * B_CACHE_WRITE/1e6

print("\n=== Cost Comparison (41-table batch run) ===\n")
print("  Scenario A: Batch + Cache (actual)")
print(f"    Input:       {inp:>10,} tok x $0.50/MTok  = ${inp * B_INPUT/1e6:.4f}")
print(f"    Output:      {out:>10,} tok x $2.50/MTok  = ${out * B_OUTPUT/1e6:.4f}")
print(f"    Cache write: {cw:>10,} tok x $0.625/MTok = ${cw * B_CACHE_WRITE/1e6:.4f}")
print(f"    Cache read:  {cr:>10,} tok x $0.05/MTok  = ${cr * B_CACHE_READ/1e6:.4f}")
print(f"    TOTAL: ${cost_a:.4f}")

print("\n  Scenario B: Batch WITHOUT cache")
print(f"    Input:       {total_inp_nocache:>10,} tok x $0.50/MTok  = ${total_inp_nocache * B_INPUT/1e6:.4f}")
print(f"    Output:      {out:>10,} tok x $2.50/MTok  = ${out * B_OUTPUT/1e6:.4f}")
print(f"    TOTAL: ${cost_b:.4f}")

print(f"\n  Scenario C: Batch + Cache, 0% hit rate (worst case)")
print(f"    TOTAL: ${cost_c:.4f}")

saving = cost_b - cost_a
saving_pct = saving / cost_b * 100
print(f"\n=== Result ===")
print(f"  Cache saving vs no-cache:  ${saving:.4f} ({saving_pct:.1f}%)")
print(f"  Actual hit rate:           {cr/(cw+cr)*100:.1f}% of cacheable tokens")

# Break-even: write overhead (0.625-0.50=0.125/MTok) vs read saving (0.50-0.05=0.45/MTok)
# 0.125 * W = 0.45 * R  =>  R/(W+R) = 0.125 / (0.125+0.45) = 21.7%
be = 0.125 / (0.125 + 0.45) * 100
print(f"  Break-even hit rate:       {be:.1f}%")
print(f"  Margin above break-even:   {cr/(cw+cr)*100 - be:.1f} pp")

# Worst case penalty (0% hits)
penalty = cost_c - cost_b
print(f"\n  Worst case (0% hits) penalty vs no-cache: ${penalty:.4f} (+{penalty/cost_b*100:.1f}%)")

# Per-stage breakdown
print("\n=== Per-stage cache economics ===")
header = f"{'Stage':<15} {'Writes':>10} {'Reads':>10} {'Hit%':>7} {'w/Cache':>10} {'no-Cache':>10} {'Saving':>8}"
print(header)
print("-" * len(header))

roles: dict[str, list] = {}
for e in entries:
    r = e["agent_role"]
    roles.setdefault(r, []).append(e)

for role in ["transcriber", "y_verifier", "x_verifier", "synthesizer"]:
    items = roles.get(role, [])
    i = sum(e["input_tokens"] for e in items)
    o = sum(e["output_tokens"] for e in items)
    w = sum(e["cache_write_tokens"] for e in items)
    rd = sum(e["cache_read_tokens"] for e in items)
    c_cache = i*B_INPUT/1e6 + o*B_OUTPUT/1e6 + w*B_CACHE_WRITE/1e6 + rd*B_CACHE_READ/1e6
    c_nocache = (i+w+rd)*B_INPUT/1e6 + o*B_OUTPUT/1e6
    hit = rd/(w+rd)*100 if (w+rd) > 0 else 0
    sv = c_nocache - c_cache
    print(f"{role:<15} {w:>10,} {rd:>10,} {hit:>6.1f}% ${c_cache:>9.4f} ${c_nocache:>9.4f} ${sv:>7.4f}")

# Extrapolate to 800 papers
scale = 2480 / 41  # ~60.5x
print(f"\n=== Extrapolation to 800 papers (~2,480 tables) ===")
print(f"  With cache:    ${cost_a * scale:.2f}")
print(f"  Without cache: ${cost_b * scale:.2f}")
print(f"  Saving:        ${saving * scale:.2f}")
