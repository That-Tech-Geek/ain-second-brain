import os
import glob
import shutil
import json
from collections import Counter
from datetime import datetime
import db_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join(BASE_DIR, "vault", "wiki")
INBOX_DIR = os.path.join(WIKI_DIR, "01_Inbox")

# Target organizational directories
TARGETS = {
    "Quant_Finance": os.path.join(WIKI_DIR, "02_Research", "Quant_Finance"),
    "Machine_Learning": os.path.join(WIKI_DIR, "02_Research", "Machine_Learning"),
    "Technology": os.path.join(WIKI_DIR, "02_Research", "Technology"),
    "Mathematics": os.path.join(WIKI_DIR, "02_Research", "Mathematics"),
    "Quantum_Physics": os.path.join(WIKI_DIR, "02_Research", "Quantum_Physics"),
    "Economics": os.path.join(WIKI_DIR, "03_Research", "Economics"),
    "Business": os.path.join(WIKI_DIR, "03_Research", "Business"),
    "Other": os.path.join(WIKI_DIR, "01_Inbox", "Categorized")
}

for d in TARGETS.values():
    os.makedirs(d, exist_ok=True)

def parse_tags(filepath):
    tags = []
    is_github = False
    is_arxiv = False
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            if i > 20: # Frontmatter shouldn't be deeper than 20 lines
                break
            if line.startswith("tags:"):
                # basic parsing of: tags: ["a", "b"]
                try:
                    tag_str = line.replace("tags:", "").strip()
                    if tag_str.startswith("[") and tag_str.endswith("]"):
                        # strip quotes and brackets
                        clean = tag_str[1:-1].replace('"', '').replace("'", "")
                        tags = [t.strip() for t in clean.split(",") if t.strip()]
                except:
                    pass
            if line.startswith("status:") or line.startswith("* **Status:**"):
                if "open-source" in line.lower() or "github" in line.lower():
                    is_github = True
                if "arxiv" in line.lower():
                    is_arxiv = True
    
    if "github" in tags: is_github = True
    if "arxiv" in tags: is_arxiv = True
    return tags, is_github, is_arxiv

def categorize_file(tags):
    t_lower = [t.lower() for t in tags]
    if "finance" in t_lower or "quant" in t_lower or "trading" in t_lower:
        return "Quant_Finance"
    elif "machine-learning" in t_lower or "ai" in t_lower or "machine_learning" in t_lower or "deep learning" in t_lower or "llm" in t_lower:
        return "Machine_Learning"
    elif "technology" in t_lower or "computer-science" in t_lower or "web_architecture" in t_lower or "distributed systems" in t_lower:
        return "Technology"
    elif "math" in t_lower or "theory" in t_lower or "optimization" in t_lower:
        return "Mathematics"
    elif "physics" in t_lower or "quantum" in t_lower:
        return "Quantum_Physics"
    elif "economics" in t_lower:
        return "Economics"
    elif "business" in t_lower or "business_tech" in t_lower or "startup" in t_lower or "saas" in t_lower:
        return "Business"
    else:
        return "Other"

def main():
    print("[*] Starting Inbox Analysis and Organization...")
    
    with db_manager.FileLock():
        # 1. Process items from the SQLite Ingest Queue
        pending = db_manager.get_pending_queue(limit=5000)
        print(f"[*] Found {len(pending)} pending items in the database queue.")
        
        total_papers = 0
        total_repos = 0
        total_other = 0
        
        for item in pending:
            item_id = item["id"]
            item_type = item["item_type"]
            identifier = item["identifier"]
            title = item["title"]
            content = item["content"]
            tags = item["tags"]
            category = item["category"]
            
            # If content is empty, it is a stub queued by user. Skip until fetched.
            if not content:
                continue
                
            # Determine target category
            cat = category if category in TARGETS else categorize_file(tags)
            if cat not in TARGETS:
                cat = "Other"
                
            # Clean filename
            safe_name = identifier.replace("/", "_").replace("\\", "_")
            if not safe_name.endswith(".md"):
                safe_name += ".md"
                
            dest_path = os.path.join(TARGETS[cat], safe_name)
            
            try:
                # Write file directly and atomically to deep storage
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(content)
                    
                db_manager.mark_item_processed(item_id)
                if item_type == "arxiv":
                    total_papers += 1
                elif item_type == "github":
                    total_repos += 1
                else:
                    total_other += 1
            except Exception as e:
                err_msg = f"Failed to write queued item {identifier} to deep storage: {e}"
                print(f"[!] {err_msg}")
                db_manager.mark_item_failed(item_id, err_msg)
                
        # 2. Process legacy physical files in 01_Inbox
        physical_files = glob.glob(os.path.join(INBOX_DIR, "*.md"))
        files_to_process = [f for f in physical_files if "Daemon_" in os.path.basename(f) or "ArXiv_" in os.path.basename(f) or "GitHub_" in os.path.basename(f) or "YT_Insights_" in os.path.basename(f)]
        
        if files_to_process:
            print(f"[*] Found {len(files_to_process)} raw legacy nodes in physical Inbox. Routing...")
            for filepath in files_to_process:
                tags, is_github, is_arxiv = parse_tags(filepath)
                cat = categorize_file(tags)
                
                if is_github: total_repos += 1
                elif is_arxiv: total_papers += 1
                else: total_other += 1
                
                filename = os.path.basename(filepath)
                dest_path = os.path.join(TARGETS[cat], filename)
                
                try:
                    shutil.move(filepath, dest_path)
                except Exception as e:
                    pass
                    
        total_processed = total_papers + total_repos + total_other
        print(f"[+] All items successfully organized. Total Processed: {total_processed}")
        
        # Trigger report reconstruction
        try:
            import reconstruct_report
            reconstruct_report.main()
        except Exception as e:
            print(f"[!] Warning: Could not run report reconstruction: {e}")

if __name__ == "__main__":
    main()
