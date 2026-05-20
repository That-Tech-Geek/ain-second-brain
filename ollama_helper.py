"""
ollama_helper.py — Graceful, offline-safe Ollama interface.

Design: RAG-first. LLM generation is always optional. Every function
returns None when Ollama is unavailable so callers degrade gracefully.

Token budget per call: num_predict ≤ 200 (enforced here, not by callers).
Models: gemma3:1b (extraction/prose), deepseek-coder:1.3b (code gen).
"""

import os
import sys

# --- Configuration ---
EXTRACT_MODEL = os.environ.get("AIN_EXTRACT_MODEL", "gemma3:1b")
CODE_MODEL    = os.environ.get("AIN_CODE_MODEL",    "deepseek-coder:1.3b")
MAX_TOKENS    = 200   # Hard ceiling on all generation calls
TIMEOUT_SEC   = 30    # Per-call timeout

_client = None
_available = None  # None = untested, True/False = result cached


def _get_client():
    """Lazy-initialize and cache the Ollama client."""
    global _client
    if _client is None:
        try:
            import ollama
            _client = ollama.Client()
        except ImportError:
            pass
    return _client


def is_available() -> bool:
    """
    Returns True if the Ollama server is reachable.
    Result is cached after the first call.
    """
    global _available
    if _available is not None:
        return _available
    client = _get_client()
    if client is None:
        _available = False
        return False
    try:
        client.list()
        _available = True
    except Exception:
        _available = False
    return _available


def reset_availability_cache():
    """Call this if Ollama was started after process launch."""
    global _available
    _available = None


def _call(model: str, prompt: str, system: str = "", max_tokens: int = MAX_TOKENS) -> str | None:
    """
    Internal low-level call. Returns text or None on any failure.
    Enforces token ceiling via max_tokens.
    """
    if not is_available():
        return None
    client = _get_client()
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat(
            model=model,
            messages=messages,
            options={"num_predict": max_tokens, "temperature": 0.2}
        )
        return response.message.content.strip()
    except Exception as e:
        print(f"[!] Ollama call failed ({model}): {e}", file=sys.stderr)
        return None


# --- Public API ---

def extract_claim(abstract: str) -> str | None:
    """
    Extract ONE falsifiable scientific claim from a paper abstract.
    Returns a ≤ 20-word claim string, or None if Ollama unavailable.
    Token cost: ~150 per call.
    """
    prompt = (
        f"Extract ONE falsifiable empirical claim from this abstract. "
        f"Output ONLY the claim in ≤ 20 words. No preamble.\n\nAbstract:\n{abstract[:800]}"
    )
    return _call(EXTRACT_MODEL, prompt)


def suggest_resolution_experiment(title_a: str, title_b: str, excerpt_a: str, excerpt_b: str) -> str | None:
    """
    Given two conflicting node titles, suggest a 1-sentence resolution experiment.
    Token cost: ~100 per call.
    """
    prompt = (
        f"These two research claims conflict:\n"
        f"A: {title_a}\n"
        f"B: {title_b}\n"
        f"Suggest ONE specific experiment to resolve which is correct. ≤ 25 words. No preamble."
    )
    return _call(EXTRACT_MODEL, prompt)

def extract_logic_relation(text: str) -> str | None:
    """
    Given a natural language relation, map it to a strict Z3 logic predicate.
    Valid outputs: IMPLIES, PREVENTS, REQUIRES, XOR.
    """
    prompt = (
        f"Map the following relation to exactly one of these strict logical predicates: IMPLIES, PREVENTS, REQUIRES, XOR.\n"
        f"Relation text: '{text}'\n"
        f"Output ONLY the predicate word. No preamble."
    )
    return _call(EXTRACT_MODEL, prompt)


def generate_backtest_stub(claim: str) -> str | None:
    """
    Generate a minimal Python function stub to test a quantitative claim.
    Token cost: ~200 per call.
    """
    system = (
        "You are a quant developer. Output ONLY valid Python code. "
        "No markdown fences, no explanations."
    )
    prompt = (
        f"Write a Python function stub to empirically test this claim:\n"
        f"'{claim}'\n"
        f"Use: pandas, numpy, ta (ta-lib compatible). "
        f"Include docstring, args (df: pd.DataFrame), return bool result."
    )
    return _call(CODE_MODEL, prompt, system=system)

def generate_tool_code(task: str, error_msg: str = "") -> str | None:
    """
    Generate a standalone Python script to accomplish a specific task.
    Includes an error feedback loop for recursive debugging.
    Token cost: ~400 per call.
    """
    system = (
        "You are an autonomous Python tool-writing agent. Output ONLY valid Python code. "
        "No markdown fences, no explanations. The script MUST run independently and print either 'True' or 'False' to standard output as its final result."
    )
    prompt = f"Write a complete Python script to perform this task:\n'{task}'\n"
    if error_msg:
        prompt += f"\nYour previous attempt failed with this exact error trace:\n{error_msg}\n\nRewrite the script to fix this error."
        
    return _call(CODE_MODEL, prompt, system=system, max_tokens=400)


def suggest_replacement_features(failed_features: list[str]) -> str | None:
    """
    Given a list of underperforming features, suggest replacements.
    Token cost: ~100 per call.
    """
    feat_str = ", ".join(failed_features)
    prompt = (
        f"Features {feat_str} lost predictive power in a mean-reversion trading model. "
        f"Suggest 3 replacement technical indicators. "
        f"Format: name | formula in 1 line. No preamble."
    )
    return _call(EXTRACT_MODEL, prompt)


def summarize_delta(new_files: list[str], modified_files: list[str]) -> str | None:
    """
    Produce a 3-line summary of what changed in the vault since last reboot.
    Token cost: ~100 per call.
    """
    new_str  = "\n".join(new_files[:5])
    mod_str  = "\n".join(modified_files[:3])
    prompt   = (
        f"New research files added:\n{new_str}\n\n"
        f"Modified files:\n{mod_str}\n\n"
        f"Summarize the research activity in 3 bullet points. ≤ 60 words total."
    )
    return _call(EXTRACT_MODEL, prompt)


def speculate_memo(topic: str, excerpts: list[str], backtest_note: str = "") -> str | None:
    """
    Write a short hypothesis-driven memo connecting retrieved vault excerpts.
    Token cost: ~200 per call.
    """
    excerpts_str = "\n\n".join([f"[{i+1}] {e[:300]}" for i, e in enumerate(excerpts[:5])])
    conflict_note = f"\nNote: This may conflict with: {backtest_note}" if backtest_note else ""
    prompt = (
        f"Topic: {topic}\n\n"
        f"Vault findings:\n{excerpts_str}{conflict_note}\n\n"
        f"Write a 3-bullet hypothesis memo. Each bullet: one falsifiable claim. "
        f"Cite [1]-[5]. No preamble, no conclusion paragraph."
    )
    return _call(EXTRACT_MODEL, prompt)
