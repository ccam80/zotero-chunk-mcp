"""Analyze economics of adding BP3 (cache breakpoint after transcriber results).

Current prompt structure per request:
  [SYSTEM: shared_system ~4,900 tok] {BP1}
  [USER: common_context + image ~1,612 tok] {BP2}
  [USER: role text + prev agent outputs]  <-- currently uncached

Proposed BP3:
  [SYSTEM: shared_system ~4,900 tok] {BP1}
  [USER: common_context + image ~1,612 tok] {BP2}
  [USER: transcriber results ~T tok] {BP3}
  [USER: remaining role text]

BP3 would let the 2nd verifier and synthesizer cache-read the
transcriber results instead of paying uncached input rate.
"""
import json
from pathlib import Path

cost_file = Path(__file__).resolve().parent.parent / "_vision_stage_costs.json"
with open(cost_file) as f:
    entries = json.load(f)

# Per-stage aggregates
stages = {}
for e in entries:
    r = e["agent_role"]
    stages.setdefault(r, {"n": 0, "inp": 0, "out": 0, "cw": 0, "cr": 0})
    stages[r]["n"] += 1
    stages[r]["inp"] += e["input_tokens"]
    stages[r]["out"] += e["output_tokens"]
    stages[r]["cw"] += e["cache_write_tokens"]
    stages[r]["cr"] += e["cache_read_tokens"]

# Per-table breakdown
tables = {}
for e in entries:
    tables.setdefault(e["table_id"], {})[e["agent_role"]] = e

print("Non-cached input tokens per request (first 10 tables):")
print(f"{'table_id':<25} {'transcr':>8} {'y_ver':>8} {'x_ver':>8} {'synth':>8}")
print("-" * 60)
for tid in sorted(tables.keys())[:10]:
    t = tables[tid]
    vals = []
    for role in ["transcriber", "y_verifier", "x_verifier", "synthesizer"]:
        vals.append(t.get(role, {}).get("input_tokens", 0))
    print(f"{tid:<25} {vals[0]:>8,} {vals[1]:>8,} {vals[2]:>8,} {vals[3]:>8,}")

print()
print("Stage averages:")
for role in ["transcriber", "y_verifier", "x_verifier", "synthesizer"]:
    s = stages[role]
    avg = s["inp"] / s["n"]
    print(f"  {role:<15} avg non-cached input: {avg:>8.0f} tok")

print()
print("What's in each stage's non-cached input:")
print("  transcriber:  role preamble only (~45 tok)")
print("  y_verifier:   role preamble + transcriber JSON output")
print("  x_verifier:   role preamble + transcriber JSON output")
print("  synthesizer:  role preamble + transcriber + y_ver + x_ver outputs")

# Estimate component sizes
avg_t_inp = stages["transcriber"]["inp"] / stages["transcriber"]["n"]
avg_y_inp = stages["y_verifier"]["inp"] / stages["y_verifier"]["n"]
avg_x_inp = stages["x_verifier"]["inp"] / stages["x_verifier"]["n"]
avg_s_inp = stages["synthesizer"]["inp"] / stages["synthesizer"]["n"]

# Role preamble is small (~200 tok for verifiers, ~45 for transcriber)
PREAMBLE = 200
est_transcriber_output = avg_y_inp - PREAMBLE
est_verifier_output = (avg_s_inp - avg_y_inp) / 2
# Cross-check: x_verifier should have similar transcriber output
est_transcriber_output_x = avg_x_inp - PREAMBLE

print()
print(f"Estimated transcriber output: ~{est_transcriber_output:.0f} tok (from y_ver)")
print(f"                              ~{est_transcriber_output_x:.0f} tok (from x_ver)")
print(f"Estimated per-verifier output: ~{est_verifier_output:.0f} tok")
print(f"Synthesizer extra over y_ver: {avg_s_inp - avg_y_inp:.0f} tok (both verifier outputs)")

# Use average of y and x estimates
T = (est_transcriber_output + est_transcriber_output_x) / 2
V = est_verifier_output

print()
print(f"Using T = {T:.0f} tok (transcriber results per table)")
print(f"Using V = {V:.0f} tok (verifier results per agent per table)")

# Pricing (batch, per MTok)
B_INPUT = 0.50
B5_WRITE = 0.625   # 5-min
B1H_WRITE = 1.00   # 1-hour
B_READ = 0.05      # same for both TTLs

N = 2480  # 800 papers

print()
print("=" * 70)
print("BP3: CACHE TRANSCRIBER RESULTS")
print("=" * 70)
print()
print("Per table, transcriber results appear in 3 later requests:")
print("  y_verifier, x_verifier, synthesizer")
print(f"  Currently: 3 x {T:.0f} tok x $0.50/MTok = ${3 * T * B_INPUT / 1e6:.6f}/table")
print()

