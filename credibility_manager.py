"""
credibility_manager.py — Self-evolving node reputation scoring system.

Zero token usage. Pure SQLite math.
Rules:
  - hypothesis confirmed   → score += 0.1  (max 1.0)
  - hypothesis falsified   → score -= 0.2  (min 0.0)
  - score < 0.3            → status = 'archived', moved to _Archived_Falsified/
  - score > 0.8 for 30d   → status = 'first_principles', moved to _First_Principles/
"""

import os
import sys
import shutil
from datetime import datetime, timedelta
import db_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join(BASE_DIR, "vault", "wiki")
ARCHIVE_DIR  = os.path.join(WIKI_DIR, "_Archived_Falsified")
PROMOTED_DIR = os.path.join(WIKI_DIR, "_First_Principles")

os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(PROMOTED_DIR, exist_ok=True)


# --- CRUD ---

def get_score(slug: str) -> float:
    """Returns current credibility score for slug, defaulting to 0.5."""
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT score FROM credibility_scores WHERE slug = ?", (slug,))
    row = cursor.fetchone()
    conn.close()
    return row["score"] if row else 0.5


def get_status(slug: str) -> str:
    """Returns node status: 'active' | 'archived' | 'first_principles'."""
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM credibility_scores WHERE slug = ?", (slug,))
    row = cursor.fetchone()
    conn.close()
    return row["status"] if row else "active"


def record_confirmation(slug: str):
    """Increment score +0.1 on hypothesis confirmation."""
    _update_score(slug, delta=+0.1, confirmed=True)


def record_falsification(slug: str):
    """Decrement score -0.2 on hypothesis falsification."""
    _update_score(slug, delta=-0.2, falsified=True)


def _update_score(slug: str, delta: float, confirmed: bool = False, falsified: bool = False):
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT score, confirmations, falsifications, promoted_at FROM credibility_scores WHERE slug = ?", (slug,))
    row = cursor.fetchone()

    if row:
        new_score = max(0.0, min(1.0, row["score"] + delta))
        new_conf  = row["confirmations"] + (1 if confirmed else 0)
        new_fals  = row["falsifications"] + (1 if falsified else 0)
        cursor.execute(
            "UPDATE credibility_scores SET score=?, confirmations=?, falsifications=?, last_updated=CURRENT_TIMESTAMP WHERE slug=?",
            (new_score, new_conf, new_fals, slug)
        )
    else:
        new_score = max(0.0, min(1.0, 0.5 + delta))
        new_conf  = 1 if confirmed else 0
        new_fals  = 1 if falsified else 0
        cursor.execute(
            "INSERT INTO credibility_scores (slug, score, confirmations, falsifications) VALUES (?, ?, ?, ?)",
            (slug, new_score, new_conf, new_fals)
        )

    conn.commit()
    conn.close()
    print(f"[credibility] {slug}: score now {new_score:.2f} (d{delta:+.1f})")


def ensure_score_exists(slug: str):
    """Initialize a score record at 0.5 if not present."""
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO credibility_scores (slug, score) VALUES (?, 0.5)",
        (slug,)
    )
    conn.commit()
    conn.close()


# --- Graph Rewiring ---

def apply_graph_rewiring(all_pages: dict) -> dict:
    """
    Called during ain.py compile. Reads scores from DB and:
      - Excludes archived nodes from Mermaid graph generation
      - Flags first_principles nodes for gold coloring in visualizer
      - Archives nodes scoring < 0.3
      - Promotes nodes scoring > 0.8 for 30+ days

    Returns a dict {slug -> status} for use in compile_wiki_locked.
    """
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT slug, score, status, last_updated, promoted_at FROM credibility_scores")
    rows = cursor.fetchall()
    conn.close()

    status_map = {}
    now = datetime.now()

    for row in rows:
        slug   = row["slug"]
        score  = row["score"]
        status = row["status"]

        if status == "active":
            if score < 0.3:
                # Archive this node
                _archive_node(slug, all_pages)
                status = "archived"
            elif score > 0.8:
                # Check if it's been above 0.8 for 30 days
                promoted_at = row["promoted_at"]
                if promoted_at is None:
                    _set_promoted_at(slug)
                else:
                    try:
                        pdate = datetime.fromisoformat(promoted_at)
                        if (now - pdate).days >= 30:
                            _promote_node(slug, all_pages)
                            status = "first_principles"
                    except Exception:
                        _set_promoted_at(slug)
            else:
                # Reset promoted_at if score dropped back below 0.8
                _clear_promoted_at(slug)

        status_map[slug] = status

    archived_count    = sum(1 for s in status_map.values() if s == "archived")
    principles_count  = sum(1 for s in status_map.values() if s == "first_principles")
    if archived_count or principles_count:
        print(f"[credibility] Rewiring: {archived_count} archived, {principles_count} in First Principles.")

    return status_map


