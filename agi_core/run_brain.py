import sys
import time
from agi_core.self_recourse_brain import SelfRecourseBrain

def launch_living_brain():
    print("="*70)
    print("🧠 ACTIVATING AUTONOMOUS SELF-RECOURSE AGI BRAIN")
    print("="*70)
    
    # Initialize the core brain system
    brain = SelfRecourseBrain()
    
    # Step 1: Establish consistent baseline world parameters
    print("\n--- Cycle 1: Building Baseline Knowledge ---")
    brain.assimilate_information("InjectCapital", "AssetInflation")
    time.sleep(1)
    
    # Step 2: Inject conflicting data stream to trigger instability
    print("\n--- Cycle 2: Processing Contradictory Input ---")
    print("[External Stream] Ingesting Paper: 'Capital injections prevent AssetInflation via structural offsets.'")
    brain.assimilate_information("InjectCapital", "AssetInflation", conflict_mode=True)
    time.sleep(1)
    
    # Step 3: Homeostatic monitoring check
    print("\n--- Cycle 3: Evaluating Homeostatic Integrity ---")
    if brain.epistemic_distress > 0.70:
        print("[Homeostasis] System is structurally unstable. Executing self-recourse routine.")
        # Identify the variable under pressure and repair it
        brain.execute_self_recourse(root_cause_variable="AssetInflation")
    else:
        print("[Homeostasis] Cognitive system remains stable. Continuing baseline monitoring loops.")
        
    print("\n" + "="*70)
    if brain.equilibrium_restored:
        print("✅ RECOURSE CYCLE SUCCESSFUL: Brain has restored inner equilibrium.")
    else:
        print("❌ RECOURSE CYCLE CRITICAL FAILURE: System is stuck in an unresolvable loop.")
    print("="*70)

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    launch_living_brain()