# --- 5-min cache ---
print("5-MIN CACHE with BP3:")
print("  Verifier batch (y+x in same batch, paired per table):")
# 1st verifier for each table writes BP3, 2nd reads
w_cost = T * B5_WRITE / 1e6
r_cost = T * B_READ / 1e6
uncached_cost = T * B_INPUT / 1e6
print(f"    1st verifier: {T:.0f} tok written at $0.625/MTok = ${w_cost:.6f}")
print(f"    2nd verifier: {T:.0f} tok read at $0.05/MTok    = ${r_cost:.6f}")
print(f"    vs both uncached: 2 x ${uncached_cost:.6f}      = ${2*uncached_cost:.6f}")
pair_saving_5m = 2 * uncached_cost - (w_cost + r_cost)
print(f"    Saving per table: ${pair_saving_5m:.6f}")
print(f"    At {N:,} tables: ${pair_saving_5m * N:.2f}")
print()
print("  Synthesizer batch (cross-batch, depends on timing):")
print("    If cache still alive (batches < 5 min apart):")
synth_saving = uncached_cost - r_cost
print(f"      Read {T:.0f} tok: ${r_cost:.6f} vs ${uncached_cost:.6f} = ${synth_saving:.6f}/table")
print(f"      At {N:,} tables: ${synth_saving * N:.2f}")
total_5m = pair_saving_5m + synth_saving
print(f"    TOTAL BP3 savings (5-min): ${total_5m * N:.2f}")

print()

# --- 1-hour cache ---
print("1-HOUR CACHE with BP3:")
w_cost_1h = T * B1H_WRITE / 1e6
print(f"  1st verifier: {T:.0f} tok written at $1.00/MTok = ${w_cost_1h:.6f}")
print(f"  2nd verifier reads: ${r_cost:.6f}")
print(f"  Synthesizer reads (guaranteed): ${r_cost:.6f}")
print(f"  vs 3x uncached: ${3*uncached_cost:.6f}")
total_1h = 3 * uncached_cost - (w_cost_1h + 2 * r_cost)
print(f"  Net saving per table: ${total_1h:.6f}")
print(f"  At {N:,} tables: ${total_1h * N:.2f}")

print()
print("=" * 70)
print("BP4: ALSO CACHE VERIFIER RESULTS (for synthesizer)")
print("=" * 70)
print()
print(f"Synthesizer receives both verifier outputs = 2 x {V:.0f} = {2*V:.0f} tok")
print(f"Currently uncached: {2*V:.0f} x $0.50/MTok = ${2*V*B_INPUT/1e6:.6f}/table")
print()

# Each verifier writes its output with BP4.
# Synthesizer reads both. Cross-batch only (different batches).
print("5-MIN CACHE with BP4 (cross-batch, if alive):")
bp4_w = 2 * V * B5_WRITE / 1e6  # both verifiers write
bp4_r = 2 * V * B_READ / 1e6    # synthesizer reads both
bp4_uncached = 2 * V * B_INPUT / 1e6
# Verifiers pay write cost regardless (they're new content in their batch)
# But the EXTRA cost is write_rate - input_rate (they'd have been uncached input otherwise)
bp4_write_extra = 2 * V * (B5_WRITE - B_INPUT) / 1e6
bp4_read_saving = 2 * V * (B_INPUT - B_READ) / 1e6
bp4_net_5m = bp4_read_saving - bp4_write_extra
print(f"  Verifier write penalty: ${bp4_write_extra:.6f}/table")
print(f"  Synthesizer read saving: ${bp4_read_saving:.6f}/table")
print(f"  Net: ${bp4_net_5m:.6f}/table")
print(f"  At {N:,} tables: ${bp4_net_5m * N:.2f}")

print()
print("1-HOUR CACHE with BP4 (guaranteed cross-batch):")
bp4_write_extra_1h = 2 * V * (B1H_WRITE - B_INPUT) / 1e6
bp4_net_1h = bp4_read_saving - bp4_write_extra_1h
print(f"  Verifier write penalty: ${bp4_write_extra_1h:.6f}/table")
print(f"  Synthesizer read saving: ${bp4_read_saving:.6f}/table")
print(f"  Net: ${bp4_net_1h:.6f}/table")
print(f"  At {N:,} tables: ${bp4_net_1h * N:.2f}")

print()
print("=" * 70)
print("COMBINED SUMMARY (at 2,480 tables)")
print("=" * 70)
print()
print(f"{'Optimization':<35} {'5-min':>10} {'1-hour':>10}")
print("-" * 55)
print(f"{'1h TTL (from earlier analysis)':<35} {'N/A':>10} {'$5.60':>10}")
bp3_5m = total_5m * N
bp3_1h = total_1h * N
bp4_5m_total = bp4_net_5m * N
bp4_1h_total = bp4_net_1h * N
print(f"{'+ BP3 (transcriber results)':<35} ${bp3_5m:>9.2f} ${bp3_1h:>9.2f}")
print(f"{'+ BP4 (verifier results)':<35} ${bp4_5m_total:>9.2f} ${bp4_1h_total:>9.2f}")
print(f"{'BP3+BP4 combined':<35} ${bp3_5m + bp4_5m_total:>9.2f} ${bp3_1h + bp4_1h_total:>9.2f}")
print(f"{'Total (TTL + BP3 + BP4)':<35} {'':>10} ${5.60 + bp3_1h + bp4_1h_total:>9.2f}")
