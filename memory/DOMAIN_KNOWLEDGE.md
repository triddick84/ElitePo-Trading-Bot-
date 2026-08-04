# Domain Knowledge — Trading, Microstructure & Algorithmic Strategies

_Curated reference for the AI's Elite PO Traders Bot. Sourced from the user's
Feb 2026 research dump (Iter 86). Kept intentionally close to the source
material — this is a lookup doc, not a design spec._

---

## 1. Algorithmic Trading Strategy Families

| Family | Idea | Typical Tools |
|---|---|---|
| **Trend / Momentum** | Buy assets rising, sell falling | Moving averages, breakouts, MACD |
| **Mean Reversion** | Prices revert to average | Bollinger, RSI, z-score |
| **Arbitrage** | Exploit price gaps across venues / assets | Latency, spread arb |
| **Market Making** | Quote both sides, earn the spread | Inventory & adverse-selection models |
| **Statistical Arbitrage / Pairs** | Trade relative mispricings | Cointegration, Kalman filters, PCA |
| **Execution Algorithms** | Minimize impact / cost | TWAP, VWAP, Implementation Shortfall |
| **High-Frequency / Latency** | Ultra-fast reaction to order flow / news | FPGA, kernel bypass, microwave links |
| **ML / AI-driven** | Pattern recognition, RL, alternative data | XGBoost, LSTM, PPO, Transformer |
| **Volatility Trading** | Trade expected vs realized volatility | Options, VIX-linked |
| **Order-Flow / Microstructure** | Order book imbalance & flow toxicity | VPIN, Kyle's λ |

**Success factors:** edge, low latency, risk controls, realistic transaction costs.

---

## 2. Market Microstructure — Core Elements

- Order types: market, limit, stop
- Order book dynamics: bid-ask spread, depth, imbalance
- Liquidity providers (makers) vs takers
- Price discovery process
- Transaction costs & market impact
- HFT effects
- Information asymmetry / adverse selection

### Key Analytical Metrics
- Bid-ask spread & depth
- Order-book imbalance
- Trade-flow toxicity / **VPIN**
- Price impact & resilience
- Effective vs quoted spread
- Queue position & fill probability

---

## 3. Foundational Models

### Kyle (1985) — Informed Trading & Price Impact
- Informed trader observes value \(V \sim N(\mu, \sigma_v^2)\), submits order \(x\).
- Noise traders: \(u \sim N(0, \sigma_u^2)\).
- Total order flow: \(y = x + u\).
- Market maker sets \(P = \mathbb{E}[V \mid y]\).

**Linear equilibrium:**
```
x = β · (V - μ)
P = μ + λ · y
```
with `λ = σ_v / (2 σ_u)`, `β = σ_u / σ_v`.

Price impact \(λ\) rises with signal strength, falls with noise. Informed profit `= σ_v · σ_u / 2`.

**Foundation** for modern order-flow-toxicity and market-impact models.

### Glosten-Milgrom (1985) — Spread from Adverse Selection
- Asset value V is high or low with equal probability.
- Informed traders know V; uninformed trade randomly.
- Risk-neutral market maker sets quotes with zero expected profit.

**Quotes:**
```
Ask = E[V | buy]
Bid = E[V | sell]
```
Spread = expected loss to informed traders. Bayesian update after each trade; spread widens as informed-trader probability rises.

### Kyle Equilibrium Derivation Sketch
Assume linear strategies `x = β(V − μ)`, `P = μ + λy`, `y = x + u`. Informed maximises `E[(V − P)x] = (V − μ)x − λx²`. Optimal `x* = (V − μ)/(2λ)` → `β = 1/(2λ)`. Market maker: `P = E[V|y]`; by projection theorem `λ = Cov(V,y)/Var(y) = β σ_v² / (β²σ_v² + σ_u²)`. Substituting gives closed-form `λ = σ_v/(2σ_u)`, `β = σ_u/σ_v`.

---

## 4. Statistical Arbitrage

**Core idea**
- Identify pairs / baskets with historically stable relationships (cointegration, correlation).
- When the spread diverges beyond a threshold → short the winner, long the loser.
- Close when the relationship reverts to mean.

**Tools:** cointegration tests, z-scores, Kalman filters, PCA, ML models.
**Holding periods:** minutes → days. Highly capacity-constrained.
**Relies on mean reversion**, not directional prediction.

---

## 5. High-Frequency Trading

