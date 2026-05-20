"""
eval_decay_curve.py
────────────────────
Generates the HDC metaplasticity decay curve data for Figure 1 in the paper.

Measures concept similarity at intervals of 50 memory updates,
for three δ values (0.90, 0.95, 0.99) to produce a sensitivity analysis.

Output:
  paper/decay_curve.json  — raw data for plotting
  paper/decay_curve.csv   — CSV for import into matplotlib / pgfplots
"""
import sys, os, json, csv
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from agi_core.hdc_memory import HDCMemory

OUT_JSON = os.path.join(os.path.dirname(__file__), "decay_curve.json")
OUT_CSV  = os.path.join(os.path.dirname(__file__), "decay_curve.csv")

DELTA_VALUES   = [0.90, 0.95, 0.99]
SATURATION_N   = 300        # writes of 'finance' to saturate
DECAY_N        = 500        # writes of 'quantum' to observe decay
SAMPLE_EVERY   = 25         # record similarity every N writes
DIM            = 10000

print("=" * 65)
print("HDC METAPLASTICITY DECAY CURVE — SENSITIVITY ANALYSIS")
print(f"δ values: {DELTA_VALUES}")
print(f"Saturation writes: {SATURATION_N} ('finance')")
print(f"Decay writes: {DECAY_N} ('quantum')")
print("=" * 65)

all_data = {}

for delta in DELTA_VALUES:
    print(f"\n[δ={delta}] Running simulation...")
    hdc = HDCMemory(dim=DIM)
    # Monkey-patch the decay factor
    original_update = hdc.update_memory
    def make_update(h, d):
        def patched_update(concepts, decay_factor=d):
            vecs = [h.encode(c) for c in concepts]
            doc_vector = h.bundle(vecs)
            h.global_state = (h.global_state * d) + doc_vector
        return patched_update
    hdc.update_memory = make_update(hdc, delta)
    
    curve = []
    
    # Phase 1: Saturate with 'finance'
    for i in range(SATURATION_N):
        hdc.update_memory(["finance", "model", f"note_{i}"])
    
    saturation_sim = hdc.query_similarity("finance")
    print(f"  Saturation similarity: {saturation_sim:.4f}")
    
    # Phase 2: Decay with 'quantum'
    for step in range(DECAY_N + 1):
        if step % SAMPLE_EVERY == 0:
            curve.append({
                "decay_step": step,
                "finance_sim": round(hdc.query_similarity("finance"), 5),
                "quantum_sim": round(hdc.query_similarity("quantum"), 5)
            })
            if step % 100 == 0:
                print(f"  Step {step:4d}: finance={hdc.query_similarity('finance'):.4f}  quantum={hdc.query_similarity('quantum'):.4f}")
        
        if step < DECAY_N:
            hdc.update_memory(["quantum", "physics", f"q_{step}"])
    
    all_data[str(delta)] = curve

# Save JSON
with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(all_data, f, indent=2)
print(f"\n[+] Saved: {OUT_JSON}")

# Save CSV (wide format: one row per step)
fieldnames = ["decay_step"] + [f"finance_sim_delta{d}" for d in DELTA_VALUES] + [f"quantum_sim_delta{d}" for d in DELTA_VALUES]
n_steps = len(all_data[str(DELTA_VALUES[0])])
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for i in range(n_steps):
        row = {"decay_step": all_data[str(DELTA_VALUES[0])][i]["decay_step"]}
        for d in DELTA_VALUES:
            entry = all_data[str(d)][i]
            row[f"finance_sim_delta{d}"] = entry["finance_sim"]
            row[f"quantum_sim_delta{d}"] = entry["quantum_sim"]
        writer.writerow(row)
print(f"[+] Saved: {OUT_CSV}")

# Print summary table for paper
print("\n── Summary Table (for paper) ──")
print(f"{'δ':>6}  {'Finance @ step 0':>18}  {'Finance @ step 250':>20}  {'Finance @ step 500':>20}")
for d in DELTA_VALUES:
    curve = all_data[str(d)]
    s0   = next(e for e in curve if e["decay_step"] == 0)["finance_sim"]
    s250 = next((e for e in curve if e["decay_step"] == 250), curve[-1])["finance_sim"]
    s500 = curve[-1]["finance_sim"]
    print(f"{d:>6}  {s0:>18.4f}  {s250:>20.4f}  {s500:>20.4f}")
print("\nDone.")
