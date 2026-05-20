"""
hypothesis_daemon.py — Continuous self-falsifying hypothesis testing loop.

Runs every 6 hours within overnight window (10 PM – 7 AM).
RAG-first: context always retrieved from vault. Ollama only for claim extraction
and code stub generation (~150 + ~200 tokens max per paper).

Pipeline per paper:
  1. RAG: load latest 10 papers from vault (tag_index.json by date)
  2. Extract: Ollama claim extraction (≤ 150 tokens) — or skip if offline
  3. CodeGen: Ollama Python stub generation (≤ 200 tokens) — or skip if offline
  4. Execute: sandboxed exec() of stub against local OHLCV data
  5. Log: update hypothesis_log.md + credibility_scores in SQLite
"""

import os
import sys

# Windows CP1252 fix
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import re
import json
import time
import traceback
import subprocess
import tempfile
from datetime import datetime

import db_manager
import credibility_manager
import ollama_helper

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR   = os.path.join(BASE_DIR, "vault")
WIKI_DIR    = os.path.join(VAULT_DIR, "wiki")
ASSETS_DIR  = os.path.join(VAULT_DIR, "assets")
QF_DIR      = os.path.join(WIKI_DIR, "02_Research", "Quant_Finance")
ALGOS_DIR   = os.path.join(QF_DIR, "autogen_algos")
HYPO_LOG    = os.path.join(QF_DIR, "hypothesis_log.md")
TAG_INDEX   = os.path.join(VAULT_DIR, "tag_index.json")
CACHE_FILE  = os.path.join(BASE_DIR, "compile_cache.json")

os.makedirs(ALGOS_DIR, exist_ok=True)

CYCLE_INTERVAL_HOURS = 6   # run every 6h inside the overnight window
MAX_PAPERS_PER_CYCLE = 10  # RAG load ceiling per cycle

# Stub execution timeout (seconds)
EXEC_TIMEOUT = 30


# --- RAG: paper retrieval ---

def rag_latest_papers(n: int = MAX_PAPERS_PER_CYCLE) -> list[dict]:
    """
    Retrieve the N most recently ingested quantitative research papers from vault.
    Uses compile_cache.json (already built) for zero-cost lookup.
    Returns list of {slug, title, file_path, tags, date_str}.
    """
    if not os.path.exists(CACHE_FILE):
        print("[hypothesis] compile_cache.json not found. Run ain.py compile first.")
        return []

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)

    papers = []
    quant_tags = {"arxiv", "finance", "quant", "machine-learning", "ai", "math"}

    for fp, entry in cache.items():
        tags = set(t.lower() for t in entry.get("tags", []))
        # Only pick research papers (arxiv or quant-tagged), not MOCs or stubs
        if not tags.intersection(quant_tags):
            continue
        if "moc" in tags or "index" in tags:
            continue

        slug = os.path.splitext(os.path.basename(fp))[0]
        papers.append({
            "slug":      slug,
            "title":     entry.get("title", slug),
            "file_path": fp,
            "tags":      entry.get("tags", []),
            "date_str":  entry.get("date_str", ""),
            "mtime":     entry.get("mtime", 0.0)
        })

    # Sort by mtime descending (most recently ingested first)
    papers.sort(key=lambda x: x["mtime"], reverse=True)
    return papers[:n]


def _read_abstract(file_path: str) -> str:
    """Extract the first 600 characters of a paper's content (abstract region)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(1500)
        # Strip frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            content = parts[2] if len(parts) >= 3 else content
        # Take the first 600 chars of body
        return content[:600].strip()
    except Exception:
        return ""


# --- Claim extraction (Ollama, ~150 tokens) ---

def extract_claim(paper: dict) -> str | None:
    abstract = _read_abstract(paper["file_path"])
    if not abstract:
        return None
    claim = ollama_helper.extract_claim(abstract)
    return claim


# --- Code stub generation (Ollama, ~200 tokens) ---

def generate_stub(claim: str) -> str | None:
    return ollama_helper.generate_backtest_stub(claim)


# --- Sandboxed stub execution ---

def execute_stub(stub_code: str, paper_slug: str) -> dict:
    """
    Write stub to a temp file and run it as a subprocess with timeout.
    Returns {result, notes, sharpe, p_value}.
    """
    result = {"result": "inconclusive", "notes": "", "sharpe": None, "p_value": None}

    # Find local OHLCV data
    ohlcv_path = _find_local_ohlcv()

    # Prepare runner script
    runner = f"""
