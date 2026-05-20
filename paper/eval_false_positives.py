"""
eval_false_positives.py
───────────────────────
Evaluation script for AIN contradiction detector.

Injects a controlled set of known-true consistent pairs and known-false
contradictory pairs into the NeuroSymbolic engine, then measures:
  - Precision (of flagged contradictions)
  - Recall (fraction of real contradictions caught)
  - F1 Score
  - Latency per rule addition

Usage:
    python paper/eval_false_positives.py

Output:
    paper/eval_results.json   — machine-readable results
    paper/eval_results.csv    — human-readable table (paste into paper)
"""
import sys, os, time, json, csv
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agi_core.neuro_symbolic import NeuroSymbolicEngine

# ─────────────────────────────────────────────────────────────────────────────
# Ground Truth Dataset
# Format: (subject, relation, object, label)
#   label = "consistent"  → the pair should NOT produce UNSAT
#   label = "contradicts" → adding this rule SHOULD produce UNSAT
# ─────────────────────────────────────────────────────────────────────────────
GROUND_TRUTH = [
    # --- Consistent pairs (True Negatives expected) ---
    ("InterestRateHike",    "causes",              "ReducedBorrowing",    "consistent"),
    ("ReducedBorrowing",    "prevents",            "CreditExpansion",     "consistent"),
    ("HighSavingsRate",     "implies",             "ReducedConsumption",  "consistent"),
    ("ReducedConsumption",  "causes",              "LowerGDPGrowth",      "consistent"),
    ("TrainingData",        "requires",            "ModelAccuracy",       "consistent"),
    ("ModelAccuracy",       "causes",              "LowerLoss",           "consistent"),
    ("HighEntropy",         "causes",              "InformationGain",     "consistent"),
    ("Regularization",      "prevents",            "Overfitting",         "consistent"),
    ("Diversification",     "reduces",             "PortfolioRisk",       "consistent"),
    ("LiquidityTrap",       "prevents",            "MonetaryPolicyEffect","consistent"),

    # --- Contradictory pairs (True Positives expected — should trigger UNSAT) ---
    ("InterestRateHike",    "causes",              "CreditExpansion",     "contradicts"),  # contradicts rule 1+2
    ("HighSavingsRate",     "causes",              "IncreasedConsumption","contradicts"),  # contradicts rule 3+4
    ("Regularization",      "causes",              "Overfitting",         "contradicts"),  # contradicts rule 8
    ("Diversification",     "causes",              "PortfolioRisk",       "contradicts"),  # contradicts rule 9
    ("MonetaryExpansion",   "mutually exclusive",  "MonetaryExpansion",   "contradicts"),  # self-contradiction
]

# ─────────────────────────────────────────────────────────────────────────────
# Run Evaluation
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 65)
print("AIN CONTRADICTION DETECTOR — PRECISION / RECALL EVALUATION")
print("=" * 65)

engine = NeuroSymbolicEngine()

# Phase 1: Load all consistent rules as ground truth world model
print("\n[Phase 1] Loading consistent world-model rules...")
consistent_rules = [(s, r, o) for s, r, o, l in GROUND_TRUTH if l == "consistent"]
for subj, rel, obj in consistent_rules:
    engine.add_rule(subj, rel, obj)

is_sat, msg = engine.check_consistency()
print(f"[Base] Universe after consistent rules: {msg}")
assert is_sat, "CRITICAL: Consistent rules produced UNSAT. Engine is broken."

# Phase 2: Inject contradictory rules one at a time and measure detection
print("\n[Phase 2] Injecting contradictory rules and measuring detection...")
contradictory_rules = [(s, r, o) for s, r, o, l in GROUND_TRUTH if l == "contradicts"]

results = []
true_positives  = 0
false_negatives = 0

for subj, rel, obj in contradictory_rules:
    # Create fresh engine with consistent base each time
    test_engine = NeuroSymbolicEngine()
    for cs, cr, co in consistent_rules:
        test_engine.add_rule(cs, cr, co)
    
    # Assert the root trigger
    trigger_var = test_engine._get_var(subj)
    test_engine.solver.add(trigger_var == True)
    
    t0 = time.perf_counter()
    test_engine.add_rule(subj, rel, obj)
    is_sat_after, state = test_engine.check_consistency()
    latency_ms = (time.perf_counter() - t0) * 1000
    
    detected = not is_sat_after  # engine says UNSAT → contradiction detected
    
    status = "TP" if detected else "FN"
    if detected:
        true_positives += 1
    else:
        false_negatives += 1
    
    result = {
        "rule": f"{subj} —{rel}→ {obj}",
        "expected": "contradiction",
        "detected": detected,
        "z3_state": state,
        "status": status,
        "latency_ms": round(latency_ms, 3)
    }
    results.append(result)
    print(f"  [{status}] '{subj} {rel} {obj}' | Z3: {state} | {latency_ms:.2f}ms")

# Phase 3: Check false positives (consistent rules wrongly flagged)
print("\n[Phase 3] Checking false positive rate on consistent rules...")
false_positives  = 0
true_negatives   = 0

clean_engine = NeuroSymbolicEngine()
for i, (subj, rel, obj) in enumerate(consistent_rules):
    clean_engine.add_rule(subj, rel, obj)
    is_sat_after, state = clean_engine.check_consistency()
    fp = not is_sat_after
    
    status = "FP" if fp else "TN"
    if fp:
        false_positives += 1
    else:
        true_negatives += 1
    
    result = {
        "rule": f"{subj} —{rel}→ {obj}",
        "expected": "consistent",
        "detected_contradiction": fp,
        "z3_state": state,
        "status": status,
    }
    results.append(result)
    if fp:
        print(f"  [FP!] '{subj} {rel} {obj}' wrongly flagged as contradiction!")
    else:
        print(f"  [TN]  '{subj} {rel} {obj}' correctly passed.")

# ─────────────────────────────────────────────────────────────────────────────
# Compute Metrics
# ─────────────────────────────────────────────────────────────────────────────
precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
recall    = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

print("\n" + "=" * 65)
print("RESULTS SUMMARY")
print("=" * 65)
print(f"  True Positives  (contradictions caught): {true_positives}")
print(f"  False Negatives (contradictions missed): {false_negatives}")
print(f"  True Negatives  (consistent, correct):  {true_negatives}")
print(f"  False Positives (consistent, wrong flag):{false_positives}")
print(f"  Precision: {precision:.3f}")
print(f"  Recall:    {recall:.3f}")
print(f"  F1 Score:  {f1:.3f}")

summary = {
    "true_positives": true_positives,
    "false_negatives": false_negatives,
    "true_negatives": true_negatives,
    "false_positives": false_positives,
    "precision": round(precision, 4),
    "recall": round(recall, 4),
    "f1": round(f1, 4),
    "detail": results
}

out_json = os.path.join(os.path.dirname(__file__), "eval_results.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)
print(f"\n[+] Saved: {out_json}")

out_csv = os.path.join(os.path.dirname(__file__), "eval_results.csv")
with open(out_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["rule", "expected", "status", "latency_ms"])
    writer.writeheader()
    for r in results:
        writer.writerow({
            "rule": r.get("rule", ""),
            "expected": r.get("expected", ""),
            "status": r.get("status", ""),
            "latency_ms": r.get("latency_ms", "N/A")
        })
print(f"[+] Saved: {out_csv}")
print("\nDone.")
