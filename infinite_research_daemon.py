import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import argparse
from datetime import datetime, timedelta
import db_manager
import traceback
from agi_core.self_recourse_brain import SelfRecourseBrain

# Reconfigure standard output encoding to prevent Windows CP1252/UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join(BASE_DIR, "vault", "wiki", "01_Inbox")
os.makedirs(WIKI_DIR, exist_ok=True)

# State Files
ARXIV_STATE_FILE = os.path.join(BASE_DIR, "daemon_state.json")
GITHUB_STATE_FILE = os.path.join(BASE_DIR, "github_daemon_state.json")

# Try to get PAT from environment variable for higher GitHub rate limits
GITHUB_PAT = os.environ.get("GITHUB_AGENT_PAT")

# Categories Configurations
ARXIV_CATEGORIES = {
    "Finance": {"query": "cat:q-fin.*", "tags": ["finance", "quant", "arxiv"]},
    "Technology": {"query": "cat:cs.CR OR cat:cs.DC OR cat:cs.NI OR cat:cs.SE OR cat:cs.SY", "tags": ["technology", "computer-science", "arxiv"]},
    "Machine_Learning": {"query": "cat:cs.LG OR cat:cs.AI OR cat:stat.ML", "tags": ["machine-learning", "ai", "arxiv"]},
    "Business_Econ": {"query": "cat:econ.* OR cat:q-fin.EC", "tags": ["economics", "business", "arxiv"]},
    "Mathematics": {"query": "cat:math.*", "tags": ["math", "theory", "arxiv"]},
    "Quantum_Physics": {"query": "cat:quant-ph", "tags": ["physics", "quantum", "arxiv"]}
}

GITHUB_CATEGORIES = {
    "Quant_Finance": "quantitative OR finance OR trading OR backtesting OR algorithm",
    "Machine_Learning": "machine learning OR deep learning OR llm OR transformer OR pytorch",
    "Agentic_AI": "autonomous agents OR llm agent OR agi OR langchain OR automation",
    "Web_Architecture": "microservices OR distributed systems OR edge computing OR serverless OR backend",
    "Business_Tech": "saas OR erp OR fintech OR startup OR analytics",
    "Math_Optimization": "optimization OR numerical analysis OR solver OR linear programming",
    "Cybersecurity": "security OR cryptography OR penetration testing OR malware analysis"
}

# --- Time Window Helper Logic ---
def is_in_active_window():
    """
    Checks if current local time is within 10 PM (22:00) to 7 AM (07:00).
    """
    now = datetime.now().time()
    start_time = datetime.strptime("22:00", "%H:%M").time()
    end_time = datetime.strptime("07:00", "%H:%M").time()
    return now >= start_time or now <= end_time

# --- State Management Helper Functions ---
def load_arxiv_state():
    """
    Loads ArXiv ingestion state.
    Format: { category: { "latest_seen_id": "http://...", "last_run": "YYYY-MM-DD" } }
    """
    if os.path.exists(ARXIV_STATE_FILE):
        try:
            with open(ARXIV_STATE_FILE, "r") as f:
                state = json.load(f)
                if state and isinstance(next(iter(state.values())), int):
                    state = {cat: {"latest_seen_id": "", "last_run": ""} for cat in ARXIV_CATEGORIES.keys()}
                return state
        except:
            pass
    return {cat: {"latest_seen_id": "", "last_run": ""} for cat in ARXIV_CATEGORIES.keys()}

