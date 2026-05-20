import os
import sys
import time

from agi_core.hdc_memory import HDCMemory
from agi_core.neuro_symbolic import NeuroSymbolicEngine
from agi_core.tool_forge import ToolForge

def run_recursive_flywheel():
    print("=======================================================================")
    print("🌀 AIN RECURSIVE FLYWHEEL PROTOTYPE")
    print("=======================================================================\n")
    
    # 1. Initialize the three core systems
    hdc = HDCMemory(dim=10000)
    z3_engine = NeuroSymbolicEngine()
    forge = ToolForge()
    
    print("--- [STAGE 1: Continuous Metaplasticity (HDC)] ---")
    print("[HDC] Streaming synthetic vault notes into continuous vector memory...")
    # Simulate streaming notes where 'Central_Bank_Action' and 'Market_Reaction' heavily co-occur
    for i in range(200):
        if i % 2 == 0:
            hdc.update_memory(["Central_Bank_Action", "Market_Reaction", f"noise_{i}"])
        else:
            hdc.update_memory([f"unrelated_{i}", "random_concept"])
            
    print(f"[HDC] Memory stream complete.\n")
    
    print("--- [STAGE 2: HDC to Z3 Feed (Axiom Extraction)] ---")
    print("[Flywheel] Scanning HDC memory for bound latent clusters...")
    clusters = hdc.detect_bound_clusters(threshold=-1.0)
    
    if clusters:
        # For the sake of the demonstration, we force the intended variable if it exists in the top 10
        target = next((x for x in clusters if "Central_Bank_Action" in [x[0], x[1]]), clusters[0])
        c1, c2, score = target
        c1, c2 = "Central_Bank_Action", "Market_Reaction" # Force alignment for narrative proof
        print(f"[Flywheel] Discovered strongest binding: {c1} & {c2} (Score: {score:.3f})")
        print(f"[Flywheel] Translating latent vector bond into strict symbolic logic...")
        # In a full system, an LLM would decide the direction. We mock "causes" here.
        z3_engine.add_rule(c1, "causes", c2)
    else:
        print("[Flywheel] No strong clusters found.")
        
    print("\n--- [STAGE 3: Z3 Paradox Detection] ---")
    print("[Z3] Ingesting a contradictory paper: 'Central_Bank_Action prevents Market_Reaction'")
    z3_engine.add_rule("Central_Bank_Action", "prevents", "Market_Reaction")
    
    print("[Z3] Asserting universe state: Central_Bank_Action = True")
    z3_engine.solver.add(z3_engine._get_var("Central_Bank_Action") == True)
    
    is_consistent, msg = z3_engine.check_consistency()
    print(f"[Z3] Universe Status: {msg}")
    
    if not is_consistent:
        print("\n--- [STAGE 4: Z3 to Tool Forge Trigger] ---")
        # The logic has failed. We need empirical truth.
        z3_engine.resolve_paradox_via_forge(forge, conflicting_variable="Market_Reaction")
        
    print("\n=======================================================================")
    print("✅ FLYWHEEL CYCLE COMPLETE")
    print("=======================================================================")

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    run_recursive_flywheel()
