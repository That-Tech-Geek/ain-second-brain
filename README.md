# AIN Second Brain

An **Autonomous Intelligence Network (AIN)** designed for personal knowledge graphs. This system scales up to 19k+ nodes natively while running locally, keeping tokens to an absolute minimum via statistical pre-processing.

## Features
- **Token-Free Contradiction Engine**: Uses a 3-Voter ensemble (TF-IDF, Jaccard, Tag Disjointness) with Reinforcement Learning recalibration.
- **Hypothesis Daemon**: Extracts claims from papers, auto-writes backtest stubs, executes them sandboxed, and dynamically updates source credibility scores (0.0 to 1.0).
- **Market Drift Monitor**: Constantly tracks financial models and triggers auto-tuning via grid-search when Sharpe drops.
- **Offline First**: All heavy lifting uses `scikit-learn` and `faiss`. When an LLM is needed, it defaults to a local `Ollama` instance.

## One-Line Install
```bash
pip install -e .
```

## Quick Start
```bash
# Compile and index existing Markdown vault
python ain.py compile

# Look for contradicting claims across your entire vault
python ain.py disputes

# View running systems
python ain.py status
```

## 3-Minute Video Demo Script
To verify the system end-to-end:
1. Show the OS reboot. The `startup/ain_startup.bat` triggers automatically.
2. Open terminal and run `python contradiction_voter.py --count`. Watch 1.5k+ contradictions get flagged in < 2 seconds.
3. Open `_Disputes/` and show the markdown auto-generated for a conflict. Run `python contradiction_voter.py --recalibrate` to show the RL weight shift.
4. Run `python drift_monitor.py --backtest` to see the live financial drift metrics.

## Artifacts included in this repo
- `voting_contradiction.py`: Core algorithm with RL recalibration.
- `docs/run_log_30d.csv`: 30-day autonomous benchmark.
- `docs/drift_alerts_log.json`: Trading model self-monitoring traces.
- `docs/hypothesis_test_TCN_vs_Transformer.md`: Falsification proof.
- `BENCHMARKS.md`: Performance and cost evaluations vs frontier labs.

## License
MIT License
