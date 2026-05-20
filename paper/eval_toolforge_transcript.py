"""
eval_toolforge_transcript.py
─────────────────────────────
Generates a documented ToolForge debug session transcript for the paper.

Simulates:
  - Attempt 1: deliberately broken code (syntax error injected)
  - Attempt 2: LLM rewrites based on error feedback → success

If Ollama is available, uses real LLM generation.
If offline, uses a scripted two-attempt mock to demonstrate the loop structure.

Output:
  paper/toolforge_transcript.txt  — formatted for inclusion in paper appendix
"""
import sys, os, time, subprocess, textwrap
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ollama_helper

TRANSCRIPT_FILE = os.path.join(os.path.dirname(__file__), "toolforge_transcript.txt")
SYNTHESIZED_DIR = os.path.join(os.path.dirname(__file__), "..", "agi_core", "synthesized_tools")
os.makedirs(SYNTHESIZED_DIR, exist_ok=True)

TOOL_PATH = os.path.join(SYNTHESIZED_DIR, "fib_15_check.py")
TASK = "Calculate the 15th Fibonacci number (1-indexed, F(1)=1). Print True if the result equals 610, else print False."

lines = []
def log(msg=""):
    print(msg)
    lines.append(msg)

log("=" * 70)
log("TOOLFORGE SELF-COMPILING DEBUG SESSION TRANSCRIPT")
log("Task: " + TASK)
log("=" * 70)

ollama_online = ollama_helper.is_available()
log(f"\n[Environment] Ollama available: {ollama_online}")
log(f"[Environment] Code model: {ollama_helper.CODE_MODEL}")
log(f"[Environment] Max tokens: 400, Temperature: 0.2")

# ─────────────────────────────────────────────────────────────────────────────
# ATTEMPT 1
# ─────────────────────────────────────────────────────────────────────────────
log("\n" + "─" * 70)
log("ATTEMPT 1 / 3")
log("─" * 70)

t0 = time.perf_counter()
if ollama_online:
    code_attempt1 = ollama_helper.generate_tool_code(TASK, error_msg="")
    if not code_attempt1:
        code_attempt1 = None
else:
    code_attempt1 = None

if code_attempt1 is None:
    # Scripted mock: deliberately broken code
    code_attempt1 = textwrap.dedent("""\
        def fibonacci(n)
            if n <= 1:
                return n
            return fibonacci(n-1) + fibonacci(n-2)
        
        result = fibonacci(15)
        print(result == 610)
    """)
    log("[LLM] Offline — using scripted broken stub (missing colon on def line)")

gen_time1 = (time.perf_counter() - t0) * 1000
log(f"\n[Generated Code — {gen_time1:.0f}ms generation time]")
log("```python")
for ln in code_attempt1.strip().split("\n"):
    log("  " + ln)
log("```")

with open(TOOL_PATH, "w", encoding="utf-8") as f:
    f.write(code_attempt1)

t1 = time.perf_counter()
result1 = subprocess.run([sys.executable, TOOL_PATH],
    capture_output=True, text=True, timeout=5.0)
exec_time1 = (time.perf_counter() - t1) * 1000

log(f"\n[Execution — {exec_time1:.1f}ms]")
log(f"  Return code: {result1.returncode}")
if result1.stdout.strip():
    log(f"  stdout: {result1.stdout.strip()}")
if result1.stderr.strip():
    log(f"  stderr (captured for feedback loop):")
    for ln in result1.stderr.strip().split("\n"):
        log(f"    {ln}")

# ─────────────────────────────────────────────────────────────────────────────
# ATTEMPT 2  (only if attempt 1 failed)
# ─────────────────────────────────────────────────────────────────────────────
if result1.returncode != 0:
    error_history = result1.stderr.strip()
    
    log("\n" + "─" * 70)
    log("ATTEMPT 2 / 3  (error feedback injected into prompt)")
    log("─" * 70)
    log(f"[Feedback] Injecting stderr into next generation prompt...")
    
    t0 = time.perf_counter()
    if ollama_online:
        code_attempt2 = ollama_helper.generate_tool_code(TASK, error_msg=error_history)
    else:
        code_attempt2 = None

    if code_attempt2 is None:
        # Scripted mock: correct code
        code_attempt2 = textwrap.dedent("""\
            def fibonacci(n):
                if n <= 1:
                    return n
                return fibonacci(n-1) + fibonacci(n-2)
            
            result = fibonacci(15)
            print(result == 610)
        """)
        log("[LLM] Offline — using scripted corrected stub (colon added)")
    
    gen_time2 = (time.perf_counter() - t0) * 1000
    log(f"\n[Generated Code — {gen_time2:.0f}ms generation time]")
    log("```python")
    for ln in code_attempt2.strip().split("\n"):
        log("  " + ln)
    log("```")
    
    with open(TOOL_PATH, "w", encoding="utf-8") as f:
        f.write(code_attempt2)
    
    t1 = time.perf_counter()
    result2 = subprocess.run([sys.executable, TOOL_PATH],
        capture_output=True, text=True, timeout=5.0)
    exec_time2 = (time.perf_counter() - t1) * 1000
    
    log(f"\n[Execution — {exec_time2:.1f}ms]")
    log(f"  Return code: {result2.returncode}")
    log(f"  stdout: {result2.stdout.strip()}")
    
    if result2.returncode == 0:
        log("\n[✅ ToolForge SUCCESS on attempt 2]")
        log(f"[Result] Output: '{result2.stdout.strip()}' → Paradox resolution: {result2.stdout.strip().upper() == 'TRUE'}")
    else:
        log("\n[❌ Attempt 2 also failed — would proceed to attempt 3]")
else:
    log("\n[✅ ToolForge SUCCESS on attempt 1 — no debug loop required]")

log("\n" + "=" * 70)
log("END OF TRANSCRIPT")
log("=" * 70)

with open(TRANSCRIPT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"\n[+] Transcript saved: {TRANSCRIPT_FILE}")
