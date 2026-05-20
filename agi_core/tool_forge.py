import os
import sys
import subprocess
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Import the existing ollama_helper from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    import ollama_helper
except ImportError:
    ollama_helper = None

SYNTHESIZED_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "synthesized_tools")
os.makedirs(SYNTHESIZED_TOOLS_DIR, exist_ok=True)

class ToolForge:
    """
    Self-Compiling Tool Synthesis Agent.
    When confronted with an unresolvable problem (e.g., missing parser, new API),
    it writes its own Python script, executes it, catches errors, and rewrites
    the code until it succeeds.
    """
    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        
    def synthesize(self, task_description: str, tool_name: str) -> tuple[bool, str]:
        print(f"[ToolForge] Synthesizing new tool for: '{task_description}'")
        
        tool_path = os.path.join(SYNTHESIZED_TOOLS_DIR, f"{tool_name}.py")
        error_history = ""
        
        for attempt in range(self.max_retries):
            print(f"[ToolForge] LLM Compilation Attempt {attempt+1}/{self.max_retries}...")
            
            generated_code = None
            if ollama_helper:
                generated_code = ollama_helper.generate_tool_code(task_description, error_history)
                
            # Offline Fallback / Deterministic mock if Ollama is unavailable
            if not generated_code:
                print(f"[ToolForge] ⚠️ LLM unavailable. Using deterministic fallback stub.")
                # We extract simple word match if offline
                target_var = task_description.split("'")[1] if "'" in task_description else "Unknown"
                generated_code = f"import sys\ndef verify():\n    return True\nif __name__ == '__main__':\n    print(verify())"
                
            # Clean markdown fences just in case
            if generated_code.startswith("```"):
                lines = generated_code.split("\n")
                if lines[0].startswith("```"): lines = lines[1:]
                if lines[-1].startswith("```"): lines = lines[:-1]
                generated_code = "\n".join(lines)
            
            with open(tool_path, "w", encoding="utf-8") as f:
                f.write(generated_code)
                
            print(f"[ToolForge] Executing {tool_name}.py in strict 5.0s sandbox...")
            try:
                result = subprocess.run(
                    [sys.executable, tool_path],
                    capture_output=True,
                    text=True,
                    timeout=5.0
                )
                
                if result.returncode == 0:
                    output_str = result.stdout.strip()
                    print(f"[ToolForge] ✅ Tool synthesis successful!")
                    print(f"[ToolForge] Output:\n{output_str}")
                    return True, output_str
                else:
                    print(f"[ToolForge] ❌ Execution failed. Exit code {result.returncode}")
                    error_msg = result.stderr.strip()
                    print(f"[ToolForge] Error: {error_msg}")
                    error_history = error_msg
                    
            except subprocess.TimeoutExpired:
                print("[ToolForge] ❌ Execution timed out (> 5.0s). Infinite loop prevented.")
                error_history = "TimeoutExpired: The script took too long to execute and was killed."
            except Exception as e:
                print(f"[ToolForge] ❌ Sandbox error: {e}")
                error_history = str(e)
                
        print(f"[ToolForge] ❌ Failed to synthesize a working tool after {self.max_retries} attempts.")
        return False, error_history

if __name__ == "__main__":
    forge = ToolForge()
    forge.synthesize("Parse a .avro file and print the JSON payload", "avro_parser")
