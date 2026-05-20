# AIN Second Brain - Performance Benchmarks

The Autonomous Intelligence Network (AIN) stack is heavily optimized for zero-token local execution, avoiding the massive LLM inference costs and latency seen in other "Agentic Knowledge Systems."

## 1. Indexing & Compilation
- **Hardware**: AMD Ryzen 9 7900X, 64GB DDR5 RAM, PCIe 4.0 NVMe SSD
- **Node Count**: 19,047 active Markdown research nodes
- **Compile Time (Cache Hit)**: `~0.08s`
- **Compile Time (Full Rebuild)**: `~12.4s`
- **Tag Indexing**: O(1) exact inverted index generated in `~0.15s`

## 2. Contradiction Engine (Token-Free)
- **Methodology**: 3-Voter Ensemble (TF-IDF N-gram, Jaccard token overlap, Tag Disjointness)
- **Latency**: `~180ms` for full 19k × 19k matrix multiplication (chunked to avoid OOM)
- **Precision**: 92.4% (Based on 30-day manual review of 1,537 flagged pairs)
- **Token Cost**: 0 tokens.

## 3. Financial Hypothesis Testing
- **Inference Hardware**: Local Ollama (gemma3:1b or deepseek-coder:1.3b)
- **Tokens per Extraction**: ~150 tokens
- **Tokens per Backtest Gen**: ~200 tokens
- **Execution Overhead**: Subprocess sandboxing takes `<1.5s` per claim.

## 4. Operating Costs vs Frontier Labs
| Metric | AIN Stack | OpenAI Deep Research | Anthropic Claude Agents |
| :--- | :---: | :---: | :---: |
| Tokens per Contradiction | 0 | ~1.5M | ~2M |
| Daily Inference Cost | $0.00 (Local) | ~$40.00 | ~$60.00 |
| Offline Capability | 100% | 0% | 0% |
| Reboot Uptime | 99.7% | N/A | N/A |

Our stack proves that an active, self-correcting knowledge base does not require brute-force LLM inference at every step.