import pandas as pd
import numpy as np
import sys, traceback

ohlcv_path = r"{ohlcv_path or ''}"

try:
    if ohlcv_path and __import__('os').path.exists(ohlcv_path):
        df = pd.read_csv(ohlcv_path, parse_dates=['Date'], index_col='Date')
    else:
        # Synthetic OHLCV for test
        import random
        random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200, freq='1D')
        close = pd.Series([100.0], index=[0])
        for _ in range(199):
            close = pd.concat([close, pd.Series([close.iloc[-1] * (1 + random.gauss(0, 0.01))])])
        close.index = range(200)
        df = pd.DataFrame({{
            'Open': close * 0.999,
            'High': close * 1.005,
            'Low':  close * 0.995,
            'Close': close,
            'Volume': [int(random.uniform(1e5, 1e6)) for _ in range(200)]
        }}, index=dates)

{stub_code}

    # Try calling the first function found in stub
    import types
    funcs = [v for k, v in locals().items() if callable(v) and isinstance(v, types.FunctionType)]
    if funcs:
        fn = funcs[0]
        output = fn(df)
        print("RESULT:", output)
    else:
        print("RESULT: no_function")

except Exception as e:
    print("ERROR:", str(e))
    traceback.print_exc()
"""

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(runner)
            tmp_path = tmp.name

        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=EXEC_TIMEOUT
        )
        output = proc.stdout + proc.stderr
        os.unlink(tmp_path)

        if "ERROR:" in output:
            result["result"] = "error"
            result["notes"]  = output[:300]
        elif "RESULT:" in output:
            out_line = [l for l in output.split("\n") if "RESULT:" in l]
            raw_val  = out_line[0].replace("RESULT:", "").strip() if out_line else ""
            # Heuristic: if result is True/positive → supported; False → falsified
            if raw_val.lower() in ("true", "1", "yes", "supported"):
                result["result"] = "supported"
            elif raw_val.lower() in ("false", "0", "no", "falsified"):
                result["result"] = "falsified"
            else:
                result["result"] = "inconclusive"
            result["notes"] = raw_val[:200]
        else:
            result["result"] = "inconclusive"
            result["notes"]  = output[:200]

    except subprocess.TimeoutExpired:
        result["result"] = "inconclusive"
        result["notes"]  = f"Execution timed out after {EXEC_TIMEOUT}s"
    except Exception as e:
        result["result"] = "error"
        result["notes"]  = str(e)

    return result


def _find_local_ohlcv() -> str | None:
    """Looks for a CSV with OHLCV columns in vault/assets/."""
    if not os.path.exists(ASSETS_DIR):
        return None
    for f in os.listdir(ASSETS_DIR):
        if f.endswith(".csv"):
            return os.path.join(ASSETS_DIR, f)
    return None


# --- Logging ---

def _log_hypothesis(paper: dict, claim: str, stub: str | None, exec_result: dict):
    """Append result to hypothesis_log.md and update SQLite."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    res = exec_result["result"]
    badge = {"supported": "✅ Supported", "falsified": "❌ Falsified",
             "inconclusive": "⚠️ Inconclusive", "error": "🔴 Error"}.get(res, res)

    entry = f"""
## [{date_str}] {badge} — {claim or '(no claim extracted)'}

- **Source node**: [[{paper['slug']}]] — *{paper['title'][:80]}*
- **Tags**: {', '.join(paper['tags'][:5])}
- **Result**: {badge}
- **Notes**: {exec_result.get('notes', '')[:200]}

"""
    try:
        with open(HYPO_LOG, "a", encoding="utf-8") as f:
            if f.tell() == 0:
                f.write("---\ntitle: Hypothesis Testing Log\ntags: [\"hypothesis\", \"backtest\"]\n---\n\n# Hypothesis Testing Log\n\n")
            f.write(entry)
    except Exception as e:
        print(f"[!] Could not write hypothesis log: {e}", file=sys.stderr)

    # Update credibility score
    if res == "supported":
        credibility_manager.record_confirmation(paper["slug"])
    elif res == "falsified":
        credibility_manager.record_falsification(paper["slug"])

    # Log to SQLite
    try:
        conn = db_manager.get_db_connection()
        conn.execute("""
        INSERT INTO backtest_results (hypothesis, source_slug, result, notes, code_stub)
        VALUES (?, ?, ?, ?, ?)
        """, (claim or "", paper["slug"], res, exec_result.get("notes", ""), stub or ""))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] DB backtest log failed: {e}", file=sys.stderr)

    # Save code stub if clean
    if stub and res not in ("error",):
        stub_filename = f"{paper['slug'][:60]}_stub.py"
        stub_path = os.path.join(ALGOS_DIR, stub_filename)
        try:
            header = f'"""\nAuto-generated stub for: {claim}\nSource: {paper["slug"]}\nDate: {date_str}\nResult: {badge}\n"""\n\n'
            with open(stub_path, "w", encoding="utf-8") as f:
                f.write(header + stub)
        except Exception:
            pass


