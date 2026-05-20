"""
snapshot_manager.py — FAISS vector snapshot with reboot delta intelligence.

On shutdown: builds a TF-IDF index + mtime manifest, saves to disk.
On reboot:   loads manifest, computes file diff, re-indexes changed files only.
             Calls Ollama (~100 tokens) for a 3-bullet delta summary.

Uses sklearn TF-IDF vectors + FAISS IndexFlatIP (cosine via normalized vecs).
Falls back to pure numpy dot-product if FAISS unavailable.
"""

import os
import sys
import json
import pickle
import numpy as np
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer

import db_manager
import ollama_helper

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR     = os.path.join(BASE_DIR, "vault")
WIKI_DIR      = os.path.join(VAULT_DIR, "wiki")
SNAPSHOT_IDX  = os.path.join(VAULT_DIR, "faiss_snapshot.npz")    # numpy fallback
MANIFEST_FILE = os.path.join(VAULT_DIR, "snapshot_manifest.json")
VECTORIZER_F  = os.path.join(VAULT_DIR, "snapshot_vectorizer.pkl")
DELTA_FILE    = os.path.join(WIKI_DIR, "01_Inbox", "reboot_delta.md")

# Try importing FAISS; fall back to numpy cosine search
try:
    import faiss
    _FAISS_AVAILABLE = True
except ImportError:
    _FAISS_AVAILABLE = False


def _walk_wiki_files() -> dict:
    """Returns {file_path: mtime} for all .md files in the wiki tree."""
    manifest = {}
    for root, _, files in os.walk(WIKI_DIR):
        for f in files:
            if f.endswith(".md"):
                fp = os.path.join(root, f)
                try:
                    manifest[fp] = os.path.getmtime(fp)
                except Exception:
                    pass
    return manifest


def build_snapshot(all_pages: dict = None):
    """
    Build and save the vector index.
    all_pages: optional pre-loaded page dict from ain.py compile.
               If None, reconstructs from compile_cache.json.
    """
    print("[snapshot] Building vector snapshot...")

    # Load pages if not supplied
    if all_pages is None:
        all_pages = _load_pages_from_cache()

    if not all_pages:
        print("[snapshot] No pages found. Skipping.")
        return

    slugs  = list(all_pages.keys())
    texts  = [
        f"{all_pages[s].get('title', '')} {' '.join(all_pages[s].get('tags', []))}"
        for s in slugs
    ]

    # Build TF-IDF matrix
    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=3000, sublinear_tf=True)
    tfidf = vec.fit_transform(texts).toarray().astype(np.float32)

    # L2-normalize for cosine similarity via dot product
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    tfidf_norm = tfidf / norms

    # Save vectorizer
    with open(VECTORIZER_F, "wb") as f:
        pickle.dump(vec, f)

    # Save index
    if _FAISS_AVAILABLE:
        d = tfidf_norm.shape[1]
        index = faiss.IndexFlatIP(d)
        index.add(tfidf_norm)
        faiss.write_index(index, SNAPSHOT_IDX.replace(".npz", ".faiss"))
        print(f"[snapshot] FAISS index saved ({index.ntotal} vectors, dim={d}).")
    else:
        np.savez_compressed(SNAPSHOT_IDX, vectors=tfidf_norm, slugs=np.array(slugs))
        print(f"[snapshot] NumPy index saved ({len(slugs)} vectors).")

    # Save mtime manifest
    manifest = _walk_wiki_files()
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "slugs":     slugs,
            "timestamp": datetime.now().isoformat(),
            "file_count": len(manifest),
            "mtimes":    manifest
        }, f, indent=2)

    print(f"[snapshot] Manifest saved: {len(slugs)} nodes, {len(manifest)} files tracked.")


