import os
import sys
import time
import json
import sqlite3
import traceback
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.join(BASE_DIR, "vault")
LOCK_FILE = os.path.join(VAULT_DIR, "ain_vault.lock")
DB_FILE = os.path.join(VAULT_DIR, "ain_system.db")

# Ensure vault directory exists
os.makedirs(VAULT_DIR, exist_ok=True)

# --- 1. OS-Level Kernel Atomic File Lock ---
class FileLock:
    """
    Highly robust, OS-level atomic file lock context manager.
    Uses standard library os.open with O_CREAT and O_EXCL to achieve atomic lock acquisition.
    """
    def __init__(self, lock_file_path=LOCK_FILE, timeout=15):
        self.lock_file_path = lock_file_path
        self.timeout = timeout
        self.has_lock = False

    def acquire(self):
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                # os.O_CREAT | os.O_EXCL is guaranteed atomic at the kernel level
                fd = os.open(self.lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self.has_lock = True
                return True
            except FileExistsError:
                # If lock exists, sleep slightly and try again
                time.sleep(0.05)
            except Exception as e:
                # Fallback print, do not crash the caller
                print(f"[!] Warning: Lock acquisition encountered unexpected error: {e}", file=sys.stderr)
                time.sleep(0.05)
        return False

    def release(self):
        if self.has_lock:
            try:
                os.remove(self.lock_file_path)
            except Exception:
                pass
            self.has_lock = False

    def __enter__(self):
        if not self.acquire():
            print(f"[!] Lock acquisition timed out after {self.timeout} seconds for {self.lock_file_path}. Proceeding under unsafe fallback mode.", file=sys.stderr)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

# --- 2. SQLite Database Queue & Error Manager ---
def get_db_connection():
    """Returns an active SQLite database connection with a high timeout to handle locks gracefully."""
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite queue and error monitoring tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Ingestion Queue Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT NOT NULL,
        identifier TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        tags TEXT NOT NULL,       -- JSON array
        sources TEXT NOT NULL,    -- JSON array
        category TEXT,
        status TEXT DEFAULT 'pending', -- pending, processed, failed
        retry_count INTEGER DEFAULT 0,
        error_log TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP
    )
    """)
    
    # 2. System Errors Table (Dead-letter Logging)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        component TEXT NOT NULL,
        error_message TEXT NOT NULL,
        traceback TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 3. Credibility Scores (self-evolving node reputation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credibility_scores (
        slug TEXT PRIMARY KEY,
        score REAL DEFAULT 0.5,
        confirmations INTEGER DEFAULT 0,
        falsifications INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        promoted_at TIMESTAMP,
        status TEXT DEFAULT 'active'  -- active | archived | first_principles
    )
    """)

    # 4. Backtest Results (hypothesis test outcomes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backtest_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hypothesis TEXT NOT NULL,
        source_slug TEXT,
        result TEXT,              -- supported | falsified | inconclusive | error
        p_value REAL,
        sharpe REAL,
        notes TEXT,
        code_stub TEXT,           -- the generated Python snippet
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 5. Contradictions (conflict pairs detected by voting engine)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contradictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug_a TEXT NOT NULL,
        slug_b TEXT NOT NULL,
        title_a TEXT,
        title_b TEXT,
        sim_tfidf REAL,
        sim_jaccard REAL,
        vote_count INTEGER DEFAULT 0,
        dispute_file TEXT,
        resolution TEXT,          -- Ollama-suggested experiment (if available)
        resolved INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(slug_a, slug_b)
    )
    """)
    
    conn.commit()
    conn.close()


def enqueue_item(item_type, identifier, title, content, tags, sources, category=None):
    """
    Safely transactionally enqueues a fetched research item.
    Returns True if successfully enqueued, False if it was already processed or queued.
    """
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    tags_json = json.dumps(tags)
    sources_json = json.dumps(sources)
    
    try:
        cursor.execute("""
        INSERT INTO ingestion_queue (item_type, identifier, title, content, tags, sources, category, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (item_type, identifier, title, content, tags_json, sources_json, category))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Item already exists in the queue (duplicate identifier)
        return False
    except Exception as e:
        log_system_error("QueueManager", f"Failed to enqueue {identifier}: {e}", traceback.format_exc())
        return False
    finally:
        conn.close()

def log_system_error(component, error_message, traceback_str=None):
    """Logs a system or crawl failure to the SQLite error database."""
    init_db()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        tb = traceback_str if traceback_str else "".join(traceback.format_stack())
        cursor.execute("""
        INSERT INTO system_errors (component, error_message, traceback)
        VALUES (?, ?, ?)
        """, (component, error_message, tb))
        conn.commit()
        conn.close()
        print(f"[!] Database logged error inside component '{component}': {error_message}", file=sys.stderr)
    except Exception as e:
        print(f"[!!] Critical Error writing to error database: {e}", file=sys.stderr)

def get_pending_queue(limit=100):
    """Retrieves list of pending queue items for processing."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, item_type, identifier, title, content, tags, sources, category, retry_count
    FROM ingestion_queue
    WHERE status = 'pending' AND retry_count < 3
    ORDER BY created_at ASC
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "item_type": r["item_type"],
            "identifier": r["identifier"],
            "title": r["title"],
            "content": r["content"],
            "tags": json.loads(r["tags"]),
            "sources": json.loads(r["sources"]),
            "category": r["category"],
            "retry_count": r["retry_count"]
        })
    return items

def mark_item_processed(item_id):
    """Marks a queue item as successfully processed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE ingestion_queue
    SET status = 'processed', processed_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (item_id,))
    conn.commit()
    conn.close()

def mark_item_failed(item_id, error_msg):
    """Increments retry counts and logs failure details on a queue item."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE ingestion_queue
    SET retry_count = retry_count + 1, error_log = ?
    WHERE id = ?
    """, (error_msg, item_id))
    
    # Check if dead-lettered
    cursor.execute("SELECT retry_count, identifier, item_type FROM ingestion_queue WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    dead_letter = False
    dead_letter_info = None
    if row and row["retry_count"] >= 3:
        cursor.execute("UPDATE ingestion_queue SET status = 'failed' WHERE id = ?", (item_id,))
        dead_letter = True
        dead_letter_info = (row['item_type'], row['identifier'])
        
    conn.commit()
    conn.close()
    
    if dead_letter and dead_letter_info:
        log_system_error(
            f"DeadLetterQueue_{dead_letter_info[0]}",
            f"Ingestion failed permanently for {dead_letter_info[1]} after 3 attempts. Error: {error_msg}"
        )

def get_system_metrics():
    """Gathers high-signal health metrics for the ain status CLI."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    metrics = {}
    try:
        # Ingestion queue aggregates
        cursor.execute("SELECT status, count(*) as count FROM ingestion_queue GROUP BY status")
        q_stats = {row["status"]: row["count"] for row in cursor.fetchall()}
        metrics["queue_pending"] = q_stats.get("pending", 0)
        metrics["queue_processed"] = q_stats.get("processed", 0)
        metrics["queue_failed"] = q_stats.get("failed", 0)
        
        # System errors counts
        cursor.execute("SELECT count(*) as count FROM system_errors")
        metrics["total_errors"] = cursor.fetchone()["count"]
        
        # Last 5 errors
        cursor.execute("SELECT component, error_message, timestamp FROM system_errors ORDER BY timestamp DESC LIMIT 5")
        metrics["recent_errors"] = [dict(row) for row in cursor.fetchall()]
        
    except Exception as e:
        metrics["db_error"] = str(e)
    finally:
        conn.close()
        
    return metrics

# Run database table initialization upon load
init_db()
