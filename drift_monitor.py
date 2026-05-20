"""
market_monitor.py — Market drift monitor with Sharpe alert + feature suggestion.

Pulls NIFTY50 data via yfinance (caches locally to vault/assets/).
Computes 20-day rolling Sharpe on a simple mean-reversion model.
On drift (Sharpe < threshold): writes inbox alert, optionally emails.
Ollama used ONLY for replacement feature naming (~100 tokens) when drift detected.
"""

import os
import sys
import json
import time
import smtplib
import traceback
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import numpy as np

import db_manager
import ollama_helper

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR   = os.path.join(BASE_DIR, "vault")
ASSETS_DIR  = os.path.join(VAULT_DIR, "assets")
WIKI_DIR    = os.path.join(VAULT_DIR, "wiki")
INBOX_DIR   = os.path.join(WIKI_DIR, "01_Inbox")
PARAMS_FILE = os.path.join(ASSETS_DIR, "model_params.json")
OHLCV_CACHE = os.path.join(ASSETS_DIR, "nifty50_cache.csv")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(INBOX_DIR,  exist_ok=True)

SHARPE_THRESHOLD   = 2.0    # Alert if rolling Sharpe drops below this
LOOKBACK_DAYS      = 20     # Rolling window
TICKER             = "^NSEI" # NIFTY 50 index

# Default simple mean-reversion model params (override via model_params.json)
DEFAULT_PARAMS = {
    "rsi_period":   14,
    "rsi_buy":      35,
    "rsi_sell":     65,
    "atr_period":   14,
    "holding_days":  3,
}


def _load_params() -> dict:
    if os.path.exists(PARAMS_FILE):
        try:
            with open(PARAMS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PARAMS


def _save_params(params: dict):
    os.makedirs(os.path.dirname(PARAMS_FILE), exist_ok=True)
    with open(PARAMS_FILE, "w") as f:
        json.dump(params, f, indent=2)


def fetch_ohlcv(ticker: str = TICKER, days: int = 60, use_cache: bool = True) -> "pd.DataFrame | None":
    """Download OHLCV data via yfinance; cache to disk."""
    try:
        import pandas as pd
        import yfinance as yf

        if use_cache and os.path.exists(OHLCV_CACHE):
            try:
                df = pd.read_csv(OHLCV_CACHE, index_col=0, parse_dates=True)
                df.index.name = "Date"
                last_date = df.index[-1].date()
                if (datetime.now().date() - last_date).days < 1:
                    print(f"[market] Using cached OHLCV ({len(df)} rows, last: {last_date})")
                    return df
            except Exception:
                pass  # Fall through to fresh download

        print(f"[market] Fetching {days}d OHLCV for {ticker}...")
        end   = datetime.now()
        start = end - timedelta(days=days + 10)  # buffer for weekends
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)

        if df is None or df.empty:
            print(f"[market] yfinance returned empty data for {ticker}.")
            return None

        df.index.name = "Date"
        df.to_csv(OHLCV_CACHE)
        print(f"[market] Downloaded {len(df)} rows. Cached to {OHLCV_CACHE}")
        return df

    except ImportError:
        print("[market] yfinance not installed. Run: pip install yfinance", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[market] OHLCV fetch failed: {e}", file=sys.stderr)
        return None


def _compute_rsi(close, period: int = 14):
    """Pure numpy RSI computation (no ta-lib dependency)."""
    delta  = np.diff(close)
    gain   = np.where(delta > 0, delta, 0.0)
    loss   = np.where(delta < 0, -delta, 0.0)
    avg_g  = np.convolve(gain, np.ones(period)/period, mode="valid")
    avg_l  = np.convolve(loss, np.ones(period)/period, mode="valid")
    rs     = np.where(avg_l == 0, 100.0, avg_g / avg_l)
    rsi    = 100 - (100 / (1 + rs))
    return rsi


def _compute_atr(high, low, close, period: int = 14):
    """Pure numpy ATR computation."""
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:]  - close[:-1])
        )
    )
    atr = np.convolve(tr, np.ones(period)/period, mode="valid")
    return atr