def save_arxiv_state(state):
    with open(ARXIV_STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def load_github_state():
    """
    Loads GitHub crawler state.
    Format: { "last_run_date": "YYYY-MM-DD", "categories": { category: page_num } }
    """
    default_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    if os.path.exists(GITHUB_STATE_FILE):
        try:
            with open(GITHUB_STATE_FILE, "r") as f:
                state = json.load(f)
                if "last_run_date" not in state:
                    state["last_run_date"] = default_date
                if "categories" not in state:
                    state["categories"] = {cat: 1 for cat in GITHUB_CATEGORIES.keys()}
                return state
        except:
            pass
    return {
        "last_run_date": default_date,
        "categories": {cat: 1 for cat in GITHUB_CATEGORIES.keys()}
    }

def save_github_state(state):
    with open(GITHUB_STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

EXISTING_RESEARCH_TITLES = set()

def clean_filename(title):
    clean = "".join([c if c.isalnum() or c.isspace() else "_" for c in title])
    clean = clean.replace(" ", "_")
    clean = "_".join(filter(None, clean.split("_")))
    return clean[:100]

def load_existing_research_titles():
    """
    Quickly scans the vault/wiki folder for existing file names
    and extracts the clean title parts to prevent duplicate downloads.
    """
    existing_titles = set()
    vault_path = os.path.join(BASE_DIR, "vault", "wiki")
    if not os.path.exists(vault_path):
        return existing_titles
        
    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                slug = os.path.splitext(file)[0].lower()
                # If it's a daemon ingested file, extract the title part
                if slug.startswith("daemon_arxiv_"):
                    # format: daemon_arxiv_{category}_{safe_title}
                    remaining = slug[len("daemon_arxiv_"):]
                    matched = False
                    for cat in ARXIV_CATEGORIES.keys():
                        cat_lower = cat.lower() + "_"
                        if remaining.startswith(cat_lower):
                            existing_titles.add(remaining[len(cat_lower):])
                            matched = True
                            break
                    if not matched:
                        existing_titles.add(slug)
                elif slug.startswith("daemon_gh_"):
                    # format: daemon_gh_{category}_{safe_title}
                    remaining = slug[len("daemon_gh_"):]
                    matched = False
                    for cat in GITHUB_CATEGORIES.keys():
                        cat_lower = cat.lower() + "_"
                        if remaining.startswith(cat_lower):
                            existing_titles.add(remaining[len(cat_lower):])
                            matched = True
                            break
                    if not matched:
                        existing_titles.add(slug)
                else:
                    existing_titles.add(slug)
    return existing_titles

# --- Core Sync Trigger Function ---
def trigger_sync(is_shutdown=False):
    if is_shutdown:
        print("\n[!] Graceful Shutdown Triggered! Intercepting process control...")
        print("[*] Running final AIN Sync to organize inbox and compile Knowledge Graph...")
    else:
        print("[*] Triggering AIN Sync pipeline...")
        
    import signal
    original_handler = None
    try:
        original_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    except ValueError:
        pass
        
    try:
        import organize_inbox
        import reconstruct_report
        import ain
        
        organize_inbox.main()
        reconstruct_report.main()
        ain.compile_wiki()
        
        print("[+] AIN Sync completed successfully.")
    except Exception as e:
        print(f"[!] AIN Sync encountered an error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if original_handler is not None:
            try:
                signal.signal(signal.SIGINT, original_handler)
            except ValueError:
                pass

# --- ArXiv Ingestion Logic ---
def fetch_arxiv_papers(brain, category, query_data, state_entry, batch_size=20):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Daemon: Fetching ArXiv '{category}'...")
    
    query = query_data["query"]
    tags = query_data["tags"]
    latest_seen_id = state_entry.get("latest_seen_id", "")
    
    start_offset = 0
    max_pages = 3
    processed = 0
    new_latest_id = None
    stop_fetching = False
    
    for page in range(max_pages):
        url = f"https://export.arxiv.org/api/query?search_query={urllib.parse.quote(query)}&start={start_offset}&max_results={batch_size}&sortBy=submittedDate&sortOrder=descending"
        req = urllib.request.Request(url, headers={'User-Agent': 'AIN-Daemon-Bot'})
        
        try:
            response = urllib.request.urlopen(req)
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('atom:entry', ns)
            
            if not entries:
                print(f"    -> No entries found at offset {start_offset}.")
                break
                
            if page == 0 and len(entries) > 0:
                first_entry_id = entries[0].find('atom:id', ns)
                if first_entry_id is not None and first_entry_id.text:
                    new_latest_id = first_entry_id.text.strip()
            
            page_processed = 0
            for entry in entries:
                id_elem = entry.find('atom:id', ns)
                link = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                
                if latest_seen_id and link == latest_seen_id:
                    print(f"    -> Reached already ingested paper ID: {link}. Stopping ingestion.")
                    stop_fetching = True
                    break
                
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text.replace('\\n', ' ').replace('\n', ' ').strip() if title_elem is not None and title_elem.text else "Untitled Paper"
                
                summary_elem = entry.find('atom:summary', ns)
                summary = summary_elem.text.replace('\\n', ' ').replace('\n', ' ').strip() if summary_elem is not None and summary_elem.text else "No abstract provided."
                
                authors = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text.strip())
                
                safe_title = clean_filename(title)
                if safe_title.lower() in EXISTING_RESEARCH_TITLES:
                    continue
                    
                date_str = datetime.now().strftime("%Y-%m-%d")
                
                md_content = f"""---
title: "{title.replace('"', "'")}"
date: "{date_str}"
tags: {json.dumps(tags)}
sources: ["{link}"]
---

# {title}

## Meta
* **Authors:** {", ".join(authors)}
* **Source:** {link}
* **Category:** {category}
* **Status:** Auto-ingested ArXiv paper.

## Abstract
{summary}

## AIN Synthesis
*This paper was automatically ingested via the academic API batch pipeline. Future iterations of the AIN agent can run local summarization or embeddings over this abstract.*

---
{' '.join([f"[[{t}]]" for t in tags])}
"""
                identifier = f"Daemon_ArXiv_{category}_{safe_title}"
                success = db_manager.enqueue_item(
                    item_type="arxiv",
                    identifier=identifier,
                    title=title,
                    content=md_content,
                    tags=tags,
                    sources=[link],
                    category=category
                )
                
                EXISTING_RESEARCH_TITLES.add(safe_title.lower())
                if success:
                    processed += 1
                    if brain:
                        brain.assimilate_information(category, safe_title)
                        if brain.epistemic_distress > 0.70:
                            brain.execute_self_recourse(root_cause_variable=category)
                page_processed += 1
                
            print(f"    -> Page {page+1}: processed {page_processed} entries.")
            
            if stop_fetching or len(entries) < batch_size:
                break
                
            start_offset += batch_size
            time.sleep(3)
            
        except Exception as e:
            err_msg = f"Error fetching ArXiv category {category} on page {page+1}: {e}"
            print(f"    -> {err_msg}")
            db_manager.log_system_error(f"ArXivCrawler_{category}", err_msg, traceback.format_exc())
            break
            
    print(f"    -> Completed. Ingested {processed} new ArXiv papers into SQLite queue.")
    
    if new_latest_id:
        state_entry["latest_seen_id"] = new_latest_id
        state_entry["last_run"] = datetime.now().strftime("%Y-%m-%d")
        
    return processed > 0

# --- GitHub Ingestion Logic ---
def fetch_github_repos(category, base_query, page, last_run_date):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Daemon: Crawling GitHub '{category}' (Page: {page}, Pushed since: {last_run_date})...")
    
    full_query = f"({base_query}) pushed:>{last_run_date}"
    url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(full_query)}&sort=stars&per_page=50&page={page}"
    req = urllib.request.Request(url, headers={'User-Agent': 'AIN-Infinite-Daemon'})
    
    global GITHUB_PAT
    if GITHUB_PAT:
        req.add_header('Authorization', f'token {GITHUB_PAT}')
        
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode('utf-8'))
        
        remaining = response.headers.get('X-RateLimit-Remaining')
        if remaining:
            print(f"    -> Rate Limit Remaining: {remaining}")
            
        return data.get("items", []), None
        
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("    -> [!] Invalid GITHUB_AGENT_PAT (401 Unauthorized). Dropping to anonymous tier.")
            GITHUB_PAT = None
            return "RETRY_ANON", 401
        elif e.code in [403, 429]:
            err_msg = f"GitHub Rate Limited (HTTP {e.code}) while crawling {category}."
            print(f"    -> [!] {err_msg}")
            db_manager.log_system_error(f"GitHubCrawler_{category}", err_msg, traceback.format_exc())
            return [], e.code
        elif e.code == 422:
            print(f"    -> [!] End of pagination reached for GitHub {category} (HTTP 422).")
            return "RESET", e.code
        else:
            err_msg = f"HTTP Error fetching GitHub {category}: {e} (Status: {e.code})"
            print(f"    -> {err_msg}")
            db_manager.log_system_error(f"GitHubCrawler_{category}", err_msg, traceback.format_exc())
            return [], e.code
    except Exception as e:
        err_msg = f"Network Error fetching GitHub {category}: {e}"
        print(f"    -> {err_msg}")
        db_manager.log_system_error(f"GitHubCrawler_{category}", err_msg, traceback.format_exc())
        return [], 500

