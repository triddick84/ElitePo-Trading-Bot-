#!/usr/bin/env python3
"""
Iter 67 — Default strategy evaluation per timeframe.

Backtests every candidate strategy for each TF on EURUSD_OTC (3-day window),
ranks by composite score, and prints/saves the winners for use as defaults.
"""
import json
import os
import sys
import time
import urllib.request

API = os.environ.get("API_URL", "http://localhost:8001")

CANDIDATES_BY_TF = {
    "5s": [
        ("deep_confluence", "5s"),
        ("momentum_buster", "5s"),
        ("5s_ema20_pullback_reversal", "5s"),
        ("5s_heikin_fractal", "5s"),
        ("5s_fast_supertrend_catch", "5s"),
        ("5s_momentum_breakout", "5s"),
        ("5s_enhanced_breakout", "5s"),
        ("5s_price_action", "5s"),
        ("hybrid", "5s"),
    ],
    "15s": [
        ("deep_confluence", "15s"),
        ("momentum_buster", "15s"),
        ("15s_ema_cascade", "15s"),
        ("15s_ema_crossover", "15s"),
        ("15s_rsi_stochastic", "15s"),
        ("15s_triple_confluence", "15s"),
        ("hybrid", "15s"),
    ],
    "30s": [
        ("deep_confluence", "30s"),
        ("momentum_buster", "30s"),
        ("30s_bollinger_rsi", "30s"),
        ("30s_macd_keltner", "30s"),
        ("30s_williams_adx_atr", "30s"),
        ("30s_vwap_momentum", "30s"),
        ("30s_triple_confirmation", "30s"),
        ("30s_fibonacci_confluence", "30s"),
        ("hybrid", "30s"),
    ],
    "M1": [
        ("deep_confluence", "M1"),
        ("hybrid", "M1"),
        ("momentum_buster", "M1"),
        ("1m_fibonacci_confluence", "M1"),
        ("1m_momentum_exhaustion", "M1"),
        ("1m_quad_crossover", "M1"),
        ("1m_rsi_divergence", "M1"),
        ("1m_triple_confirmation", "M1"),
        ("1m_triple_ema", "M1"),
    ],
}

SYMBOL = "EURUSD_OTC"
DAYS = 3
MIN_CONF = 50


def post_backtest(strategy, symbol, tf, days):
    body = json.dumps({
        "strategy": strategy,
        "symbol": symbol,
        "timeframe": tf,
        "days": days,
        "min_confidence": MIN_CONF,
    }).encode()
    req = urllib.request.Request(
        f"{API}/api/backtest/run",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)[:160]}


def score(wr, sig, pf):
    import math
    pf_c = max(0.5, min(2.5, pf or 1.0))
    return round((wr - 50.0) * math.sqrt(max(1, sig)) * pf_c, 2)


def main():
    results = {}
    for tf, cands in CANDIDATES_BY_TF.items():
        print(f"\n{'='*70}\nTIMEFRAME {tf} ({len(cands)} candidates)\n{'='*70}")
        rows = []
        for strat, real_tf in cands:
            t0 = time.time()
            r = post_backtest(strat, SYMBOL, real_tf, DAYS)
            elapsed = time.time() - t0
            if r.get("error"):
                print(f"  {strat:32s} ERROR: {r['error'][:80]}")
                continue
            res = (r.get("results") or [{}])[0]
            if res.get("error"):
                print(f"  {strat:32s} {res['error'][:80]}")
                continue
            m = res.get("metrics") or {}
            wr = float(m.get("win_rate") or 0)
            sig = int(m.get("total_trades") or 0)
            pf = float(m.get("profit_factor") or 0)
            roi = float(m.get("roi_percent") or 0)
            sc = score(wr, sig, pf)
            if sig < 5:
                tag = "  (thin)"
            else:
                tag = ""
            print(f"  {strat:32s} wr={wr:5.1f}% sig={sig:>4} pf={pf:>5.2f} roi={roi:>6.1f}% score={sc:>7}{tag}  [{elapsed:.1f}s]")
            rows.append({
                "strategy": strat, "wr": wr, "signals": sig, "pf": pf,
                "roi": roi, "score": sc,
            })
        rows = [r for r in rows if r["signals"] >= 5]
        rows.sort(key=lambda r: r["score"], reverse=True)
        if rows:
            winner = rows[0]
            print(f"\n  >>> WINNER: {winner['strategy']} (score={winner['score']}, wr={winner['wr']}%)")
            results[tf] = winner
        else:
            print(f"\n  >>> NO QUALIFIED STRATEGIES for {tf}")
    print("\n" + "=" * 70)
    print("FINAL RECOMMENDATIONS")
    print("=" * 70)
    for tf, w in results.items():
        print(f"  {tf:>4} -> {w['strategy']:32s} (score={w['score']}, wr={w['wr']}%, signals={w['signals']})")
    with open("/tmp/strategy_eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved: /tmp/strategy_eval_results.json")


if __name__ == "__main__":
    main()
