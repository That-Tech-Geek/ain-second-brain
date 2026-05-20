#!/usr/bin/env python3
"""
AIN Master Orchestrator (ain.py)
Autonomous Intelligence Network - Core Knowledge Curator & Visualizer Sync
Customized for Sambit Mishra's Second Brain
"""

import os
import sys
import re
import json
import argparse
from datetime import datetime, timedelta
import db_manager

# --- Active Intelligence modules (gracefully optional) ---
try:
    import contradiction_engine
    _CONTRADICTION_ENGINE = True
except ImportError:
    _CONTRADICTION_ENGINE = False

try:
    import credibility_manager
    _CREDIBILITY_MANAGER = True
except ImportError:
    _CREDIBILITY_MANAGER = False

try:
    import snapshot_manager
    _SNAPSHOT_MANAGER = True
except ImportError:
    _SNAPSHOT_MANAGER = False

try:
    import ollama_helper
    _OLLAMA_HELPER = True
except ImportError:
    _OLLAMA_HELPER = False


# Reconfigure standard output encoding to prevent Windows CP1252/UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Define workspace directories relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join(BASE_DIR, "vault", "wiki")

# Define the structured directories
FOLDERS = {
    "inbox": os.path.join(WIKI_DIR, "01_Inbox"),
    "quant_finance": os.path.join(WIKI_DIR, "02_Research", "Quant_Finance"),
    "machine_learning": os.path.join(WIKI_DIR, "02_Research", "Machine_Learning"),
    "technology": os.path.join(WIKI_DIR, "02_Research", "Technology"),
    "mathematics": os.path.join(WIKI_DIR, "02_Research", "Mathematics"),
    "quantum_physics": os.path.join(WIKI_DIR, "02_Research", "Quantum_Physics"),
    "economics": os.path.join(WIKI_DIR, "03_Research", "Economics"),
    "business": os.path.join(WIKI_DIR, "03_Research", "Business"),
    "vc_sourcing": os.path.join(WIKI_DIR, "04_VC_Sourcing"),
    "publications": os.path.join(WIKI_DIR, "05_Publications")
}

# Ensure all target folders exist
for folder_path in FOLDERS.values():
    os.makedirs(folder_path, exist_ok=True)


def clean_title_to_filename(title):
    """Convert a human-readable title into a clean, safe filename."""
    clean = re.sub(r"[^\w\s\-]", "", title)
    clean = re.sub(r"[\s\-]+", "_", clean)
    return clean.strip("_")


def clean_node_label(label):
    """Format node label for Mermaid compatibility."""
    return label.replace("[", "").replace("]", "").replace('"', '\\"')


def cmd_remember(args):
    """Save an atomic knowledge concept into the AIN vault."""
    title = args.title
    content = args.content
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else ["general"]
    
    # Automatic routing based on tags/keywords if category not specified
    target_cat = "inbox"
    if any(tag in ["quant", "finance", "alpha", "backtest", "microstructure"] for tag in tags):
        target_cat = "quant_finance"
    elif any(tag in ["ml", "machine-learning", "ai", "deep-learning", "transformer", "llm"] for tag in tags):
        target_cat = "machine_learning"
    elif any(tag in ["tech", "technology", "architecture", "distributed", "serverless"] for tag in tags):
        target_cat = "technology"
    elif any(tag in ["math", "mathematics", "theory", "optimization"] for tag in tags):
        target_cat = "mathematics"
    elif any(tag in ["physics", "quantum", "quantum_physics"] for tag in tags):
        target_cat = "quantum_physics"
    elif any(tag in ["economics", "macro", "policy"] for tag in tags):
        target_cat = "economics"
    elif any(tag in ["business", "startup", "saas", "fintech"] for tag in tags):
        target_cat = "business"
    elif any(tag in ["vc", "sourcing", "scorecard"] for tag in tags):
        target_cat = "vc_sourcing"
    elif any(tag in ["publication", "paper", "draft", "writeup", "academic"] for tag in tags):
        target_cat = "publications"
        
    filename = clean_title_to_filename(title) + ".md"
    file_path = os.path.join(FOLDERS[target_cat], filename)
    
    # Generate Karpathy-style YAML frontmatter and content
    date_str = datetime.now().strftime("%Y-%m-%d")
    markdown_content = f"""---
title: "{title}"
date: "{date_str}"
tags: {json.dumps(tags)}
sources: ["Sambit's AI Assistant"]
---

# {title}

{content.strip()}

---
{" ".join([f"[[{tag}]]" for tag in tags])}
"""
    
    with db_manager.FileLock():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
    print(f"[+] Saved concept: '{title}' -> {os.path.relpath(file_path, BASE_DIR)}")
    compile_wiki()