def process_github_repos(brain, repos, cat_name):
    processed = 0
    for repo in repos:
        name = repo.get("name", "Unknown")
        full_name = repo.get("full_name", name)
        description = repo.get("description", "No description provided.")
        url = repo.get("html_url", "")
        stars = repo.get("stargazers_count", 0)
        language = repo.get("language", "Unknown")
        topics = repo.get("topics", [])
        
        safe_title = clean_filename(full_name)
        if safe_title.lower() in EXISTING_RESEARCH_TITLES:
            continue
            
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        tags = ["github", "open-source", cat_name.lower()] + topics
        
        md_content = f"""---
title: "{name.replace('"', "'")}"
date: "{date_str}"
tags: {json.dumps(tags[:10])}
sources: ["{url}"]
---

# GitHub Repo: {full_name}

## Meta
* **Repository:** {url}
* **Stars:** {stars}
* **Primary Language:** {language}
* **Category:** {cat_name.replace("_", " ")}
* **Status:** Auto-ingested GitHub repository.

## Description
{description}

## Topics
{', '.join(topics)}

---
{' '.join([f"[[{t}]]" for t in tags[:10]])}
"""
        identifier = f"Daemon_GH_{cat_name}_{safe_title}"
        success = db_manager.enqueue_item(
            item_type="github",
            identifier=identifier,
            title=name,
            content=md_content,
            tags=tags[:10],
            sources=[url],
            category=cat_name
        )
        
        EXISTING_RESEARCH_TITLES.add(safe_title.lower())
        if success:
            processed += 1
            if brain:
                brain.assimilate_information(cat_name, safe_title)
                if brain.epistemic_distress > 0.70:
                    brain.execute_self_recourse(root_cause_variable=cat_name)
            
    return processed