def run_model(df, params: dict) -> "pd.Series":
    """
    Simple RSI mean-reversion model. Returns daily returns series.
    """
    import pandas as pd

    # yfinance >=0.2.x returns MultiIndex columns — flatten them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close  = df["Close"].values.squeeze().astype(float)
    high   = df["High"].values.squeeze().astype(float)
    low    = df["Low"].values.squeeze().astype(float)

    rsi    = _compute_rsi(close, params["rsi_period"])
    atr    = _compute_atr(high, low, close, params["atr_period"])
    min_len = min(len(rsi), len(atr))

    # Align series
    rsi = rsi[-min_len:]
    close_aligned = close[-(min_len+1):-1]
    next_close    = close[-(min_len):]

    positions = np.zeros(min_len)
    for i in range(min_len):
        if rsi[i] < params["rsi_buy"]:
            positions[i] = 1    # long
        elif rsi[i] > params["rsi_sell"]:
            positions[i] = -1   # short

    pct_returns = np.diff(next_close) / next_close[:-1]
    strat_returns = positions[:-1] * pct_returns

    return pd.Series(strat_returns, name="strategy_returns")


def compute_rolling_sharpe(returns, window: int = LOOKBACK_DAYS) -> float:
    """Annualised Sharpe on a rolling window."""
    if len(returns) < window:
        return 0.0
    recent = returns.values[-window:]
    mu     = np.mean(recent)
    sigma  = np.std(recent)
    if sigma == 0:
        return 0.0
    return float((mu / sigma) * np.sqrt(252))


def grid_search_params(df, base_params: dict) -> dict:
    """
    Fast local grid search on a 20-day window to find better params.
    Returns best params dict.
    """
    import pandas as pd

    best_sharpe = -np.inf
    best_params = base_params.copy()

    rsi_buys  = [25, 30, 35, 40]
    rsi_sells = [60, 65, 70, 75]

    for rb in rsi_buys:
        for rs in rsi_sells:
            if rb >= rs:
                continue
            candidate = base_params.copy()
            candidate["rsi_buy"]  = rb
            candidate["rsi_sell"] = rs
            try:
                rets = run_model(df, candidate)
                sh   = compute_rolling_sharpe(rets, window=LOOKBACK_DAYS)
                if sh > best_sharpe:
                    best_sharpe = sh
                    best_params = candidate
            except Exception:
                pass

    print(f"[market] Grid search complete. Best Sharpe: {best_sharpe:.2f} with params: {best_params}")
    return best_params