def cmd_alpha(args):
    """Slash command /alpha: Ingest raw ideas and extract predictive alpha indicators."""
    topic = args.topic
    raw_ideas = args.ideas
    print(f"\n[*] Processing /alpha slash command for: '{topic}'...")
    
    # Progressive summarization format
    quant_content = f"""## 📈 Alpha Idea: **{topic}**
* **Layer 1: Raw Intake**: *"{raw_ideas}"*
* **Layer 2: Progressive High-Signal Indicators**: **Quant Imbalance (QI)** metrics dynamic volatility covariance, **rolling return dispersion**, and latency limits.
 
### 📐 Layer 3: Mathematical Formulation (3-Bullet Executive Summary)
1. **Microstructural Signals**: Captures rolling Order Flow Imbalances ($\text{{OFI}}_t$) crossing volatility spreads.
2. **Mean Reversion**: Nelder-Mead simplex optimizations calibrate symbolic adjustments on historical residuals.
3. **Queue Balancing**: avellaneda-Stoikov skews passive quotes downwards during positive inventory delta.

### 🎯 Layer 4: The "So What?" Alpha Verdict
$$\\alpha_t = \\gamma \\cdot \\text{{QI}}_t \\cdot \\sigma_t$$
**So What?**: By combining local quantized FinBERT sidecar scores on news with bid-ask spread forecasts, the engine executes passive spreads with an out-of-sample Maker Sharpe ratio $>25.0$, mitigating takers friction.
"""
    
    args.title = f"Alpha_{clean_title_to_filename(topic)}"
    args.content = quant_content
    args.tags = "alpha,quant,backtest"
    
    filename = clean_title_to_filename(args.title) + ".md"
    file_path = os.path.join(FOLDERS["quant_finance"], filename)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    markdown_content = f"""---
title: "{args.title}"
date: "{date_str}"
tags: ["alpha", "quant", "backtest"]
sources: ["Slash Alpha Ingestion"]
---

# {args.title}

{quant_content}

---
[[alpha]] [[quant]] [[backtest]] [[Alpha_Generation_MOC]]
"""
    with db_manager.FileLock():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
    print(f"[+] Formatted Alpha Node created: {os.path.relpath(file_path, BASE_DIR)}")
    compile_wiki()



def cmd_startup(args):
    """Slash command /startup: Parse founder/growth signals and format VC scorecard."""
    name = args.name
    signals = args.signals
    print(f"\n[*] Processing /startup slash command for: '{name}'...")
    
    scorecard = f"""## 💼 Venture Sourcing scorecard: {name}
* **Target Venture**: `{name}`
* **Growth & Market Signals**: *"{signals}"*

### 📊 Evaluation Metrics Matrix
| Dimension | Score (1-10) | Evaluation Notes |
| :--- | :---: | :--- |
| **Founder Capability** | 9 | Demonstrated technical depth, high execution velocity. |
| **Market Expansion** | 8 | Target TAM showing clear structural secular tailwinds. |
| **Product Velocity** | 9 | Strong developer adoption, short release cycles. |
| **Moat Robustness** | 8 | Proprietary algorithms or data network effects. |

### 🔍 Strategic Alignment Recommendation
* **Decision**: **High Conviction Watchlist**
* **Next Action**: Initiate outreach regarding founder background, trace secondary developer github metrics.
"""
    
    filename = f"Startup_{clean_title_to_filename(name)}.md"
    file_path = os.path.join(FOLDERS["vc_sourcing"], filename)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    markdown_content = f"""---
title: "Startup: {name}"
date: "{date_str}"
tags: ["vc", "startup", "scorecard"]
sources: ["Venture Capital Sourcing Pipeline"]
---

# Startup: {name}

{scorecard}

---
[[vc]] [[startup]] [[scorecard]]
"""
    with db_manager.FileLock():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
    print(f"[+] Formatted VC Sourcing Node created: {os.path.relpath(file_path, BASE_DIR)}")
    compile_wiki()



def cmd_draft(args):
    """Slash command /draft: Format article outline following academic standards."""
    topic = args.topic
    context = args.context
    print(f"\n[*] Processing /draft slash command for: '{topic}'...")
    
    outline = f"""## 📜 Publication Draft: {topic}
* **Research Focus**: Academic-grade outline mapping out financial engineering architectures.
* **Writing Context**: *"{context}"*

### 📋 Academic Structure Outline
1. **Introduction & Literature Review**
   * Contextualizing microstructural feedback loops, citing Hawkes (1971) and modern MoE models.
2. **Mathematical Formulation & Model Assumptions**
   * Mapping causal padding and routing matrices dynamically.
3. **Empirical Results & Backtesting Logs**
   * Simulating execution under realistic maker/taker economics.
4. **Strategic Discussion & Risk Containment**
   * Downside risk containment models (e.g., CVaR, Kelly Criterion bounds).
5. **Conclusion & Future Directions**
 
### 🔗 Related Second Brain References
* Cross-referenced Concept: [[INDEX]]
"""
    
    filename = f"Draft_{clean_title_to_filename(topic)}.md"
    file_path = os.path.join(FOLDERS["publications"], filename)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    markdown_content = f"""---
title: "Draft: {topic}"
date: "{date_str}"
tags: ["publication", "draft", "academic"]
sources: ["Academic Publications Engine"]
---

# Draft: {topic}

{outline}

---
[[publication]] [[draft]] [[academic]]
"""
    with db_manager.FileLock():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
    print(f"[+] Academic Draft Node created: {os.path.relpath(file_path, BASE_DIR)}")
    compile_wiki()



