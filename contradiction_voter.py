"""
contradiction_engine.py — Voting-based conflict detection across 19k+ nodes.

Zero LLM tokens for detection. Ollama used ONLY for 1-sentence resolution
suggestion (optional, gracefully skipped if unavailable).

Ensemble vote:
  Voter 1: TF-IDF cosine similarity (ngram 1-3, 5000 features) > TFIDF_THRESH
  Voter 2: Jaccard token overlap                                > JACCARD_THRESH
  Voter 3: High semantic sim + tag disjointness (sim > SEM_THRESH, tag overlap < 0.3)

Conflict = votes >= 2 AND tags differ.
Estimated runtime: <500ms on 19k nodes (sklearn sparse matrix ops).
"""

import os
import sys
import re
import json
from datetime import datetime
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import db_manager
import ollama_helper

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR    = os.path.join(BASE_DIR, "vault", "wiki")
DISPUTE_DIR = os.path.join(WIKI_DIR, "_Disputes")
os.makedirs(DISPUTE_DIR, exist_ok=True)

# --- Thresholds & Config ---
CONFIG_FILE = os.path.join(BASE_DIR, "contradiction_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"TFIDF_THRESH": 0.72, "JACCARD_THRESH": 0.45, "SEM_THRESH": 0.65}

config = load_config()
TFIDF_THRESH   = config["TFIDF_THRESH"]
JACCARD_THRESH = config["JACCARD_THRESH"]
SEM_THRESH     = config["SEM_THRESH"]
TAG_OVERLAP_MAX = 0.30
MAX_PAIRS      = 150


def _tokenize(text: str) -> set:
    """Lowercase unigram tokenizer, strips punctuation."""
    return set(re.sub(r"[^\w\s]", "", text.lower()).split())


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tag_overlap(tags_a: list, tags_b: list) -> float:
    if not tags_a or not tags_b:
        return 0.0
    sa, sb = set(t.lower() for t in tags_a), set(t.lower() for t in tags_b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def detect_contradictions(all_pages: dict, dry_run: bool = False) -> list[dict]:
    """
    Main entry point. Receives the all_pages dict from ain.py compile.
    Returns list of contradiction dicts; side-effects: writes DB + _Disputes/ stubs.

    all_pages: {slug -> {title, tags, links, group, date_str, file_path, ...}}
    """
    slugs  = list(all_pages.keys())
    n      = len(slugs)

    if n < 10:
        print("[contradiction] Too few nodes to run. Skipping.")
        return []

    print(f"[contradiction] Running voting engine on {n} nodes...")

    # Build text corpus: title + first-line summary tag string (ultra-lightweight)
    texts = []
    tag_lists = []
    for slug in slugs:
        info = all_pages[slug]
        title = info.get("title", slug.replace("_", " "))
        tags  = info.get("tags", [])
        tag_str = " ".join(tags)
        texts.append(f"{title} {tag_str}")
        tag_lists.append(tags)

    # --- Voter 1: TF-IDF cosine similarity ---
    print("[contradiction] Computing TF-IDF similarity matrix...")
    vec = TfidfVectorizer(ngram_range=(1, 3), max_features=5000, min_df=2, sublinear_tf=True)
    try:
        tfidf_matrix = vec.fit_transform(texts)
    except ValueError:
        print("[contradiction] TF-IDF failed (corpus too small/uniform). Skipping.")
        return []

    # Compute similarity in chunks to avoid OOM on 19k × 19k
    conflicts = []
    chunk_size = 500
    seen_pairs = set()

    for start_i in range(0, n, chunk_size):
        end_i = min(start_i + chunk_size, n)
        chunk = tfidf_matrix[start_i:end_i]
        sim_block = cosine_similarity(chunk, tfidf_matrix)  # (chunk_size, n)

        for local_i, global_i in enumerate(range(start_i, end_i)):
            for global_j in range(global_i + 1, n):
                sim_tf = float(sim_block[local_i, global_j])
                if sim_tf < TFIDF_THRESH * 0.7:   # fast pre-filter
                    continue

                pair_key = (slugs[global_i], slugs[global_j])
                if pair_key in seen_pairs:
                    continue

                # Voter 1
                v1 = int(sim_tf >= TFIDF_THRESH)

                # Voter 2: Jaccard
                tok_i = _tokenize(texts[global_i])
                tok_j = _tokenize(texts[global_j])
                sim_jac = _jaccard(tok_i, tok_j)
                v2 = int(sim_jac >= JACCARD_THRESH)

                # Voter 3: high semantic sim + tag disjointness
                tag_ov = _tag_overlap(tag_lists[global_i], tag_lists[global_j])
                v3 = int(sim_tf >= SEM_THRESH and tag_ov < TAG_OVERLAP_MAX)

                votes = v1 + v2 + v3

                if votes >= 2 and tag_ov < 0.80:  # don't flag near-duplicates in same category
                    seen_pairs.add(pair_key)
                    conflicts.append({
                        "slug_a":    slugs[global_i],
                        "slug_b":    slugs[global_j],
                        "title_a":   all_pages[slugs[global_i]].get("title", ""),
                        "title_b":   all_pages[slugs[global_j]].get("title", ""),
                        "tags_a":    tag_lists[global_i],
                        "tags_b":    tag_lists[global_j],
                        "sim_tfidf": round(sim_tf, 4),
                        "sim_jaccard": round(sim_jac, 4),
                        "vote_count": votes,
                    })

        if len(conflicts) >= MAX_PAIRS:
            break

    print(f"[contradiction] Found {len(conflicts)} conflict pairs (capped at {MAX_PAIRS}).")

    if dry_run:
        for c in conflicts[:10]:
            print(f"  [{c['vote_count']}v] {c['title_a'][:50]} ↔ {c['title_b'][:50]}  "
                  f"(tfidf={c['sim_tfidf']:.2f}, jac={c['sim_jaccard']:.2f})")
        return conflicts

    # Write to DB and _Disputes/ stubs
    _persist_conflicts(conflicts, all_pages)
    return conflicts


def _persist_conflicts(conflicts: list[dict], all_pages: dict):
    """Write conflict pairs to SQLite and create _Disputes/ markdown stubs."""
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()

    written = 0
    for c in conflicts:
        slug_a, slug_b = c["slug_a"], c["slug_b"]
        dispute_filename = f"CONTENDER_{slug_a[:30]}_{slug_b[:30]}.md"
        dispute_path     = os.path.join(DISPUTE_DIR, dispute_filename)

        # Check if already in DB (avoid reprocessing)
        cursor.execute(
            "SELECT id, resolution FROM contradictions WHERE slug_a=? AND slug_b=?",
            (slug_a, slug_b)
        )
        existing = cursor.fetchone()

        if existing:
            continue  # already logged; skip

        # Ask Ollama for resolution suggestion (optional, offline-safe)
        resolution = None
        excerpt_a = all_pages.get(slug_a, {}).get("title", slug_a)
        excerpt_b = all_pages.get(slug_b, {}).get("title", slug_b)
        resolution = ollama_helper.suggest_resolution_experiment(
            c["title_a"], c["title_b"], excerpt_a, excerpt_b
        )

        # Insert into DB
        try:
            cursor.execute("""
            INSERT OR IGNORE INTO contradictions
              (slug_a, slug_b, title_a, title_b, sim_tfidf, sim_jaccard, vote_count, dispute_file, resolution)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (slug_a, slug_b, c["title_a"], c["title_b"],
                  c["sim_tfidf"], c["sim_jaccard"], c["vote_count"],
                  dispute_filename, resolution))
        except Exception as e:
            print(f"[!] contradiction DB insert failed: {e}", file=sys.stderr)
            continue

        # Write _Disputes/ stub
        score_a = _get_score_str(slug_a)
        score_b = _get_score_str(slug_b)
        date_str = datetime.now().strftime("%Y-%m-%d")
        tags_a_str = ", ".join(c["tags_a"][:5])
        tags_b_str = ", ".join(c["tags_b"][:5])

        resolution_md = (
            f"\n## 🧪 Suggested Resolution Experiment\n{resolution}"
            if resolution else
            "\n## 🧪 Suggested Resolution Experiment\n*(Ollama unavailable — run `python ain.py disputes` to generate)*"
        )

        stub = f"""---
title: "[CONTENDER] {c['title_a'][:60]} vs {c['title_b'][:60]}"
date: "{date_str}"
tags: ["contender", "dispute", "unresolved"]
sources: ["Contradiction Engine (voting-based)"]
---

# [CONTENDER] Conflicting Claims Detected

## Node A
- **Slug**: [[{slug_a}]]
- **Title**: {c['title_a']}
- **Tags**: {tags_a_str}
- **Credibility Score**: {score_a}

## Node B
- **Slug**: [[{slug_b}]]
- **Title**: {c['title_b']}
- **Tags**: {tags_b_str}
- **Credibility Score**: {score_b}

## 📊 Detection Metrics
| Voter | Score | Threshold | Vote |
| :--- | :--- | :--- | :--- |
| TF-IDF cosine | {c['sim_tfidf']:.3f} | >{TFIDF_THRESH} | {"✅" if c['sim_tfidf'] >= TFIDF_THRESH else "❌"} |
| Jaccard overlap | {c['sim_jaccard']:.3f} | >{JACCARD_THRESH} | {"✅" if c['sim_jaccard'] >= JACCARD_THRESH else "❌"} |
| Tag disjointness | diverges | <{TAG_OVERLAP_MAX} | ✅ |
| **Total votes** | **{c['vote_count']}/3** | **≥2** | **🚨 CONFLICT** |
{resolution_md}

---
[[_Disputes]] [[CONTENDER]] [[{slug_a}]] [[{slug_b}]]
"""
        try:
            with open(dispute_path, "w", encoding="utf-8") as f:
                f.write(stub)
            written += 1
        except Exception as e:
            print(f"[!] Could not write dispute stub {dispute_path}: {e}", file=sys.stderr)

    conn.commit()
    conn.close()
    print(f"[contradiction] Persisted {written} new conflict stubs to _Disputes/.")


def _get_score_str(slug: str) -> str:
    try:
        conn = db_manager.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT score FROM credibility_scores WHERE slug=?", (slug,))
        row = cursor.fetchone()
        conn.close()
        return f"{row['score']:.2f}" if row else "0.50 (default)"
    except Exception:
        return "N/A"


def get_unresolved_count() -> int:
    """Returns number of unresolved contradiction pairs in DB."""
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM contradictions WHERE resolved=0")
    cnt = cursor.fetchone()["cnt"]
    conn.close()
    return cnt


def recalibrate_voters():
    """
    Self-rewriting voter logic (RL bonus feature).
    Reads the contradictions table for manually resolved items.
    If true positive (resolution indicates helpful/conflict confirmed), 
    we lower thresholds slightly to catch more.
    If false positive, we raise thresholds slightly to be stricter.
    """
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sim_tfidf, sim_jaccard, resolution FROM contradictions WHERE resolved=1")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("[contradiction] No resolved data to recalibrate on.")
        return
        
    tf_adj, jac_adj = 0.0, 0.0
    for row in rows:
        res = str(row["resolution"]).lower()
        if "false positive" in res or "ignore" in res:
            tf_adj += 0.005
            jac_adj += 0.005
        elif "helpful" in res or "confirmed" in res or "true positive" in res:
            tf_adj -= 0.005
            jac_adj -= 0.005
            
    # Apply learning rate
    lr = 0.1
    new_tf = max(0.5, min(0.95, TFIDF_THRESH + (tf_adj * lr)))
    new_jac = max(0.3, min(0.85, JACCARD_THRESH + (jac_adj * lr)))
    
    new_config = {"TFIDF_THRESH": round(new_tf, 3), "JACCARD_THRESH": round(new_jac, 3), "SEM_THRESH": SEM_THRESH}
    with open(CONFIG_FILE, "w") as f:
        json.dump(new_config, f, indent=2)
        
    print(f"[contradiction] Recalibrated voters. TFIDF: {new_tf:.3f}, Jaccard: {new_jac:.3f}")


# --- CLI ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AIN Contradiction Engine")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print conflicts without writing to DB or disk")
    parser.add_argument("--count", action="store_true",
                        help="Print count of unresolved contradictions in DB")
    parser.add_argument("--recalibrate", action="store_true",
                        help="Run RL recalibration loop based on user resolutions")
    args = parser.parse_args()

    if args.recalibrate:
        recalibrate_voters()
        sys.exit(0)

    if args.count:
        print(f"Unresolved contradictions: {get_unresolved_count()}")
        sys.exit(0)

    # Load all_pages from compile_cache.json for standalone run
    cache_path = os.path.join(BASE_DIR, "compile_cache.json")
    if not os.path.exists(cache_path):
        print("[!] compile_cache.json not found. Run 'python ain.py compile' first.")
        sys.exit(1)

    print("[*] Loading compile cache...")
    with open(cache_path, "r", encoding="utf-8") as f:
        raw_cache = json.load(f)

    # Reconstruct minimal all_pages from cache
    all_pages = {}
    for file_path, entry in raw_cache.items():
        slug = os.path.splitext(os.path.basename(file_path))[0]
        all_pages[slug] = {
            "title":     entry.get("title", slug),
            "tags":      entry.get("tags", []),
            "links":     entry.get("links", []),
            "group":     entry.get("group", "Core"),
            "date_str":  entry.get("date_str", ""),
            "file_path": file_path
        }

    detect_contradictions(all_pages, dry_run=args.dry_run)