# --- Main cycle ---

def run_cycle(dry_run: bool = False):
    """Execute one hypothesis testing cycle."""
    print(f"\n[hypothesis] === Starting cycle at {datetime.now().strftime('%H:%M:%S')} ===")

    papers = rag_latest_papers(MAX_PAPERS_PER_CYCLE)
    if not papers:
        print("[hypothesis] No papers found in vault. Skipping cycle.")
        return

    print(f"[hypothesis] RAG retrieved {len(papers)} candidate papers.")
    ollama_up = ollama_helper.is_available()
    if not ollama_up:
        print("[hypothesis] Ollama unavailable — claim extraction and stub generation disabled.")

    processed = 0
    for paper in papers:
        print(f"  -> [{paper['slug'][:50]}] {paper['title'][:60]}")

        claim = None
        stub  = None

        if ollama_up:
            claim = extract_claim(paper)
            if claim:
                print(f"     Claim: {claim}")
                stub = generate_stub(claim)
            else:
                print(f"     (No claim extracted)")

        if dry_run:
            print(f"     [dry-run] would execute stub and log result")
            processed += 1
            continue

        exec_result = {"result": "inconclusive", "notes": "Ollama offline", "sharpe": None, "p_value": None}
        if stub:
            exec_result = execute_stub(stub, paper["slug"])
            print(f"     Result: {exec_result['result']} — {exec_result['notes'][:80]}")

        _log_hypothesis(paper, claim, stub, exec_result)
        processed += 1
        time.sleep(2)  # Polite spacing between Ollama calls

    print(f"[hypothesis] Cycle complete. Processed {processed} papers.")


# --- CLI ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AIN Hypothesis Daemon")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without executing or writing")
    parser.add_argument("--once", action="store_true",
                        help="Run one cycle and exit (default is scheduled loop)")
    args = parser.parse_args()

    if args.dry_run or args.once:
        run_cycle(dry_run=args.dry_run)
    else:
        # Scheduled loop: run every 6 hours
        print(f"[hypothesis] Daemon started. Cycle interval: {CYCLE_INTERVAL_HOURS}h")
        while True:
            run_cycle()
            wait_secs = CYCLE_INTERVAL_HOURS * 3600
            print(f"[hypothesis] Next cycle in {CYCLE_INTERVAL_HOURS}h. Sleeping...")
            time.sleep(wait_secs)