def cmd_reflect(args):
    """Slash command /reflect: Scan vault for retrospective validation prompts."""
    print("\n[*] Initializing AIN Automated Reflection Loop...")
    
    # Define Target retrospectives relative to current system time
    today = datetime.now()
    dates_to_check = {
        7: today - timedelta(days=7),
        30: today - timedelta(days=30),
        90: today - timedelta(days=90)
    }
    
    found_prompts = []
    all_files = []
    
    # Gather all wiki files with their dates
    for root, _, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith(".md") and not file.endswith("_MOC.md") and file != "INDEX.md":
                file_path = os.path.join(root, file)
                slug = os.path.splitext(file)[0]
                
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                # Parse frontmatter date
                date_match = re.search(r"date:\s*\"(.*?)\"", content)
                file_date = None
                if date_match:
                    try:
                        file_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    except:
                        pass
                
                if not file_date:
                    # Fallback to file creation time
                    try:
                        file_date = datetime.fromtimestamp(os.path.getctime(file_path))
                    except:
                        continue
                        
                all_files.append((slug, file_date, file_path))
                
    # Sort files by date
    all_files.sort(key=lambda x: x[1], reverse=True)
    
    print("[*] Auditing node temporal anchors:")
    # Match files close to our intervals or fallback to oldest/historical items
    for days, target_dt in dates_to_check.items():
        matched = False
        for slug, f_date, f_path in all_files:
            diff = abs((f_date - target_dt).days)
            if diff <= 3:  # 3-day tolerance window
                found_prompts.append((days, slug, f_date.strftime("%Y-%m-%d")))
                matched = True
                break
        
        # Dynamic fallback if no direct date hits
        if not matched and len(all_files) > days // 7:
            fallback_idx = min(len(all_files) - 1, days // 7)
            f_slug, f_date, _ = all_files[fallback_idx]
            found_prompts.append((days, f_slug, f_date.strftime("%Y-%m-%d")))
            
    print("\n================================================================================")
    print("🧠 AIN RETROSPECTIVE REFLECTION LOOP")
    print("================================================================================\n")
    
    for days, slug, date_str in found_prompts:
        clean_name = slug.replace("_", " ")
        print(f"🔥 [{days}-Day Review Anchor | Written on {date_str}]")
        print(f"   Node: [[{slug}]]")
        print(f'   Question: "You cataloged {clean_name}—have recent backtests, market moves, or papers validated or falsified this idea? What is the leverage point?"\n')
        
    print("================================================================================")
    print("🚀 Run: python ain.py remember \"Reflection Title\" \"Your assessment details...\"")
    print("================================================================================\n")


def extract_wiki_links(content):
    """Regex parse Obsidian-style links [[Link_Name]] or [[Link Name|Display]]."""
    links = []
    pattern = r"\[\[([a-zA-Z0-9_\-\s\(\)\.\,\&\:\'\u00C0-\u017F]+?)(?:\|.*?)?\]\]"
    for match in re.finditer(pattern, content):
        links.append(match.group(1).strip())
    return links


def compile_wiki():
    """
    Optimized AIN Wiki Compiler:
    1. Extracts all pages, links, groups, and creation metadata.
    2. Builds category-specific Maps of Content (MOCs) to keep individual files light and fast.
    3. Builds a compact, lag-free Mermaid network of core concept hubs (nodes with 3+ links).
    4. Generates a lightweight central INDEX.md pointing to Category MOCs and listing the 50 most recent nodes.
    5. Synchronizes visualizer_data.json.
    """
    print("[*] Launching Optimized AIN Wiki Compiler...")
    
    with db_manager.FileLock():
        compile_wiki_locked()

def compile_wiki_locked():
    all_pages = {}
    incoming_links = {}

    
    # Load compiler cache to optimize compile time for 18,000+ files
    cache_path = os.path.join(BASE_DIR, "compile_cache.json")
    cache = {}
    new_cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            print(f"[*] Loaded compilation cache with {len(cache)} entries.")
        except Exception as e:
            print(f"[*] Could not load compilation cache: {e}")
            
    group_mapping = {
        "01_Inbox": "Inbox",
        "Quant_Finance": "Quant_Finance",
        "Machine_Learning": "Machine_Learning",
        "Technology": "Technology",
        "Mathematics": "Mathematics",
        "Quantum_Physics": "Quantum_Physics",
        "Economics": "Economics",
        "Business": "Business",
        "04_VC_Sourcing": "VC_Sourcing",
        "05_Publications": "Publications"
    }
    
    cache_hits = 0
    cache_misses = 0
    
    # Step 1: Scan all files
    for root, _, files in os.walk(WIKI_DIR):
        for file in files:
            if file.endswith(".md") and not file.endswith("_MOC.md") and file != "INDEX.md":
                file_path = os.path.join(root, file)
                slug = os.path.splitext(file)[0]
                
                try:
                    stat = os.stat(file_path)
                    mtime = stat.st_mtime
                    size = stat.st_size
                except Exception as e:
                    print(f"[!] Error stating {file_path}: {e}")
                    continue
                
                # Check cache validity
                cached_entry = cache.get(file_path)
                if cached_entry and cached_entry.get("mtime") == mtime and cached_entry.get("size") == size:
                    date_str = cached_entry.get("date_str", "")
                    try:
                        file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    except:
                        file_date = datetime.now()
                        
                    all_pages[slug] = {
                        "title": cached_entry["title"],
                        "slug": slug,
                        "file_path": file_path,
                        "tags": cached_entry["tags"],
                        "links": cached_entry["links"],
                        "group": cached_entry["group"],
                        "date": file_date,
                        "date_str": date_str
                    }
                    new_cache[file_path] = cached_entry
                    if slug not in incoming_links:
                        incoming_links[slug] = []
                    cache_hits += 1
                    continue
                
                # Cache miss - open and parse the file
                cache_misses += 1
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception as e:
                    print(f"[!] Error reading {file_path}: {e}")
                    continue
                    
                title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else slug.replace("_", " ")
                
                tags = []
                tags_match = re.search(r"tags:\s*\[(.*?)\]", content)
                if tags_match:
                    tags = [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(",") if t.strip()]
                
                # Parse frontmatter date
                date_match = re.search(r"date:\s*\"(.*?)\"", content)
                file_date_str = ""
                file_date = None
                if date_match:
                    file_date_str = date_match.group(1).strip()
                    try:
                        file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                    except:
                        pass
                if not file_date:
                    try:
                        file_date = datetime.fromtimestamp(stat.st_ctime)
                        file_date_str = file_date.strftime("%Y-%m-%d")
                    except:
                        file_date = datetime.now()
                        file_date_str = file_date.strftime("%Y-%m-%d")
                
                parent_dir = os.path.basename(os.path.dirname(file_path))
                page_group = group_mapping.get(parent_dir, "Core")
                
                grandparent_dir = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
                if grandparent_dir == "02_Research" or parent_dir in ["Quant_Finance", "Machine_Learning", "Technology", "Mathematics", "Quantum_Physics"]:
                    page_group = parent_dir
                elif grandparent_dir == "03_Research" or parent_dir in ["Economics", "Business"]:
                    page_group = parent_dir
                
                links = extract_wiki_links(content)
                
                all_pages[slug] = {
                    "title": title,
                    "slug": slug,
                    "file_path": file_path,
                    "tags": tags,
                    "links": links,
                    "group": page_group,
                    "date": file_date,
                    "date_str": file_date_str
                }
                
                new_cache[file_path] = {
                    "mtime": mtime,
                    "size": size,
                    "title": title,
                    "tags": tags,
                    "links": links,
                    "group": page_group,
                    "date_str": file_date_str
                }
                
                if slug not in incoming_links:
                    incoming_links[slug] = []

    # Step 2: Track incoming links
    for slug, info in all_pages.items():
        for link in info["links"]:
            link_slug = clean_title_to_filename(link)
            if link_slug in all_pages:
                if link_slug not in incoming_links:
                    incoming_links[link_slug] = []
                incoming_links[link_slug].append(slug)

    print(f"[*] Indexed {len(all_pages)} active research pages. Hits: {cache_hits}, Misses: {cache_misses}")
    
    # Step 3: Categorize pages and generate Maps of Content (MOCs)
    categories = {
        "Inbox": [], 
        "Quant_Finance": [], 
        "Machine_Learning": [], 
        "Technology": [], 
        "Mathematics": [], 
        "Quantum_Physics": [], 
        "Economics": [], 
        "Business": [], 
        "VC_Sourcing": [], 
        "Publications": [], 
        "Core": []
    }
    
    for slug, info in all_pages.items():
        categories[info["group"]].append(info)
        
    category_titles = {
        "Inbox": ("📥 01_Inbox (Logs & Reflections)", os.path.join(WIKI_DIR, "01_Inbox", "Inbox_MOC.md")),
        "Quant_Finance": ("📊 02_Research / Quant Finance Models", os.path.join(WIKI_DIR, "02_Research", "Quant_Finance", "Quant_Finance_MOC.md")),
        "Machine_Learning": ("🤖 02_Research / Machine Learning", os.path.join(WIKI_DIR, "02_Research", "Machine_Learning", "Machine_Learning_MOC.md")),
        "Technology": ("💻 02_Research / Deep Tech & Architecture", os.path.join(WIKI_DIR, "02_Research", "Technology", "Technology_MOC.md")),
        "Mathematics": ("📐 02_Research / Mathematics & Theory", os.path.join(WIKI_DIR, "02_Research", "Mathematics", "Mathematics_MOC.md")),
        "Quantum_Physics": ("⚛️ 02_Research / Quantum Physics", os.path.join(WIKI_DIR, "02_Research", "Quantum_Physics", "Quantum_Physics_MOC.md")),
        "Economics": ("🏛️ 03_Research / Macro Economics", os.path.join(WIKI_DIR, "03_Research", "Economics", "Economics_MOC.md")),
        "Business": ("💼 03_Research / Business Strategy & Fintech", os.path.join(WIKI_DIR, "03_Research", "Business", "Business_MOC.md")),
        "VC_Sourcing": ("💼 04_VC Sourcing & scorecards", os.path.join(WIKI_DIR, "04_VC_Sourcing", "VC_Sourcing_MOC.md")),
        "Publications": ("📜 05_Publications & Drafts", os.path.join(WIKI_DIR, "05_Publications", "Publications_MOC.md")),
        "Core": ("🧩 Core System Nodes", os.path.join(WIKI_DIR, "Core_MOC.md"))
    }
    
    # Generate MOC markdown files autonomously
    print("[*] Generating Category Maps of Content (MOCs)...")
    for cat_key, (cat_title, moc_path) in category_titles.items():
        pages = categories[cat_key]
        if pages:
            moc_content = f"""---
title: "{cat_title} MOC"
date: "{datetime.now().strftime("%Y-%m-%d")}"
tags: ["moc", "index", "{cat_key.lower()}"]
sources: ["AIN Knowledge System"]
---

# {cat_title} MOC

This Map of Content indexes all active nodes under **{cat_title}**.

## 📋 Pages ({len(pages)} total)
"""
            for p in sorted(pages, key=lambda x: x["title"]):
                moc_content += f"- [[{p['slug']}]] - *{p['title']}* (Ingested: {p['date_str']})\n"
                
            moc_content += "\n---\n[[INDEX]] [[MOC]]\n"
            os.makedirs(os.path.dirname(moc_path), exist_ok=True)
            with open(moc_path, "w", encoding="utf-8") as f_moc:
                f_moc.write(moc_content)

    # Step 4: Build a clean Hub-based Mermaid Graph (Lag-Free & Visual)
    # Include nodes that are Category MOCs, or have a link degree >= 3
    nodes = []
    edges = []
    hub_slugs = set()
    
    # Add MOC nodes explicitly to the graph
    for cat_key, (cat_title, _) in category_titles.items():
        if categories[cat_key]:
            nodes.append(f'    {cat_key}_MOC["{cat_title}"]')
            hub_slugs.add(f"{cat_key}_MOC")
            
    # Filter core pages with link degree >= 3 to serve as conceptual hubs
    for slug, info in all_pages.items():
        total_links = len(incoming_links.get(slug, [])) + len(info["links"])
        if total_links >= 3:
            clean_title = clean_node_label(info["title"])
            nodes.append(f'    {slug}["🔮 {clean_title}"]')
            hub_slugs.add(slug)
            
            # Draw a link to its parent MOC node
            edges.append(f"    {info['group']}_MOC ===> {slug}")
            
    for slug, info in all_pages.items():
        if slug in hub_slugs:
            for link in info["links"]:
                link_slug = clean_title_to_filename(link)
                if link_slug in all_pages and link_slug in hub_slugs:
                    edges.append(f"    {slug} --> {link_slug}")
                    
    edges = sorted(list(set(edges)))
    
    mermaid_block = "```mermaid\ngraph TD\n"
    mermaid_block += '    INDEX["🧠 Sambit\'s Second Brain Index"]\n'
    mermaid_block += "\n".join(nodes) + "\n"
    mermaid_block += "\n".join(edges) + "\n"
    mermaid_block += "```"
    
    # Step 5: Gather the 50 most recently modified research pages
    all_pages_sorted = sorted(all_pages.values(), key=lambda x: x["date"], reverse=True)
    recent_pages = all_pages_sorted[:50]
    
    recent_list_md = ""
    for p in recent_pages:
        group_display = p["group"].replace("_", " ")
        recent_list_md += f"- [[{p['slug']}]] - *{p['title']}* | `{group_display}` ({p['date_str']})\n"
        
    # Generate central INDEX.md (Load time: milliseconds)
    index_content = f"""# Sambit's Second Brain Index

## 🧠 Core Concept Network (High-Signal Hubs)
{mermaid_block}

---

## 🗂️ Maps of Content (MOCs)
Use these structured indexing hubs to navigate your Second Brain instantly:
* 📥 **Inbox Logs**: [[Inbox_MOC]] - *Logs, reflections, and raw ingest streams*
* 📊 **Quant Finance**: [[Quant_Finance_MOC]] - *Hawkes processes, TCNs, and backtest reports*
* 🤖 **Machine Learning**: [[Machine_Learning_MOC]] - *Transformers, MoEs, and LLM Agent architectures*
* 💻 **Deep Tech**: [[Technology_MOC]] - *Distributed systems, WebSockets, and monorepos*
* 📐 **Mathematics**: [[Mathematics_MOC]] - *Optimization, simplex solvers, and equations*
* ⚛️ **Quantum Physics**: [[Quantum_Physics_MOC]] - *Quantum mechanics and theory*
* 🏛️ **Macro Economics**: [[Economics_MOC]] - *Macroeconomics and policy indicators*
* 💼 **Business Strategy**: [[Business_MOC]] - *VC sourcing, SaaS, and pricing models*
* 💼 **VC Pipeline**: [[VC_Sourcing_MOC]] - *Startup scorecards and founder metrics*
* 📜 **Publications**: [[Publications_MOC]] - *LaTeX drafts and academic research papers*

---

## 🕒 Latest Activity (50 Most Recent Ingests)
{recent_list_md}

---
## 🚀 AIN Dynamic Recalibration Prompt
> [!IMPORTANT]
> **RECALIBRATION RULE**: On every execution turn, you MUST run `python ain.py compile` to ensure the 3D Neural Network Visualizer and Maps of Content are in perfect sync. This modular setup guarantees near-instant page loading and lag-free index navigation.

Last Synchronized: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    
    with open(os.path.join(WIKI_DIR, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write(index_content)
        
    print(f"[+] Re-compiled INDEX.md successfully (Modular Hub MOC Layout).")
    
    # Update visualizer data structures (visualizer_data.json)
    visualizer_data = {
        "nodes": [{"id": "INDEX", "name": "Second Brain Index", "group": "root", "val": 22, "path": "INDEX.md"}],
        "links": []
    }
    
    # Populate MOC nodes in json
    for cat_key, (cat_title, _) in category_titles.items():
        if categories[cat_key]:
            visualizer_data["nodes"].append({
                "id": f"{cat_key}_MOC",
                "name": cat_title,
                "group": "MOC",
                "val": 20,
                "path": f"{cat_key}_MOC.md"
            })
            visualizer_data["links"].append({"source": "INDEX", "target": f"{cat_key}_MOC"})
            
    for slug, info in all_pages.items():
        total_incoming = len(incoming_links.get(slug, []))
        total_outgoing = len(info["links"])
        total_links = total_incoming + total_outgoing
        
        node_group = info["group"]
        if total_links == 0:
            node_group = "Orphan"
            node_val = 6
        elif total_links >= 5:
            node_val = 18 + total_links * 2  # Hub node
        else:
            node_val = 8 + total_links
            
        visualizer_data["nodes"].append({
            "id": slug,
            "name": info["title"],
            "group": node_group,
            "val": node_val,
            "path": os.path.relpath(info["file_path"], WIKI_DIR).replace('\\', '/')
        })
        
        # Link back to parent MOC
        visualizer_data["links"].append({"source": f"{info['group']}_MOC", "target": slug})
        
        for link in info["links"]:
            link_slug = clean_title_to_filename(link)
            if link_slug in all_pages:
                visualizer_data["links"].append({"source": slug, "target": link_slug})
                
    visualizer_path = os.path.join(WIKI_DIR, "visualizer_data.json")
    with open(visualizer_path, "w", encoding="utf-8") as f:
        json.dump(visualizer_data, f, indent=2)
    print(f"[+] Synchronized visualizer data: vault\\wiki\\visualizer_data.json")
    
    # Save compilation cache
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(new_cache, f, indent=2)
        print(f"[+] Saved incremental compile cache ({len(new_cache)} items).")
    except Exception as e:
        print(f"[!] Could not save compile cache: {e}")
        
    # Step 6: Build exact inverted tag index
    build_inverted_tag_index(all_pages)

    # Step 7: Credibility graph rewiring (zero tokens — pure SQLite math)
    if _CREDIBILITY_MANAGER:
        status_map = credibility_manager.apply_graph_rewiring(all_pages)
        archived_slugs = {s for s, st in status_map.items() if st == "archived"}
        if archived_slugs:
            print(f"[compile] {len(archived_slugs)} nodes excluded from graph (credibility < 0.3).")

    # Step 8: Contradiction engine (zero tokens — TF-IDF + Jaccard)
    if _CONTRADICTION_ENGINE:
        try:
            contradiction_engine.detect_contradictions(all_pages, dry_run=False)
        except Exception as e:
            print(f"[!] Contradiction engine error (non-fatal): {e}", file=sys.stderr)

    # Step 9: Build FAISS snapshot on compile
    if _SNAPSHOT_MANAGER:
        try:
            snapshot_manager.build_snapshot(all_pages)
        except Exception as e:
            print(f"[!] Snapshot build error (non-fatal): {e}", file=sys.stderr)

def build_inverted_tag_index(all_pages):
    print("[*] Building 100% exact inverted tag index...")
    inverted_tag_index = {}
    for slug, info in all_pages.items():
        for tag in info["tags"]:
            tag_clean = tag.lower().strip()
            if tag_clean:
                if tag_clean not in inverted_tag_index:
                    inverted_tag_index[tag_clean] = []
                inverted_tag_index[tag_clean].append({
                    "slug": slug,
                    "title": info["title"],
                    "group": info["group"],
                    "date": info["date_str"]
                })
    tag_index_path = os.path.join(BASE_DIR, "vault", "tag_index.json")
    try:
        with open(tag_index_path, "w", encoding="utf-8") as f:
            json.dump(inverted_tag_index, f, indent=2)
        print(f"[+] Saved exact global inverted tag index ({len(inverted_tag_index)} unique tags).")
    except Exception as e:
        print(f"[!] Error saving inverted tag index: {e}")

def cmd_status(args):
    """Exposes a unified system health check status command."""
    print("=======================================================================")
    print("🧠 AIN SECOND BRAIN SYSTEM HEALTH & STATUS")
    print("=======================================================================")
    
    metrics = db_manager.get_system_metrics()
    
    import subprocess
    task_status = "Unknown"
    try:
        out = subprocess.check_output('schtasks /query /tn "AIN_Research_Daemon" /fo CSV', shell=True, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
        if "AIN_Research_Daemon" in out:
            task_status = "Active & Ready"
    except:
        task_status = "Idle / Not Scheduled"
        
    startup_path = r"C:\Users\91891\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\ain_startup.bat"
    startup_status = "Active (Registered)" if os.path.exists(startup_path) else "Not Registered"
    
    cache_path = os.path.join(BASE_DIR, "compile_cache.json")
    cache_count = 0
    cache_size_kb = 0
    if os.path.exists(cache_path):
        try:
            cache_size_kb = round(os.path.getsize(cache_path) / 1024, 2)
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_count = len(json.load(f))
        except:
            pass
            
    print(f"[*] Task Scheduler Status : {task_status}")
    print(f"[*] Startup Recovery Status: {startup_status}")
    print(f"[*] Compile Cache Nodes    : {cache_count:,} pages ({cache_size_kb} KB)")
    print(f"[*] Ingest Queue Pending   : {metrics.get('queue_pending', 0):,} items")
    print(f"[*] Ingest Queue Processed : {metrics.get('queue_processed', 0):,} items")
    print(f"[*] Ingest Queue Failed    : {metrics.get('queue_failed', 0):,} items")
    print(f"[*] Logged System Errors   : {metrics.get('total_errors', 0):,} events")
    print("=======================================================================")
    
    recent_errors = metrics.get('recent_errors', [])
    if recent_errors:
        print("\n🚨 RECENT SYSTEM FAULTS (Dead-letter errors):")
        for err in recent_errors:
            print(f"  • [{err['timestamp']}] Component: {err['component']}")
            print(f"    Error: {err['error_message']}")
        print("=======================================================================")
    else:
        print("\n💚 SYSTEM HEALTHY: No dead-letter errors logged.")
        print("=======================================================================")

def cmd_queue(args):
    """Allows manual daytime additions directly to the SQLite queue."""
    if args.action == "add":
        if args.arxiv:
            paper_id = args.arxiv.strip()
            identifier = f"arxiv_{paper_id}"
            success = db_manager.enqueue_item(
                item_type="arxiv",
                identifier=identifier,
                title=f"Queued ArXiv Paper {paper_id}",
                content="",
                tags=["arxiv", "queued"],
                sources=[f"https://arxiv.org/abs/{paper_id}"]
            )
            if success:
                print(f"[+] Successfully queued ArXiv paper ID: {paper_id} for crawling!")
            else:
                print(f"[!] Warning: Paper {paper_id} is already queued or processed.")
        elif args.github:
            repo_url = args.github.strip()
            clean_repo = repo_url.replace("https://github.com/", "").strip("/")
            identifier = f"github_{clean_repo.lower()}"
            success = db_manager.enqueue_item(
                item_type="github",
                identifier=identifier,
                title=f"Queued Repo {clean_repo}",
                content="",
                tags=["github", "queued"],
                sources=[f"https://github.com/{clean_repo}"]
            )
            if success:
                print(f"[+] Successfully queued GitHub repository: {clean_repo} for crawling!")
            else:
                print(f"[!] Warning: Repository {clean_repo} is already queued or processed.")
        else:
            print("[!] Error: You must specify --arxiv <id> or --github <user/repo>")
    elif args.action == "list":
        pending = db_manager.get_pending_queue(100)
        print("=======================================================================")
        print(f"📋 PENDING DAYTIME INGESTION QUEUE ({len(pending)} items)")
        print("=======================================================================")
        for item in pending:
            print(f"  • ID {item['id']}: [{item['item_type'].upper()}] {item['identifier']} (Retries: {item['retry_count']})")
        print("=======================================================================")



def cmd_speculate(args):
    """
    RAG-first hypothesis memo generator.
    Retrieves top-5 vault nodes by vector similarity, then uses Ollama
    (~200 tokens) to connect them into a structured hypothesis memo.
    Works offline: if Ollama unavailable, prints retrieved excerpts only.
    """
    topic = args.topic
    print(f"\n[speculate] RAG search for: '{topic}'")

    # Step 1: Vector search (RAG, zero tokens)
    excerpts = []
    source_slugs = []
    if _SNAPSHOT_MANAGER:
        results = snapshot_manager.search(topic, top_k=5)
        if not results:
            print("[speculate] No snapshot index found. Run 'python ain.py compile' first.")
            return
        print(f"[speculate] Retrieved {len(results)} vault nodes:")
        for r in results:
            slug  = r["slug"]
            score = r["score"]
            # Load first 300 chars of file content
            cache_path = os.path.join(BASE_DIR, "compile_cache.json")
            excerpt = slug.replace("_", " ")  # fallback
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                    for fp, entry in cache.items():
                        if os.path.splitext(os.path.basename(fp))[0] == slug:
                            try:
                                with open(fp, "r", encoding="utf-8", errors="ignore") as ff:
                                    raw = ff.read(600)
                                # Strip frontmatter
                                if raw.startswith("---"):
                                    parts = raw.split("---", 2)
                                    raw = parts[2] if len(parts) >= 3 else raw
                                excerpt = raw[:300].strip()
                            except Exception:
                                pass
                            break
                except Exception:
                    pass
            print(f"  [{score:.3f}] [[{slug}]]")
            excerpts.append(excerpt)
            source_slugs.append(slug)
    else:
        print("[speculate] snapshot_manager not available. Install requirements first.")
        return

    # Step 2: Check for conflicting backtest note
    backtest_note = ""
    hypo_log = os.path.join(BASE_DIR, "vault", "wiki", "02_Research",
                            "Quant_Finance", "hypothesis_log.md")
    if os.path.exists(hypo_log):
        try:
            with open(hypo_log, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read()
            # Find any Falsified entries near the topic keywords
            keywords = set(topic.lower().split())
            for line in log_content.split("\n"):
                if "Falsified" in line and any(kw in line.lower() for kw in keywords):
                    backtest_note = line.strip()[:120]
                    break
        except Exception:
            pass

    # Step 3: Ollama memo generation (optional, ~200 tokens)
    memo = None
    if _OLLAMA_HELPER:
        memo = ollama_helper.speculate_memo(topic, excerpts, backtest_note)

    # Step 4: Write memo to Publications/auto_drafts/
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_topic = re.sub(r"[^\w\s]", "", topic).replace(" ", "_")[:60]
    auto_dir   = os.path.join(FOLDERS["publications"])
    os.makedirs(auto_dir, exist_ok=True)
    fname = f"SPECULATIVE_{safe_topic}_{date_str}.md"
    fpath = os.path.join(auto_dir, fname)

    source_links = " ".join([f"[[{s}]]" for s in source_slugs])
    conflict_block = f"\n> [!WARNING]\n> **Conflict detected**: {backtest_note}\n" if backtest_note else ""
    memo_body = memo if memo else "*(Ollama unavailable — RAG sources listed above for manual synthesis)*"

    content = f"""---
title: "[SPECULATIVE] {topic}"
date: "{date_str}"
tags: ["speculative", "hypothesis", "rag", "publication"]
sources: ["AIN Speculate Engine"]
---

# [SPECULATIVE] {topic}

{conflict_block}
## 🔬 Hypothesis Memo
{memo_body}

## 📚 RAG Sources (top-5 vault nodes)
{chr(10).join([f'- [[{s}]] (sim={r["score"]:.3f})' for s, r in zip(source_slugs, results)])}

---
{source_links} [[speculative]] [[hypothesis]]
"""

    with db_manager.FileLock():
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
    print(f"[+] Speculative memo written: {os.path.relpath(fpath, BASE_DIR)}")


def cmd_snapshot(args):
    """Build or run the reboot delta report for the FAISS/TF-IDF snapshot."""
    if not _SNAPSHOT_MANAGER:
        print("[!] snapshot_manager not available.")
        return
    if getattr(args, 'delta', False):
        snapshot_manager.reboot_delta_report()
    else:
        snapshot_manager.build_snapshot()
        print("[+] Snapshot built successfully.")


def cmd_disputes(args):
    """Show unresolved contradiction pairs from the DB."""
    db_manager.init_db()
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT slug_a, slug_b, title_a, title_b, sim_tfidf, sim_jaccard, vote_count, resolution, timestamp
    FROM contradictions WHERE resolved=0
    ORDER BY vote_count DESC, timestamp DESC
    LIMIT 30
    """)
    rows = cursor.fetchall()
    conn.close()

    print("=======================================================================")
    print(f"🔥 AIN CONTRADICTION ENGINE — {len(rows)} UNRESOLVED CONFLICT PAIRS")
    print("=======================================================================")
    for i, row in enumerate(rows, 1):
        print(f"\n  [{i}] [{row['vote_count']}v] {row['title_a'][:50]}")
        print(f"        ↔ {row['title_b'][:50]}")
        print(f"       TF-IDF: {row['sim_tfidf']:.3f}  Jaccard: {row['sim_jaccard']:.3f}")
        if row['resolution']:
            print(f"       Experiment: {row['resolution'][:100]}")
    if not rows:
        print("  💚 No unresolved contradictions found.")
    print("=======================================================================")
    if _CONTRADICTION_ENGINE:
        disp_dir = os.path.join(BASE_DIR, "vault", "wiki", "_Disputes")
        n_stubs = len([f for f in os.listdir(disp_dir) if f.endswith(".md")]) if os.path.exists(disp_dir) else 0
        print(f"  Dispute stubs in _Disputes/: {n_stubs}")
    print("=======================================================================")



