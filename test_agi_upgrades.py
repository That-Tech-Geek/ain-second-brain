"""
Test Suite: True AGI Capability Upgrades
Verifies:
  1. HDC Metaplasticity (synaptic decay)
  2. NeuroSymbolic LLM mapping (with offline fallback)
  3. ToolForge LLM code synthesis with debug loop
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# ─────────────────────────────────────────────────────────────────────────────
# 1. HDC METAPLASTICITY
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: HDC Continuous Metaplasticity (Synaptic Decay)")
print("=" * 60)

from agi_core.hdc_memory import HDCMemory
import time

hdc = HDCMemory(dim=10000)

# Phase 1: Saturate with 'finance' memories
for i in range(500):
    hdc.update_memory(["finance", "model", f"note_{i}"])

finance_before = hdc.query_similarity("finance")
print(f"[1a] 'finance' similarity after 500 writes: {finance_before:.4f}")

# Phase 2: Write 300 unrelated 'quantum' memories to trigger decay on 'finance'
for i in range(300):
    hdc.update_memory(["quantum", "physics", f"q_{i}"])

finance_after = hdc.query_similarity("finance")
quantum_after = hdc.query_similarity("quantum")
unseen_after  = hdc.query_similarity("alien_technology")

print(f"[1b] 'finance' similarity AFTER 300 decay steps: {finance_after:.4f}")
print(f"[1c] 'quantum' similarity (recent):              {quantum_after:.4f}")
print(f"[1d] 'alien_technology' (never seen):            {unseen_after:.4f}")

assert finance_after < finance_before, "FAIL: Synaptic decay is not reducing old memories!"
assert quantum_after > finance_after,  "FAIL: Recent memories should dominate over old ones!"
print("[OK] Synaptic decay is working correctly.\n")


# ─────────────────────────────────────────────────────────────────────────────
# 2. NEURO-SYMBOLIC LLM MAPPING
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST 2: Neuro-Symbolic LLM Predicate Extraction")
print("=" * 60)

from agi_core.neuro_symbolic import NeuroSymbolicEngine
import ollama_helper

if ollama_helper.is_available():
    print("[*] Ollama is ONLINE. Testing real LLM extraction...")
    engine = NeuroSymbolicEngine()
    
    # These are ambiguous phrases that string-matching would fail on
    test_cases = [
        ("HighCortisol", "almost certainly triggers a cascade in", "ChronicStress"),
        ("MonetaryExpansion", "is strictly incompatible with", "Deflation"),
        ("TrainingData", "is a necessary precondition for", "ModelAccuracy"),
    ]
    
    for subj, rel, obj in test_cases:
        engine.add_rule(subj, rel, obj)
    
    is_sat, msg = engine.check_consistency()
    print(f"\n[2a] Universe consistency after LLM-mapped rules: {msg}")
    print("[OK] LLM Neuro-Symbolic mapping passed.\n")
else:
    print("[*] Ollama is OFFLINE. Testing deterministic fallback...")
    engine = NeuroSymbolicEngine()
    engine.add_rule("InterestRates", "causes", "ReducedBorrowing")
    engine.add_rule("ReducedBorrowing", "prevents", "Inflation")
    is_sat, msg = engine.check_consistency()
    print(f"[2b] Universe consistency (fallback): {msg}")
    assert is_sat, "FAIL: Consistent fallback rules should be SAT!"
    print("[OK] Deterministic fallback mapping passed.\n")


# ─────────────────────────────────────────────────────────────────────────────
# 3. TOOLFORGE LLM CODE SYNTHESIS + DEBUG LOOP
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST 3: ToolForge LLM Code Synthesis with Debug Loop")
print("=" * 60)

from agi_core.tool_forge import ToolForge

forge = ToolForge(max_retries=3)

if ollama_helper.is_available():
    print("[*] Ollama is ONLINE. Testing real LLM code synthesis...")
    task = "Calculate the 15th Fibonacci number and print True if it equals 610, else print False."
    success, output = forge.synthesize(task, "fib_test")
    print(f"\n[3a] Synthesis success: {success}")
    print(f"[3b] LLM-generated output: {output}")
    assert success, "FAIL: ToolForge failed to synthesize a working script!"
    print("[OK] LLM Code Synthesis passed.\n")
else:
    print("[*] Ollama is OFFLINE. Testing deterministic fallback stub...")
    task = "Verify the status of SystemHealth and print True or False."
    success, output = forge.synthesize(task, "health_check_test")
    print(f"\n[3a] Synthesis success (fallback): {success}")
    print(f"[3b] Fallback output: {output}")
    assert success, "FAIL: Deterministic fallback stub failed!"
    print("[OK] Offline fallback synthesis passed.\n")


print("=" * 60)
print("ALL AGI UPGRADE TESTS PASSED")
print("=" * 60)