# --- 10/10 Enterprise Features: Single Ingest & Daytime Processing ---

def fetch_single_arxiv_paper(paper_id):
    """Fetches metadata for a single ArXiv paper by ID with 429 rate limit retries."""
    print(f"[*] Crawling single ArXiv paper: {paper_id}...")
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(paper_id)}"
    req = urllib.request.Request(url, headers={'User-Agent': 'AIN-Daemon-Bot'})
    
    retries = 2
    response = None
    for attempt in range(retries + 1):
        try:
            response = urllib.request.urlopen(req)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                print(f"    -> [!] ArXiv rate limit (429) hit in single crawler. Retrying in 4 seconds (attempt {attempt+1}/{retries})...")
                time.sleep(4)
            else:
                raise e
        except Exception as e:
            if attempt < retries:
                print(f"    -> [!] Connection error: {e} in single crawler. Retrying in 4 seconds...")
                time.sleep(4)
            else:
                raise e
                
    if response is None:
        raise Exception("Failed to fetch response after retries.")
        
    xml_data = response.read()
    root = ET.fromstring(xml_data)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    entry = root.find('atom:entry', ns)
    if entry is None:
        raise Exception(f"No entry found for ArXiv ID: {paper_id}")
        
    id_elem = entry.find('atom:id', ns)
    link = id_elem.text.strip() if id_elem is not None and id_elem.text else f"https://arxiv.org/abs/{paper_id}"
    
    title_elem = entry.find('atom:title', ns)
    title = title_elem.text.replace('\\n', ' ').replace('\n', ' ').strip() if title_elem is not None and title_elem.text else f"ArXiv Paper {paper_id}"
    
    summary_elem = entry.find('atom:summary', ns)
    summary = summary_elem.text.replace('\\n', ' ').replace('\n', ' ').strip() if summary_elem is not None and summary_elem.text else "No abstract provided."
    
    authors = []
    for author in entry.findall('atom:author', ns):
        name_elem = author.find('atom:name', ns)
        if name_elem is not None and name_elem.text:
            authors.append(name_elem.text.strip())
            
    tags = ["arxiv", "queued"]
    # We can try to map some basic categories based on primary category
    primary_cat = entry.find('arxiv:primary_category', {'arxiv': 'http://arxiv.org/schemas/atom'})
    category = "Other"
    if primary_cat is not None:
        cat_attrib = primary_cat.attrib.get('term', '')
        tags.append(cat_attrib)
        if cat_attrib.startswith("q-fin"):
            category = "Quant_Finance"
        elif cat_attrib.startswith("cs.LG") or cat_attrib.startswith("cs.AI") or cat_attrib.startswith("stat.ML"):
            category = "Machine_Learning"
        elif cat_attrib.startswith("cs."):
            category = "Technology"
        elif cat_attrib.startswith("math"):
            category = "Mathematics"
        elif cat_attrib.startswith("quant-ph"):
            category = "Quantum_Physics"
        elif cat_attrib.startswith("econ"):
            category = "Economics"
            
    date_str = datetime.now().strftime("%Y-%m-%d")
    md_content = f"""---
title: "{title.replace('"', "'")}"
date: "{date_str}"
tags: {json.dumps(tags)}
sources: ["{link}"]
---

# {title}

## Meta
* **Authors:** {", ".join(authors)}
* **Source:** {link}
* **Category:** {category}
* **Status:** Queued and custom-ingested ArXiv paper.

## Abstract
{summary}

## AIN Synthesis
*This paper was queued by the user and custom-ingested via the ArXiv ID lookup.*

---
{' '.join([f"[[{t}]]" for t in tags])}
"""
    return {
        "title": title,
        "content": md_content,
        "tags": tags,
        "sources": [link],
        "category": category
    }