def reboot_delta_report() -> str:
    """
    Called on reboot. Compares current file state vs saved manifest.
    Returns path to written delta report or empty string.
    """
    if not os.path.exists(MANIFEST_FILE):
        print("[snapshot] No manifest found. First run — building baseline.")
        build_snapshot()
        return ""

    print("[snapshot] Comparing reboot state vs last snapshot...")

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    last_mtimes   = manifest.get("mtimes", {})
    last_ts       = manifest.get("timestamp", "unknown")
    current_files = _walk_wiki_files()

    new_files      = [fp for fp in current_files if fp not in last_mtimes]
    modified_files = [
        fp for fp in current_files
        if fp in last_mtimes and abs(current_files[fp] - last_mtimes[fp]) > 1.0
    ]
    deleted_files  = [fp for fp in last_mtimes if fp not in current_files]

    def _basename_list(fps):
        return [os.path.basename(fp) for fp in fps[:10]]

    new_names  = _basename_list(new_files)
    mod_names  = _basename_list(modified_files)
    del_names  = _basename_list(deleted_files)

    print(f"[snapshot] Δ: +{len(new_files)} new, ~{len(modified_files)} modified, -{len(deleted_files)} deleted.")

    # Get Ollama 3-bullet summary
    delta_summary = ollama_helper.summarize_delta(new_names, mod_names)

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    delta_md = f"""---
title: "Reboot Delta Report — {date_str}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
tags: ["reboot", "delta", "system"]
sources: ["AIN Snapshot Manager"]
---

# 🔄 Reboot Delta Report

**Snapshot taken**: {last_ts}  
**Current time**: {date_str}

## 📊 File System Changes
| Category | Count | Files |
| :--- | :---: | :--- |
| **New** | {len(new_files)} | {', '.join(new_names[:5]) or 'none'} |
| **Modified** | {len(modified_files)} | {', '.join(mod_names[:5]) or 'none'} |
| **Deleted** | {len(deleted_files)} | {', '.join(del_names[:5]) or 'none'} |

## 🧠 AI Delta Summary
{delta_summary if delta_summary else "*(Ollama unavailable — summary not generated)*"}

## ⚡ Actions Taken
- {'Re-indexed ' + str(len(new_files) + len(modified_files)) + ' changed files' if new_files or modified_files else 'No re-indexing needed'}
- Run `python ain.py compile` to fully synchronize INDEX.md

---
[[reboot_delta]] [[system]]
"""

    os.makedirs(os.path.dirname(DELTA_FILE), exist_ok=True)
    with open(DELTA_FILE, "w", encoding="utf-8") as f:
        f.write(delta_md)

    print(f"[snapshot] Delta report written to: {os.path.relpath(DELTA_FILE, BASE_DIR)}")

    # Rebuild snapshot with updated state
    build_snapshot()
    return DELTA_FILE


def search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vector similarity search over the snapshot index.
    Returns top-k {slug, score} dicts.
    Used by ain.py speculate for RAG retrieval.
    """
    if not os.path.exists(MANIFEST_FILE):
        return []

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    slugs = manifest.get("slugs", [])
    if not slugs:
        return []

    # Load vectorizer
    if not os.path.exists(VECTORIZER_F):
        return []
    with open(VECTORIZER_F, "rb") as f:
        vec = pickle.load(f)

    query_vec = vec.transform([query]).toarray().astype(np.float32)
    norm = np.linalg.norm(query_vec)
    if norm > 0:
        query_vec = query_vec / norm

    faiss_path = SNAPSHOT_IDX.replace(".npz", ".faiss")
    if _FAISS_AVAILABLE and os.path.exists(faiss_path):
        index = faiss.read_index(faiss_path)
        scores, indices = index.search(query_vec, top_k)
        return [{"slug": slugs[i], "score": float(scores[0][k])}
                for k, i in enumerate(indices[0]) if i < len(slugs)]

    elif os.path.exists(SNAPSHOT_IDX):
        data = np.load(SNAPSHOT_IDX, allow_pickle=True)
        vecs = data["vectors"]
        all_slugs = list(data["slugs"])
        sims = (vecs @ query_vec.T).flatten()
        top_idx = np.argsort(sims)[::-1][:top_k]
        return [{"slug": all_slugs[i], "score": float(sims[i])} for i in top_idx]

    return []


def _load_pages_from_cache() -> dict:
    cache_path = os.path.join(BASE_DIR, "compile_cache.json")
    if not os.path.exists(cache_path):
        return {}
    with open(cache_path, "r", encoding="utf-8") as f:
        raw_cache = json.load(f)
    pages = {}
    for fp, entry in raw_cache.items():
        slug = os.path.splitext(os.path.basename(fp))[0]
        pages[slug] = {
            "title":    entry.get("title", slug),
            "tags":     entry.get("tags", []),
            "file_path": fp
        }
    return pages


# --- CLI ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AIN Snapshot Manager")
    parser.add_argument("--build",  action="store_true", help="Build snapshot now")
    parser.add_argument("--delta",  action="store_true", help="Run reboot delta report")
    parser.add_argument("--search", metavar="QUERY",     help="Search the snapshot index")
    args = parser.parse_args()

    if args.build:
        build_snapshot()
    elif args.delta:
        reboot_delta_report()
    elif args.search:
        results = search(args.search, top_k=10)
        print(f"\nTop results for '{args.search}':")
        for r in results:
            print(f"  {r['score']:.3f}  {r['slug']}")
    else:
        parser.print_help()