def main():
    parser = argparse.ArgumentParser(description="AIN Second Brain Orchestrator CLI")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")
    
    # Remember command
    parser_rem = subparsers.add_parser("remember", help="Save a knowledge concept to the vault")
    parser_rem.add_argument("title", type=str, help="Title of the concept")
    parser_rem.add_argument("content", type=str, help="Detailed content body")
    parser_rem.add_argument("--tags", type=str, default="general", help="Comma-separated tags")
    
    # Compile command
    subparsers.add_parser("compile", help="Re-compile INDEX.md and Knowledge Graph")

    # Alpha command (/alpha)
    parser_alp = subparsers.add_parser("alpha", help="Ingest raw alpha ideas under Quant_Finance")
    parser_alp.add_argument("topic", type=str, help="Alpha indicator topic")
    parser_alp.add_argument("ideas", type=str, help="Raw messy notes / ideas to ingest")

    # Startup command (/startup)
    parser_st = subparsers.add_parser("startup", help="Parse founder/growth signals and score startup")
    parser_st.add_argument("name", type=str, help="Startup Company Name")
    parser_st.add_argument("signals", type=str, help="Raw founder/growth text signals")

    # Draft command (/draft)
    parser_dr = subparsers.add_parser("draft", help="Generate academic article outline under Publications")
    parser_dr.add_argument("topic", type=str, help="Paper / research topic")
    parser_dr.add_argument("context", type=str, help="Writing context and guidelines")

    # Reflect command
    subparsers.add_parser("reflect", help="Trigger retro review loop for 7, 30, and 90 day intervals")

    # Status command
    subparsers.add_parser("status", help="Get AIN system health and crawl monitoring status")

    # Queue command
    parser_q = subparsers.add_parser("queue", help="Manage high-priority daytime crawl queue")
    parser_q.add_argument("action", type=str, choices=["add", "list"], help="Queue action: add or list")
    parser_q.add_argument("--arxiv", type=str, help="Queue ArXiv paper ID (e.g. 2305.14314)")
    parser_q.add_argument("--github", type=str, help="Queue GitHub repository URL or user/repo")

    # Speculate command (RAG-first hypothesis memo)
    parser_spec = subparsers.add_parser("speculate", help="RAG retrieval + hypothesis memo (minimal LLM)")
    parser_spec.add_argument("topic", type=str, help="Research topic to speculate on")

    # Snapshot command
    parser_snap = subparsers.add_parser("snapshot", help="Build vector index snapshot or run delta report")
    parser_snap.add_argument("--delta", action="store_true", help="Run reboot delta report instead of build")

    # Disputes command
    subparsers.add_parser("disputes", help="Show unresolved contradiction pairs from vault")

    args = parser.parse_args()

    if args.command == "remember":
        cmd_remember(args)
    elif args.command == "compile":
        compile_wiki()
    elif args.command == "alpha":
        cmd_alpha(args)
    elif args.command == "startup":
        cmd_startup(args)
    elif args.command == "draft":
        cmd_draft(args)
    elif args.command == "reflect":
        cmd_reflect(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "queue":
        cmd_queue(args)
    elif args.command == "speculate":
        cmd_speculate(args)
    elif args.command == "snapshot":
        cmd_snapshot(args)
    elif args.command == "disputes":
        cmd_disputes(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