### Strategy Types
- Market making — continuous two-sided quotes; profit from spread + inventory risk
- Latency arbitrage — race to react to price updates across venues
- Statistical arbitrage (ultra-short) — fast mean-reversion on pairs/baskets
- Order-flow prediction — anticipate large orders from imbalance/patterns
- Liquidity detection — find hidden/iceberg orders
- Event/news trading — parse machine-readable data in microseconds

**Requires:** co-location, custom hardware (FPGA), sophisticated risk systems.

### Latency Benchmarks (2026, co-located)
| Layer | Latency |
|---|---|
| Top FPGA tick-to-trade | 700 – 800 ns |
| Optimized software + kernel bypass | 3 – 10 µs |
| Nasdaq matching engine (best) | ~14 µs |
| Nasdaq round-trip / tick-to-trade | sub-50 µs |
| CME Globex matching engine | < 150 µs |
| Standard low-latency (colo) | 50 – 200 µs |
| Regular exchange API | 1 – 5 ms+ |
| Cross-venue microwave (Nasdaq↔CME) | ~4.1 – 4.25 ms one-way |

### Practical Percentile Focus
- Firms measure privately; **p99 / p99.9 / p99.99 matter more than mean**.
- Tails decide who wins races.
- Public numbers are usually upper bounds or medians.

---

## 6. VPIN (Easley, López de Prado, O'Hara)

**Volume-Synchronized Probability of Informed Trading.**

Rough recipe:
1. Split time into **volume buckets** (equal traded volume per bucket, not equal time).
2. Within each bucket, assign each trade a buy/sell tag (Lee-Ready rule, or BVC — Bulk Volume Classification).
3. Bucket imbalance = `|B_buy − B_sell| / bucket_volume`.
4. VPIN = mean bucket imbalance over the last N buckets.
5. High VPIN → **flow is one-sided / informed** → market maker widens spreads → adverse selection risk high.

**Our proxy** (single-trade context, no order book): use win/loss + direction sequence bucketed by TRADE COUNT (see `/app/backend/microstructure.py`).

---

## 7. Quantitative Finance — Areas & Tooling

- Derivative pricing (Black-Scholes, stochastic calculus)
- Risk management (VaR, stress testing)
- Portfolio optimisation (Markowitz, factor models)
- Algorithmic / HFT
- Statistical arb & microstructure
- ML for prediction & alpha

**Skills:** strong math, Python / C++, data.

---

## 8. Real-Time Data — Legitimate Sources

**Only** use official / licensed endpoints:
- Broker APIs (OANDA, IB, etc.) with explicit data rights
- Alpha Vantage, Twelve Data, Polygon.io (API key required)
- `yfinance` for public equities/FX (free but rate-limited)
- Emergent LLM key for AI/model access

**Never** use unofficial Pocket Option WS endpoints — legal + rate-limit risk.

---

## 9. Reference — Latency Percentile Snippets

Python one-liner:
```python
import numpy as np
lat = np.loadtxt("latency_log.txt")
print(np.percentile(lat, 99))
```

Pandas:
```python
import pandas as pd
pd.read_csv("latency_log.csv", header=None).quantile(0.99)
```

Realtime TCP RTT monitor: [`request_latency_histogram.py`](/app/backend/request_latency_histogram.py) — bounded deque per route with p50/p95/p99/p99.9.

---

## 10. Applied to This Codebase (Iter 86)

| Concept | Where implemented |
|---|---|
| VPIN toxicity gate | `microstructure.py::compute_vpin` + `MicrostructureService.should_gate` |
| Kyle's λ estimator | `microstructure.py::compute_kyle_lambda` + `.confidence_multiplier` |
| Order-flow imbalance | `microstructure.py::compute_flow_imbalance` (candle-derived) |
| Cointegrated-pair confluence | `pair_confluence.py::confluence_score` |
| Latency p50/p99 monitor | `request_latency_histogram.py::RequestLatencyMiddleware` |
| Regime classifier (trend/range/high-vol) | `regime_classifier.py` |
| Accuracy-weighted ensemble | `ensemble_weights.py::compute_weights` |
| PPO RL reward shaping | `rl_ppo_agent.py::TradingEnv.step` |
| Chronic-loser gate | `accuracy_engine.py::AccuracyEngine.should_gate` |

All of these compose in `/api/signals/latest`:
```
AccuracyEngine (chronic losers) → Microstructure (toxic flow) → Latency
  → Pair Confluence (confidence tilt) → λ multiplier (regime tilt)
```
The signal only reaches the TM script if all four gates pass, and its confidence
carries the pair-confluence + λ multipliers.
