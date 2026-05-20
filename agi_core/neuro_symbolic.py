import os
import sys
import z3

# Import ollama_helper
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    import ollama_helper
except ImportError:
    ollama_helper = None

class NeuroSymbolicEngine:
    def __init__(self):
        self.solver = z3.Solver()
        self.variables = {}
        
    def _get_var(self, name):
        """Get or create a boolean variable in Z3 representing a concept/state"""
        if name not in self.variables:
            self.variables[name] = z3.Bool(name)
        return self.variables[name]

    def add_rule(self, subj, relation, obj):
        """
        Translates a natural language relation into Z3 symbolic logic.
        Uses an LLM to accurately extract the formal predicate.
        """
        s_var = self._get_var(subj)
        o_var = self._get_var(obj)
        
        extracted_pred = None
        if ollama_helper:
            extracted_pred = ollama_helper.extract_logic_relation(relation)
            
        if extracted_pred:
            extracted_pred = extracted_pred.strip().upper()
        else:
            # Deterministic fallback if offline
            relation_lower = relation.lower().strip()
            if "cause" in relation_lower or "leads to" in relation_lower or "implies" in relation_lower:
                extracted_pred = "IMPLIES"
            elif "prevent" in relation_lower or "blocks" in relation_lower or "inhibits" in relation_lower:
                extracted_pred = "PREVENTS"
            elif "requires" in relation_lower:
                extracted_pred = "REQUIRES"
            elif "mutually exclusive" in relation_lower or "contradicts" in relation_lower:
                extracted_pred = "XOR"
            else:
                extracted_pred = "IMPLIES"
                
        # Apply the predicate to Z3
        if "IMPLIES" in extracted_pred or "REQUIRES" in extracted_pred:
            self.solver.add(z3.Implies(s_var, o_var))
            print(f"[NeuroSymbolic] Mapped '{relation}' -> IMPLIES: {subj} => {obj}")
        elif "PREVENTS" in extracted_pred:
            self.solver.add(z3.Implies(s_var, z3.Not(o_var)))
            print(f"[NeuroSymbolic] Mapped '{relation}' -> PREVENTS: {subj} => NOT {obj}")
        elif "XOR" in extracted_pred:
            self.solver.add(z3.Or(z3.Not(s_var), z3.Not(o_var)))
            print(f"[NeuroSymbolic] Mapped '{relation}' -> XOR: {subj} XOR {obj}")
        else:
            # Default fallback mapping
            self.solver.add(z3.Implies(s_var, o_var))
            print(f"[NeuroSymbolic] Unknown LLM Output '{extracted_pred}'. Defaulting to IMPLIES: {subj} => {obj}")
            
    def check_consistency(self, hypothesis_subj=None, hypothesis_obj=None):
        """
        Checks if the current knowledge base contains a mathematical contradiction.
        """
        # If we want to test a specific hypothesis, push a new context
        if hypothesis_subj and hypothesis_obj:
            self.solver.push()
            s_var = self._get_var(hypothesis_subj)
            o_var = self._get_var(hypothesis_obj)
            # Assert the hypothesis to see if it breaks the universe
            self.solver.add(z3.And(s_var, o_var))
            
        result = self.solver.check()
        
        if hypothesis_subj and hypothesis_obj:
            self.solver.pop()
            
        if result == z3.sat:
            return True, "Consistent"
        elif result == z3.unsat:
            return False, "Paradox / Contradiction Detected (UNSAT)"
        else:
            return False, "Unknown state"

    def resolve_paradox_via_forge(self, forge_instance, conflicting_variable: str):
        """
        [Flywheel] Bridges Symbolic Logic to Tool Synthesis.
        When Z3 hits an epistemic wall (UNSAT) involving a specific variable,
        it instructs the ToolForge to write a scraper/parser to fetch the 
        real-world ground truth for that variable.
        """
        print(f"\n[NeuroSymbolic] 🚨 PARADOX DETECTED involving '{conflicting_variable}'.")
        print(f"[NeuroSymbolic] Symbolic logic is insufficient. Triggering Tool Forge for empirical data...")
        
        task_desc = f"Fetch the current real-world status of '{conflicting_variable}' from a public API or website, and print True or False."
        tool_name = f"empirical_check_{conflicting_variable.lower()}"
        
        success, output_str = forge_instance.synthesize(task_desc, tool_name)
        if success:
            # Semantic Grounding: Actually parse the truth value
            truth_val = None
            if "true" in output_str.lower():
                truth_val = True
            elif "false" in output_str.lower():
                truth_val = False
                
            if truth_val is not None:
                print(f"[NeuroSymbolic] 🔧 Empirical resolution successful. Ground truth for '{conflicting_variable}' is {truth_val}.")
                print(f"[NeuroSymbolic] Pruning false axioms and injecting empirical truth into logic universe to collapse the paradox...")
                
                # To collapse the paradox, we must drop the rules that contradict reality.
                # For this prototype, we reset the solver and assert the absolute ground truth.
                self.solver.reset() 
                self.solver.add(self._get_var(conflicting_variable) == truth_val)
                
                # Re-check consistency to ensure it collapsed correctly
                is_consistent, msg = self.check_consistency()
                print(f"[NeuroSymbolic] Final Universe Status after grounding: {msg}")
                return True
            else:
                print(f"[NeuroSymbolic] ❌ Tool Forge succeeded but failed to return a boolean truth value. Output: {output_str}")
                return False
        else:
            print(f"[NeuroSymbolic] ❌ Tool Forge failed to resolve the paradox empirically.")
        return False

if __name__ == "__main__":
    print("--- Neuro-Symbolic Reconciliation Test ---")
    engine = NeuroSymbolicEngine()
    
    # Ingesting knowledge
    engine.add_rule("Interest_Rate_Hike", "causes", "Reduced_Borrowing")
    engine.add_rule("Reduced_Borrowing", "prevents", "Inflation_Spike")
    
    # Check universe consistency
    is_consistent, msg = engine.check_consistency()
    print(f"Base Universe Status: {msg}")
    
    # Suppose a new paper claims: "Interest_Rate_Hike causes Inflation_Spike"
    print("\n[!] Ingesting conflicting paper...")
    engine.add_rule("Interest_Rate_Hike", "causes", "Inflation_Spike")
    
    # To find a paradox, we assert the root cause (Interest_Rate_Hike = True)
    # If the root cause leads to a logical impossibility, the system is UNSAT.
    engine.solver.add(engine._get_var("Interest_Rate_Hike") == True)
    
    is_consistent, msg = engine.check_consistency()
    print(f"Updated Universe Status: {msg}")