def _write_drift_alert(current_sharpe: float, new_params: dict,
                       feature_suggestions: str | None, dry_run: bool = False):
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"drift_alert_{date_str}.md"
    alert_path = os.path.join(INBOX_DIR, filename)

    sug_md = (
        f"\n## 💡 Replacement Feature Suggestions (AI)\n{feature_suggestions}"
        if feature_suggestions else
        "\n## 💡 Replacement Feature Suggestions\n*(Ollama unavailable — run manually)*"
    )

    content = f"""---
title: "Drift Alert — {date_str}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
tags: ["drift", "market", "alert", "model"]
sources: ["AIN Market Monitor"]
---

# 🚨 Model Drift Alert

**Detected at**: {datetime.now().strftime('%Y-%m-%d %H:%M')}  
**Current Rolling Sharpe ({LOOKBACK_DAYS}d)**: {current_sharpe:.3f} *(threshold: {SHARPE_THRESHOLD})*  
**Status**: Below acceptable threshold — drift detected.

## 🔧 Auto-Tuned Parameters
```json
{json.dumps(new_params, indent=2)}
```
{sug_md}

## ⚡ Recommended Actions
1. Review `vault/assets/model_params.json` with suggested params above
2. Run `python market_monitor.py --backtest` to validate new params on 60d window
3. If validated, copy to `model_params.json` and commit

---
[[drift_alert]] [[model]] [[market_monitor]]
"""

    if dry_run:
        print(f"[market][dry-run] Would write drift alert to: {filename}")
        print(f"  Sharpe: {current_sharpe:.3f}, new params: {new_params}")
        return

    with open(alert_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[market] Drift alert written: {alert_path}")

    # Log to SQLite
    try:
        conn = db_manager.get_db_connection()
        conn.execute(
            "INSERT INTO system_errors (component, error_message, traceback) VALUES (?, ?, ?)",
            ("MarketMonitor", f"Drift detected: Sharpe={current_sharpe:.3f}", "")
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    # Optional email alert
    _try_send_email(f"[AIN] Model Drift Alert: Sharpe={current_sharpe:.3f}", content)


def _try_send_email(subject: str, body: str):
    """Send email if SMTP env vars are configured."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_to   = os.environ.get("SMTP_TO", smtp_user)

    if not (smtp_host and smtp_user and smtp_pass):
        return  # Not configured — silent skip

    try:
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"]    = smtp_user
        msg["To"]      = smtp_to
        with smtplib.SMTP_SSL(smtp_host, 465, timeout=10) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, smtp_to, msg.as_string())
        print(f"[market] Drift alert emailed to {smtp_to}.")
    except Exception as e:
        print(f"[market] Email failed (SMTP error): {e}", file=sys.stderr)


def run(dry_run: bool = False):
    """Full monitor cycle."""
    print(f"\n[market] === Market Monitor Cycle {datetime.now().strftime('%H:%M:%S')} ===")

    params = _load_params()
    df     = fetch_ohlcv(TICKER, days=60)

    if df is None or len(df) < LOOKBACK_DAYS + 5:
        print("[market] Insufficient data. Skipping.")
        return

    try:
        returns = run_model(df, params)
        sharpe  = compute_rolling_sharpe(returns, window=LOOKBACK_DAYS)
        print(f"[market] Rolling Sharpe ({LOOKBACK_DAYS}d): {sharpe:.3f}")

        if dry_run:
            print(f"[market][dry-run] Sharpe={sharpe:.3f} (threshold={SHARPE_THRESHOLD})")
            if sharpe < SHARPE_THRESHOLD:
                print("[market][dry-run] Would trigger drift alert + grid search.")
            return

        if sharpe < SHARPE_THRESHOLD:
            print(f"[market] ⚠️  Sharpe {sharpe:.3f} < {SHARPE_THRESHOLD}. Triggering drift response...")

            # Grid search for better params
            new_params = grid_search_params(df, params)

            # Ask Ollama for feature suggestions
            failed = [k for k, v in {
                "RSI": params.get("rsi_period", 14),
                "ATR": params.get("atr_period", 14)
            }.items()]
            feature_suggestions = ollama_helper.suggest_replacement_features(failed)

            _write_drift_alert(sharpe, new_params, feature_suggestions, dry_run=dry_run)

            # Save new params as candidate (don't overwrite production params automatically)
            candidate_path = os.path.join(
                ASSETS_DIR,
                f"candidate_params_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            )
            with open(candidate_path, "w") as f:
                json.dump({"sharpe": sharpe, "params": new_params}, f, indent=2)
            print(f"[market] Candidate params saved: {candidate_path}")
        else:
            print(f"[market] ✅ Model healthy. Sharpe {sharpe:.3f} ≥ {SHARPE_THRESHOLD}.")

    except Exception as e:
        print(f"[market] Error in run_model: {e}", file=sys.stderr)
        traceback.print_exc()


# --- CLI ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AIN Market Monitor")
    parser.add_argument("--dry-run",  action="store_true", help="Compute Sharpe without writing alert")
    parser.add_argument("--backtest", action="store_true", help="Run full 60d backtest and print metrics")
    args = parser.parse_args()

    if args.backtest:
        params = _load_params()
        df     = fetch_ohlcv(TICKER, days=60, use_cache=False)
        if df is not None:
            rets = run_model(df, params)
            sh   = compute_rolling_sharpe(rets, window=20)
            ann_ret = float(rets.mean() * 252)
            print(f"Annualised Return : {ann_ret:.2%}")
            print(f"Rolling Sharpe 20d: {sh:.3f}")
    else:
        run(dry_run=args.dry_run)