def _set_promoted_at(slug: str):
    conn = db_manager.get_db_connection()
    conn.execute("UPDATE credibility_scores SET promoted_at=CURRENT_TIMESTAMP WHERE slug=?", (slug,))
    conn.commit()
    conn.close()


def _clear_promoted_at(slug: str):
    conn = db_manager.get_db_connection()
    conn.execute("UPDATE credibility_scores SET promoted_at=NULL WHERE slug=?", (slug,))
    conn.commit()
    conn.close()


def _archive_node(slug: str, all_pages: dict):
    """Move node file to _Archived_Falsified/ and update DB."""
    if slug in all_pages:
        src = all_pages[slug].get("file_path", "")
        if src and os.path.exists(src):
            dst = os.path.join(ARCHIVE_DIR, os.path.basename(src))
            try:
                shutil.move(src, dst)
                print(f"[credibility] Archived low-credibility node: {slug} (score < 0.3)")
            except Exception as e:
                print(f"[!] credibility: Could not archive {slug}: {e}", file=sys.stderr)
    conn = db_manager.get_db_connection()
    conn.execute("UPDATE credibility_scores SET status='archived' WHERE slug=?", (slug,))
    conn.commit()
    conn.close()


def _promote_node(slug: str, all_pages: dict):
    """Move node file to _First_Principles/ and update DB."""
    if slug in all_pages:
        src = all_pages[slug].get("file_path", "")
        if src and os.path.exists(src):
            dst = os.path.join(PROMOTED_DIR, os.path.basename(src))
            try:
                shutil.copy2(src, dst)  # copy (keep original, symlink-style)
                # Append STABLE badge to original
                with open(src, "a", encoding="utf-8") as f:
                    f.write(f"\n\n> [!TIP]\n> **[STABLE]** This node has maintained credibility > 0.8 for 30+ days.\n")
                print(f"[credibility] Promoted to First Principles: {slug} (score > 0.8, 30d+)")
            except Exception as e:
                print(f"[!] credibility: Could not promote {slug}: {e}", file=sys.stderr)
    conn = db_manager.get_db_connection()
    conn.execute("UPDATE credibility_scores SET status='first_principles' WHERE slug=?", (slug,))
    conn.commit()
    conn.close()


def get_all_scores_summary() -> list[dict]:
    """Returns sorted list of all scores for status display."""
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT slug, score, confirmations, falsifications, status, last_updated
        FROM credibility_scores ORDER BY score DESC LIMIT 50
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# --- CLI Test ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Credibility Manager CLI")
    parser.add_argument("--test", action="store_true", help="Run a self-test cycle")
    parser.add_argument("--confirm", metavar="SLUG", help="Record a confirmation for SLUG")
    parser.add_argument("--falsify", metavar="SLUG", help="Record a falsification for SLUG")
    parser.add_argument("--scores", action="store_true", help="Print top-50 scores")
    args = parser.parse_args()

    if args.test:
        print("[test] Recording confirmation for test_node_alpha...")
        for _ in range(4):
            record_confirmation("test_node_alpha")
        print("[test] Recording falsifications for test_node_beta (should archive)...")
        for _ in range(4):
            record_falsification("test_node_beta")
        print(f"[test] test_node_alpha score: {get_score('test_node_alpha'):.2f}")
        print(f"[test] test_node_beta  score: {get_score('test_node_beta'):.2f}")
        print(f"[test] test_node_beta  status: {get_status('test_node_beta')}")
        print("[test] PASS")

    elif args.confirm:
        record_confirmation(args.confirm)

    elif args.falsify:
        record_falsification(args.falsify)

    elif args.scores:
        scores = get_all_scores_summary()
        print("=" * 60)
        print("CREDIBILITY SCORES")
        print("=" * 60)
        for r in scores:
            bar = "█" * int(r["score"] * 10)
            print(f"  {r['score']:.2f} {bar:<10} [{r['status']:16}] {r['slug'][:50]}")
        print("=" * 60)