def fetch_single_github_repo(repo_fullname):
    """Fetches metadata for a single GitHub repository by user/repo name with 401 fallback."""
    print(f"[*] Crawling single GitHub repository: {repo_fullname}...")
    url = f"https://api.github.com/repos/{repo_fullname}"
    req = urllib.request.Request(url, headers={'User-Agent': 'AIN-Infinite-Daemon'})
    
    global GITHUB_PAT
    if GITHUB_PAT:
        req.add_header('Authorization', f'token {GITHUB_PAT}')
        
    try:
        response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("    -> [!] Invalid GITHUB_AGENT_PAT (401 Unauthorized) in single crawler. Retrying with anonymous credentials...")
            GITHUB_PAT = None
            req = urllib.request.Request(url, headers={'User-Agent': 'AIN-Infinite-Daemon'})
            response = urllib.request.urlopen(req)
        else:
            raise e
            
    repo = json.loads(response.read().decode('utf-8'))
    
    name = repo.get("name", repo_fullname.split("/")[-1])
    full_name = repo.get("full_name", repo_fullname)
    description = repo.get("description", "No description provided.")
    repo_url = repo.get("html_url", f"https://github.com/{repo_fullname}")
    stars = repo.get("stargazers_count", 0)
    language = repo.get("language", "Unknown")
    
    # Get topics
    topics = repo.get("topics", [])
    
    tags = ["github", "queued"] + topics
    category = "Other"
    
    # Determine category based on topics and description
    desc_lower = description.lower()
    t_lower = [t.lower() for t in tags]
    if any(k in desc_lower or k in t_lower for k in ["quant", "finance", "trading", "backtest"]):
        category = "Quant_Finance"
    elif any(k in desc_lower or k in t_lower for k in ["machine learning", "deep learning", "llm", "transformer", "ai"]):
        category = "Machine_Learning"
    elif any(k in desc_lower or k in t_lower for k in ["distributed", "serverless", "architecture", "microservice"]):
        category = "Technology"
    elif any(k in desc_lower or k in t_lower for k in ["math", "optimization", "solver"]):
        category = "Mathematics"
    elif any(k in desc_lower or k in t_lower for k in ["quantum", "physics"]):
        category = "Quantum_Physics"
    elif any(k in desc_lower or k in t_lower for k in ["economics"]):
        category = "Economics"
    elif any(k in desc_lower or k in t_lower for k in ["business", "saas", "fintech", "startup"]):
        category = "Business"
        
    date_str = datetime.now().strftime("%Y-%m-%d")
    md_content = f"""---
title: "{name.replace('"', "'")}"
date: "{date_str}"
tags: {json.dumps(tags[:10])}
sources: ["{repo_url}"]
---

# GitHub Repo: {full_name}

## Meta
* **Repository:** {repo_url}
* **Stars:** {stars}
* **Primary Language:** {language}
* **Category:** {category.replace("_", " ")}
* **Status:** Queued and custom-ingested GitHub repository.

## Description
{description}

## Topics
{', '.join(topics)}

---
{' '.join([f"[[{t}]]" for t in tags[:10]])}
"""
    return {
        "title": name,
        "content": md_content,
        "tags": tags[:10],
        "sources": [repo_url],
        "category": category
    }

def process_daytime_queue():
    """Processes any pending items in the ingestion queue, especially user-queued stubs."""
    pending_items = db_manager.get_pending_queue(limit=50)
    if not pending_items:
        return False
        
    print(f"[*] Found {len(pending_items)} pending items in the ingestion queue. Processing...")
    processed_count = 0
    
    for item in pending_items:
        item_id = item["id"]
        item_type = item["item_type"]
        identifier = item["identifier"]
        content = item["content"]
        
        # If content is empty, it needs to be fetched
        if not content:
            print(f"[*] Crawling queued item: [{item_type.upper()}] {identifier}...")
            try:
                if item_type == "arxiv":
                    # Extract ArXiv paper ID from identifier (e.g. arxiv_2305.14314 -> 2305.14314)
                    paper_id = identifier.replace("arxiv_", "")
                    data = fetch_single_arxiv_paper(paper_id)
                elif item_type == "github":
                    # Extract GitHub repo name from identifier (e.g. github_user_repo -> user/repo)
                    repo_name = identifier.replace("github_", "")
                    # Ensure formatting is user/repo
                    if "_" in repo_name and "/" not in repo_name:
                        parts = repo_name.split("_", 1)
                        if len(parts) == 2:
                            repo_name = f"{parts[0]}/{parts[1]}"
                    data = fetch_single_github_repo(repo_name)
                else:
                    raise Exception(f"Unsupported queued item type: {item_type}")
                
                # Update item in the queue with content and proper title/tags
                conn = db_manager.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE ingestion_queue
                SET title = ?, content = ?, tags = ?, sources = ?, category = ?, status = 'pending'
                WHERE id = ?
                """, (data["title"], data["content"], json.dumps(data["tags"]), json.dumps(data["sources"]), data["category"], item_id))
                conn.commit()
                conn.close()
                print(f"[+] Successfully fetched metadata and updated queue for {identifier}.")
                processed_count += 1
                
            except Exception as e:
                err_msg = f"Failed to fetch metadata for queued item {identifier}: {e}"
                print(f"[!] Error: {err_msg}")
                db_manager.log_system_error(f"DaytimeQueue_{item_type}", err_msg, traceback.format_exc())
                db_manager.mark_item_failed(item_id, err_msg)
        else:
            # Item already has content, but it's pending (needs writing by organize_inbox)
            processed_count += 1
            
    if processed_count > 0:
        print(f"[*] Successfully processed {processed_count} queued items. Running sync pipeline...")
        trigger_sync(is_shutdown=False)
        return True
    return False

# --- Main Daemon Execution Loop ---
def main():
    parser = argparse.ArgumentParser(description="AIN Research Ingestion Daemon")
    parser.add_argument("--force", action="store_true", help="Force run the daemon even during daytime hours")
    args = parser.parse_args()

    print("=======================================================================")
    print("🌌 AIN UNIFIED MULTI-SOURCE INGESTION DAEMON INITIALIZED")
    print("=======================================================================")
    print(f"[*] Ingesting ArXiv research topics across {len(ARXIV_CATEGORIES)} categories.")
    print(f"[*] Ingesting GitHub open-source repositories across {len(GITHUB_CATEGORIES)} categories.")
    print("[*] Enforced Active Window: 10:00 PM to 07:00 AM Daily.")
    if args.force:
        print("[*] --force detected. Bypassing active time window check.")
    if GITHUB_PAT:
         print("[*] GITHUB_AGENT_PAT detected. Using authenticated GitHub sessions.")
    else:
         print("[!] Warning: No GITHUB_AGENT_PAT detected. Anonymous GitHub tier will apply.")
    print("=======================================================================")
    print("[!] Graceful Shutdown Configured: Press Ctrl+C to auto-sync and exit cleanly.")
    print("=======================================================================\n")
    
    # Initialize the Homeostatic Brain
    brain = SelfRecourseBrain()
    print("[*] Homeostatic Meta-Cognitive Engine Initialized. Ready to process vector streams.")
    
    global EXISTING_RESEARCH_TITLES
    EXISTING_RESEARCH_TITLES = load_existing_research_titles()
    print(f"[*] Loaded {len(EXISTING_RESEARCH_TITLES)} existing research titles from vault for deduplication.")
    
    arxiv_state = load_arxiv_state()
    github_state = load_github_state()
    
    arxiv_keys = list(ARXIV_CATEGORIES.keys())
    github_keys = list(GITHUB_CATEGORIES.keys())
    
    arxiv_idx = 0
    github_idx = 0
    
    new_data_ingested = False
    
    while True:
        try:
            # Active execution time-boxing check (only if not forced)
            if not args.force and not is_in_active_window():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Daemon: Current time is outside 10PM - 7AM window.")
                print("[*] Checking for high-priority user queued items first...")
                has_processed = process_daytime_queue()
                if has_processed:
                    print("[+] Completed high-priority queued items.")
                else:
                    print("[*] No pending high-priority queued items.")
                print("[*] Spin-down time reached. Executing graceful compilation and exiting...")
                trigger_sync(is_shutdown=True)
                print("[+] Complete. Exiting AIN Daemon process.")
                sys.exit(0)
                
            # Step 1: Process one ArXiv Category
            cat_name = arxiv_keys[arxiv_idx]
            cat_data = ARXIV_CATEGORIES[cat_name]
            state_entry = arxiv_state.get(cat_name, {"latest_seen_id": "", "last_run": ""})
            
            ingested = fetch_arxiv_papers(brain, cat_name, cat_data, state_entry, batch_size=20)
            if ingested:
                new_data_ingested = True
            
            arxiv_state[cat_name] = state_entry
            save_arxiv_state(arxiv_state)
            arxiv_idx = (arxiv_idx + 1) % len(arxiv_keys)
            
            time.sleep(15)
            
            # Step 2: Process one GitHub Category
            gh_cat_name = github_keys[github_idx]
            gh_query = GITHUB_CATEGORIES[gh_cat_name]
            
            last_run_date = github_state.get("last_run_date")
            current_page = github_state.get("categories", {}).get(gh_cat_name, 1)
            
            repos, err_code = fetch_github_repos(gh_cat_name, gh_query, current_page, last_run_date)
            
            if repos == "RETRY_ANON":
                print("    -> Retrying immediately without authentication...")
                repos, err_code = fetch_github_repos(gh_cat_name, gh_query, current_page, last_run_date)
                
            if repos == "RESET":
                github_state["categories"][gh_cat_name] = 1
                save_github_state(github_state)
                time.sleep(5)
                github_idx = (github_idx + 1) % len(github_keys)
                continue
                
            if err_code in [403, 429]:
                print("    -> Sleeping for 65 seconds to clear GitHub API limit limits...")
                time.sleep(65)
                continue
                
            if repos and isinstance(repos, list):
                count = process_github_repos(brain, repos, gh_cat_name)
                print(f"    -> Successfully processed {count} GitHub repositories.")
                if count > 0:
                    new_data_ingested = True
                
                if current_page >= 2 or len(repos) < 50:
                    github_state["categories"][gh_cat_name] = 1
                else:
                    github_state["categories"][gh_cat_name] = current_page + 1
                    
                save_github_state(github_state)
            
            github_idx = (github_idx + 1) % len(github_keys)
            
            if arxiv_idx == 0 and github_idx == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Daemon: Completed full round-robin cycle.")
                github_state["last_run_date"] = datetime.now().strftime("%Y-%m-%d")
                save_github_state(github_state)
                
                if new_data_ingested:
                    trigger_sync(is_shutdown=False)
                    new_data_ingested = False
            
            print("    -> Sleeping for 15 seconds to space out crawler requests...")
            time.sleep(15)
            
        except KeyboardInterrupt:
            trigger_sync(is_shutdown=True)
            print("[+] Graceful shutdown synchronization complete. Exiting AIN Daemon.")
            sys.exit(0)
        except Exception as e:
            print(f"\n[!] Unexpected AIN Daemon Loop Error: {e}")
            import traceback
            traceback.print_exc()
            print("[*] Re-triggering recovery cycle in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    main()
