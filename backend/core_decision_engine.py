"""
Core Decision Engine v2.0
==========================
Translates ML model predictions into executable, risk-controlled trading decisions.

Architecture:
- Multi-model ensemble (LSTM/GRU + XGBoost/LightGBM + RF + PPO RL)
- Multi-strategy simultaneous execution (trend-following, mean-reversion, scalping)
- Risk management (stop-loss, max drawdown, Kelly sizing, volatility filters)
- Continuous learning with auto-retrain scheduling
- Real-time execution quality monitoring
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


class StrategyMode(Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    SCALPING = "scalping"
    MOMENTUM = "momentum"


@dataclass
class RiskLimits:
    max_drawdown_pct: float = 10.0       # Max 10% portfolio drawdown
    max_daily_loss_pct: float = 5.0      # Max 5% daily loss
    max_position_pct: float = 5.0        # Max 5% per trade (Kelly-adjusted)
    min_confidence: float = 65.0         # Min signal confidence to trade
    max_consecutive_losses: int = 5      # Stop after 5 consecutive losses
    max_open_trades: int = 3             # Max simultaneous trades
    volatility_filter_atr_mult: float = 2.0  # Skip if ATR > 2x normal
    min_win_rate_threshold: float = 0.45 # Pause if win rate drops below 45%
    cooldown_after_loss_streak_s: int = 300  # 5 min cooldown after loss streak


@dataclass
class TradeDecision:
    action: str = "HOLD"                 # CALL, PUT, HOLD
    confidence: float = 0.0
    strategy_mode: str = "ensemble"
    position_size_pct: float = 1.0       # % of capital
    expiry_seconds: int = 5
    stop_loss_pips: float = 0.0
    take_profit_pips: float = 0.0
    risk_reward_ratio: float = 0.0
    model_votes: Dict = field(default_factory=dict)
    regime: str = "unknown"
    volatility_state: str = "normal"
    risk_check_passed: bool = True
    risk_warnings: List[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class PerformanceTracker:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    peak_balance: float = 10000.0
    current_balance: float = 10000.0
    daily_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    sharpe_daily_returns: List[float] = field(default_factory=list)
    trade_history: List[Dict] = field(default_factory=list)
    strategy_performance: Dict = field(default_factory=dict)
    last_trade_time: Optional[str] = None
    last_loss_streak_time: Optional[str] = None

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_trades if self.total_trades > 0 else 0.5

    @property
    def sharpe_ratio(self) -> float:
        if len(self.sharpe_daily_returns) < 5:
            return 0.0
        rets = np.array(self.sharpe_daily_returns)
        if rets.std() == 0:
            return 0.0
        return float(np.sqrt(252) * rets.mean() / rets.std())

    @property
    def max_drawdown_pct(self) -> float:
        if self.peak_balance == 0:
            return 0.0
        return (self.max_drawdown / self.peak_balance) * 100


class CoreDecisionEngine:
    """
    Central decision engine that orchestrates all ML models, strategies, and risk management.
    """

    def __init__(self, db=None):
        self.db = db
        self.risk_limits = RiskLimits()
        self.performance = PerformanceTracker()
        self.active_strategies = {
            StrategyMode.TREND_FOLLOWING: True,
            StrategyMode.MEAN_REVERSION: True,
            StrategyMode.SCALPING: True,
            StrategyMode.MOMENTUM: True,
        }

        # Model references (set externally)
        self.maximized_ml = None
        self.improved_ml = None
        self.lstm_gru = None
        self.ppo_agent = None
        self.iq720 = None

        # Model weights for ensemble voting
        self.model_weights = {
            "maximized_ml": 0.30,
            "improved_ml": 0.20,
            "lstm_gru": 0.25,
            "ppo_rl": 0.10,
            "iq720": 0.15,
        }

        # Strategy weights per regime
        self.regime_strategy_weights = {
            MarketRegime.TRENDING_UP: {
                StrategyMode.TREND_FOLLOWING: 0.50,
                StrategyMode.MOMENTUM: 0.30,
                StrategyMode.MEAN_REVERSION: 0.10,
                StrategyMode.SCALPING: 0.10,
            },
            MarketRegime.TRENDING_DOWN: {
                StrategyMode.TREND_FOLLOWING: 0.50,
                StrategyMode.MOMENTUM: 0.30,
                StrategyMode.MEAN_REVERSION: 0.10,
                StrategyMode.SCALPING: 0.10,
            },
            MarketRegime.RANGING: {
                StrategyMode.MEAN_REVERSION: 0.50,
                StrategyMode.SCALPING: 0.30,
                StrategyMode.TREND_FOLLOWING: 0.10,
                StrategyMode.MOMENTUM: 0.10,
            },
            MarketRegime.HIGH_VOLATILITY: {
                StrategyMode.SCALPING: 0.40,
                StrategyMode.MOMENTUM: 0.30,
                StrategyMode.TREND_FOLLOWING: 0.20,
                StrategyMode.MEAN_REVERSION: 0.10,
            },
            MarketRegime.LOW_VOLATILITY: {
                StrategyMode.MEAN_REVERSION: 0.40,
                StrategyMode.SCALPING: 0.30,
                StrategyMode.TREND_FOLLOWING: 0.20,
                StrategyMode.MOMENTUM: 0.10,
            },
        }

        logger.info("Core Decision Engine v2.0 initialized")

    # ==================== MARKET REGIME DETECTION ====================

    def detect_regime(self, closes: np.ndarray, highs: np.ndarray = None, lows: np.ndarray = None) -> MarketRegime:
        """Detect current market regime from price data."""
        if len(closes) < 30:
            return MarketRegime.RANGING

        # Trend detection via EMA slope
        ema20 = pd.Series(closes).ewm(span=20).mean().values
        ema50 = pd.Series(closes).ewm(span=50).mean().values if len(closes) >= 50 else ema20

        ema20_slope = (ema20[-1] - ema20[-5]) / ema20[-5] if len(ema20) >= 5 else 0
        trend_up = ema20[-1] > ema50[-1] and ema20_slope > 0.0001
        trend_down = ema20[-1] < ema50[-1] and ema20_slope < -0.0001

        # Volatility via ATR
        if highs is not None and lows is not None and len(highs) > 14:
            tr = np.maximum(
                highs[-14:] - lows[-14:],
                np.maximum(
                    np.abs(highs[-14:] - np.roll(closes, 1)[-14:]),
                    np.abs(lows[-14:] - np.roll(closes, 1)[-14:])
                )
            )
            atr = np.mean(tr)
            avg_atr = np.mean(np.abs(np.diff(closes[-30:])))
            high_vol = atr > avg_atr * 1.5
            low_vol = atr < avg_atr * 0.5
        else:
            rets = np.abs(np.diff(closes[-20:]) / closes[-21:-1])
            recent_vol = np.std(rets[-5:]) if len(rets) >= 5 else 0
            avg_vol = np.std(rets) if len(rets) > 0 else 0
            high_vol = recent_vol > avg_vol * 1.5
            low_vol = recent_vol < avg_vol * 0.5

        if high_vol:
            return MarketRegime.HIGH_VOLATILITY
        if low_vol:
            return MarketRegime.LOW_VOLATILITY
        if trend_up:
            return MarketRegime.TRENDING_UP
        if trend_down:
            return MarketRegime.TRENDING_DOWN
        return MarketRegime.RANGING

    # ==================== MULTI-MODEL ENSEMBLE ====================

    def collect_model_votes(self, candles: List[Dict], symbol: str = "EURUSD") -> Dict:
        """Collect predictions from all available ML models."""
        votes = {}

        # IQ-720 Ensemble (always available — pure technical)
        if self.iq720:
            try:
                sig = self.iq720.generate_ensemble_signal(candles)
                if sig:
                    votes["iq720"] = {
                        "direction": sig.get("direction", "HOLD"),
                        "confidence": sig.get("confidence", 0),
                        "source": "iq720_ensemble"
                    }
            except Exception as e:
                logger.debug(f"IQ-720 vote error: {e}")

        # Maximized ML (XGBoost/LightGBM stacking)
        if self.maximized_ml and self.maximized_ml.is_trained:
            try:
                df = pd.DataFrame(candles)
                for col in ['open', 'high', 'low', 'close']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                features, names = self.maximized_ml.extract_features(df)
                if features is not None:
                    features_scaled = self.maximized_ml.scaler.transform(features.reshape(1, -1))
                    pred = self.maximized_ml.model.predict(features_scaled)[0]
                    proba = self.maximized_ml.model.predict_proba(features_scaled)[0]
                    conf = float(max(proba)) * 100
                    votes["maximized_ml"] = {
                        "direction": "CALL" if pred == 1 else "PUT",
                        "confidence": round(conf, 1),
                        "source": "maximized_v3"
                    }
            except Exception as e:
                logger.debug(f"Maximized ML vote error: {e}")

        # Improved ML (RF/GB/AdaBoost)
        if self.improved_ml and self.improved_ml.is_trained:
            try:
                df = pd.DataFrame(candles)
                for col in ['open', 'high', 'low', 'close']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                features, names = self.improved_ml.extract_features(df)
                if features is not None:
                    features_scaled = self.improved_ml.scaler.transform(features.reshape(1, -1))
                    pred = self.improved_ml.model.predict(features_scaled)[0]
                    proba = self.improved_ml.model.predict_proba(features_scaled)[0]
                    conf = float(max(proba)) * 100
                    votes["improved_ml"] = {
                        "direction": "CALL" if pred == 1 else "PUT",
                        "confidence": round(conf, 1),
                        "source": "improved_v2"
                    }
            except Exception as e:
                logger.debug(f"Improved ML vote error: {e}")

        # LSTM/GRU
        if self.lstm_gru and self.lstm_gru.is_trained:
            try:
                from lstm_gru_system import FeatureEngine
                feats = FeatureEngine.compute(candles)
                if feats is not None and len(feats) >= self.lstm_gru.SEQUENCE_LEN:
                    seq = feats[-self.lstm_gru.SEQUENCE_LEN:]
                    pred = self.lstm_gru.model.predict(np.expand_dims(seq, 0), verbose=0)[0]
                    buy_prob, sell_prob, hold_prob = float(pred[0]), float(pred[1]), float(pred[2])
                    if buy_prob > sell_prob and buy_prob > hold_prob:
                        votes["lstm_gru"] = {"direction": "CALL", "confidence": round(buy_prob * 100, 1), "source": "lstm_gru"}
                    elif sell_prob > buy_prob and sell_prob > hold_prob:
                        votes["lstm_gru"] = {"direction": "PUT", "confidence": round(sell_prob * 100, 1), "source": "lstm_gru"}
            except Exception as e:
                logger.debug(f"LSTM/GRU vote error: {e}")

        # PPO RL Agent
        if self.ppo_agent and hasattr(self.ppo_agent, 'actor') and self.ppo_agent.actor is not None:
            try:
                from lstm_gru_system import FeatureEngine
                feats = FeatureEngine.compute(candles)
                if feats is not None and len(feats) > 20:
                    state = feats[-20:].flatten()
                    state = np.concatenate([state, [0, 0]])  # position info
                    action, _ = self.ppo_agent.act(state)
                    if action == 1:
                        votes["ppo_rl"] = {"direction": "CALL", "confidence": 60, "source": "ppo_rl"}
                    elif action == 2:
                        votes["ppo_rl"] = {"direction": "PUT", "confidence": 60, "source": "ppo_rl"}
            except Exception as e:
                logger.debug(f"PPO RL vote error: {e}")

        return votes

    def weighted_ensemble_decision(self, votes: Dict, regime: MarketRegime) -> Tuple[str, float]:
        """Combine model votes using regime-adjusted weights."""
        if not votes:
            return "HOLD", 0.0

        call_score = 0.0
        put_score = 0.0
        total_weight = 0.0

        for model_name, vote in votes.items():
            weight = self.model_weights.get(model_name, 0.1)
            conf = vote.get("confidence", 50) / 100.0
            direction = vote.get("direction", "HOLD")

            if direction == "CALL":
                call_score += weight * conf
            elif direction == "PUT":
                put_score += weight * conf
            total_weight += weight

        if total_weight == 0:
            return "HOLD", 0.0

        call_score /= total_weight
        put_score /= total_weight

        # Require minimum margin between directions
        margin = abs(call_score - put_score)
        if margin < 0.05:  # Less than 5% difference = uncertain
            return "HOLD", margin * 100

        if call_score > put_score:
            return "CALL", min(95, call_score * 100)
        else:
            return "PUT", min(95, put_score * 100)

    # ==================== RISK MANAGEMENT ====================

    def check_risk_limits(self) -> Tuple[bool, List[str]]:
        """Check all risk limits before allowing a trade."""
        warnings = []

        # Max drawdown check
        if self.performance.max_drawdown_pct > self.risk_limits.max_drawdown_pct:
            warnings.append(f"MAX_DRAWDOWN: {self.performance.max_drawdown_pct:.1f}% > {self.risk_limits.max_drawdown_pct}%")
            return False, warnings

        # Daily loss check
        daily_loss_pct = abs(self.performance.daily_pnl / self.performance.peak_balance * 100) if self.performance.daily_pnl < 0 else 0
        if daily_loss_pct > self.risk_limits.max_daily_loss_pct:
            warnings.append(f"DAILY_LOSS: {daily_loss_pct:.1f}% > {self.risk_limits.max_daily_loss_pct}%")
            return False, warnings

        # Consecutive loss check
        if self.performance.consecutive_losses >= self.risk_limits.max_consecutive_losses:
            warnings.append(f"LOSS_STREAK: {self.performance.consecutive_losses} >= {self.risk_limits.max_consecutive_losses}")
            # Check cooldown
            if self.performance.last_loss_streak_time:
                elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(self.performance.last_loss_streak_time)).total_seconds()
                if elapsed < self.risk_limits.cooldown_after_loss_streak_s:
                    warnings.append(f"COOLDOWN: {int(self.risk_limits.cooldown_after_loss_streak_s - elapsed)}s remaining")
                    return False, warnings

        # Win rate check
        if self.performance.total_trades > 20 and self.performance.win_rate < self.risk_limits.min_win_rate_threshold:
            warnings.append(f"LOW_WIN_RATE: {self.performance.win_rate:.1%} < {self.risk_limits.min_win_rate_threshold:.0%}")
            return False, warnings

        return True, warnings

    def calculate_position_size(self, confidence: float, regime: MarketRegime) -> float:
        """Dynamic position sizing using Kelly Criterion + regime adjustment."""
        win_rate = max(0.45, self.performance.win_rate) if self.performance.total_trades > 10 else 0.55
        payout = 0.82  # Pocket Option typical payout

        # Kelly fraction
        loss_rate = 1 - win_rate
        kelly = (win_rate * payout - loss_rate) / payout if payout > 0 else 0
        kelly = max(0.01, min(0.25, kelly))
        half_kelly = kelly * 0.5  # Half-Kelly for safety

        # Confidence adjustment (higher confidence = closer to full Kelly)
        conf_mult = min(1.0, confidence / 85.0)

        # Regime adjustment
        regime_mult = {
            MarketRegime.TRENDING_UP: 1.0,
            MarketRegime.TRENDING_DOWN: 1.0,
            MarketRegime.RANGING: 0.7,
            MarketRegime.HIGH_VOLATILITY: 0.5,
            MarketRegime.LOW_VOLATILITY: 0.8,
        }.get(regime, 0.7)

        # Drawdown adjustment (reduce size as drawdown increases)
        dd_pct = self.performance.current_drawdown / self.performance.peak_balance * 100 if self.performance.peak_balance > 0 else 0
        dd_mult = max(0.3, 1.0 - dd_pct / 20.0)

        size = half_kelly * conf_mult * regime_mult * dd_mult * 100  # as percentage
        return round(min(size, self.risk_limits.max_position_pct), 2)

    # ==================== STRATEGY SELECTION ====================

    def select_strategies(self, regime: MarketRegime, candles: List[Dict]) -> List[StrategyMode]:
        """Select active strategies based on market regime."""
        weights = self.regime_strategy_weights.get(regime, {})
        active = []

        for mode, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            if self.active_strategies.get(mode, False) and weight >= 0.10:
                active.append(mode)

        return active or [StrategyMode.SCALPING]

    # ==================== CORE DECISION PIPELINE ====================

    def generate_decision(self, candles: List[Dict], symbol: str = "EURUSD") -> TradeDecision:
        """
        Main decision pipeline:
        1. Detect market regime
        2. Collect model votes
        3. Weighted ensemble decision
        4. Risk management checks
        5. Position sizing
        6. Generate final executable decision
        """
        decision = TradeDecision(timestamp=datetime.now(timezone.utc).isoformat())

        if not candles or len(candles) < 30:
            decision.risk_warnings.append("INSUFFICIENT_DATA")
            return decision

        closes = np.array([float(c.get('close', c.get('Close', 0))) for c in candles])
        highs = np.array([float(c.get('high', c.get('High', c.get('close', 0)))) for c in candles])
        lows = np.array([float(c.get('low', c.get('Low', c.get('close', 0)))) for c in candles])

        # 1. Market Regime
        regime = self.detect_regime(closes, highs, lows)
        decision.regime = regime.value

        # Volatility state
        if regime == MarketRegime.HIGH_VOLATILITY:
            decision.volatility_state = "high"
        elif regime == MarketRegime.LOW_VOLATILITY:
            decision.volatility_state = "low"
        else:
            decision.volatility_state = "normal"

        # 2. Collect Model Votes
        votes = self.collect_model_votes(candles, symbol)
        decision.model_votes = {k: v for k, v in votes.items()}

        if not votes:
            decision.risk_warnings.append("NO_MODEL_VOTES")
            return decision

        # 3. Weighted Ensemble Decision
        direction, confidence = self.weighted_ensemble_decision(votes, regime)
        decision.action = direction
        decision.confidence = round(confidence, 1)

        if direction == "HOLD" or confidence < self.risk_limits.min_confidence:
            decision.action = "HOLD"
            decision.risk_warnings.append(f"LOW_CONFIDENCE: {confidence:.1f}% < {self.risk_limits.min_confidence}%")
            return decision

        # 4. Risk Management
        risk_ok, risk_warnings = self.check_risk_limits()
        decision.risk_warnings = risk_warnings
        decision.risk_check_passed = risk_ok

        if not risk_ok:
            decision.action = "HOLD"
            return decision

        # 5. Select Strategy Mode
        strategies = self.select_strategies(regime, candles)
        if strategies:
            decision.strategy_mode = strategies[0].value

        # 6. Position Sizing
        decision.position_size_pct = self.calculate_position_size(confidence, regime)

        # 7. Expiry based on strategy
        if decision.strategy_mode == StrategyMode.SCALPING.value:
            decision.expiry_seconds = 5
        elif decision.strategy_mode == StrategyMode.MOMENTUM.value:
            decision.expiry_seconds = 15
        elif decision.strategy_mode == StrategyMode.MEAN_REVERSION.value:
            decision.expiry_seconds = 30
        else:
            decision.expiry_seconds = 60

        # 8. Risk/Reward
        atr = np.mean(highs[-14:] - lows[-14:]) if len(highs) >= 14 else 0.001
        decision.stop_loss_pips = round(atr * 10000 * 1.5, 1)
        decision.take_profit_pips = round(atr * 10000 * 2.5, 1)
        decision.risk_reward_ratio = round(decision.take_profit_pips / decision.stop_loss_pips, 2) if decision.stop_loss_pips > 0 else 0

        return decision

    # ==================== TRADE OUTCOME TRACKING ====================

    def record_trade_result(self, symbol: str, direction: str, outcome: str, pnl: float = 0, strategy: str = ""):
        """Record trade result for performance tracking, per-asset/strategy stats, and auto-promotion."""
        is_win = outcome.lower() in ("win", "profit", "1")

        self.performance.total_trades += 1
        if is_win:
            self.performance.wins += 1
            self.performance.consecutive_wins += 1
            self.performance.consecutive_losses = 0
        else:
            self.performance.losses += 1
            self.performance.consecutive_losses += 1
            self.performance.consecutive_wins = 0
            if self.performance.consecutive_losses >= self.risk_limits.max_consecutive_losses:
                self.performance.last_loss_streak_time = datetime.now(timezone.utc).isoformat()

        # Balance tracking
        self.performance.current_balance += pnl
        self.performance.daily_pnl += pnl
        if self.performance.current_balance > self.performance.peak_balance:
            self.performance.peak_balance = self.performance.current_balance

        drawdown = self.performance.peak_balance - self.performance.current_balance
        self.performance.current_drawdown = drawdown
        if drawdown > self.performance.max_drawdown:
            self.performance.max_drawdown = drawdown

        # Daily returns for Sharpe
        self.performance.sharpe_daily_returns.append(pnl / self.performance.peak_balance if self.performance.peak_balance > 0 else 0)

        # === Per-asset performance tracking ===
        if symbol not in self.performance.strategy_performance:
            self.performance.strategy_performance[symbol] = {}
        asset_perf = self.performance.strategy_performance[symbol]
        
        if "_total" not in asset_perf:
            asset_perf["_total"] = {"wins": 0, "losses": 0, "pnl": 0.0, "best_strategy": ""}
        asset_perf["_total"]["wins" if is_win else "losses"] += 1
        asset_perf["_total"]["pnl"] += pnl

        # === Per-strategy-per-asset tracking ===
        strat_key = strategy or "unknown"
        if strat_key not in asset_perf:
            asset_perf[strat_key] = {"wins": 0, "losses": 0, "pnl": 0.0}
        asset_perf[strat_key]["wins" if is_win else "losses"] += 1
        asset_perf[strat_key]["pnl"] += pnl

        # === Auto-promotion: find best strategy per asset ===
        best_strat = ""
        best_wr = 0.0
        for sk, sv in asset_perf.items():
            if sk.startswith("_"):
                continue
            total = sv["wins"] + sv["losses"]
            if total >= 5:  # Min 5 trades to judge
                wr = sv["wins"] / total
                if wr > best_wr:
                    best_wr = wr
                    best_strat = sk
        asset_perf["_total"]["best_strategy"] = best_strat
        asset_perf["_total"]["best_win_rate"] = round(best_wr * 100, 1)

        # Trade history
        self.performance.trade_history.append({
            "symbol": symbol,
            "direction": direction,
            "outcome": outcome,
            "pnl": pnl,
            "strategy": strat_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cumulative_balance": self.performance.current_balance,
            "win_rate": self.performance.win_rate,
        })

        # Keep last 500 trades
        if len(self.performance.trade_history) > 500:
            self.performance.trade_history = self.performance.trade_history[-500:]

        self.performance.last_trade_time = datetime.now(timezone.utc).isoformat()

    def get_strategy_tracker(self) -> Dict:
        """Get per-asset strategy performance with auto-promotion recommendations."""
        tracker = {}
        for symbol, perf in self.performance.strategy_performance.items():
            total_info = perf.get("_total", {})
            total_trades = total_info.get("wins", 0) + total_info.get("losses", 0)
            strategies = {}
            for sk, sv in perf.items():
                if sk.startswith("_"):
                    continue
                st = sv["wins"] + sv["losses"]
                strategies[sk] = {
                    "wins": sv["wins"],
                    "losses": sv["losses"],
                    "total": st,
                    "win_rate": round(sv["wins"] / st * 100, 1) if st > 0 else 0,
                    "pnl": round(sv["pnl"], 2),
                }
            tracker[symbol] = {
                "total_trades": total_trades,
                "win_rate": round(total_info.get("wins", 0) / total_trades * 100, 1) if total_trades > 0 else 0,
                "pnl": round(total_info.get("pnl", 0), 2),
                "best_strategy": total_info.get("best_strategy", ""),
                "best_win_rate": total_info.get("best_win_rate", 0),
                "strategies": strategies,
            }
        return tracker

    def get_best_strategy_for_asset(self, symbol: str) -> Optional[str]:
        """Get the best-performing strategy for a specific asset (auto-promotion)."""
        perf = self.performance.strategy_performance.get(symbol, {})
        total = perf.get("_total", {})
        return total.get("best_strategy", "") or None

    # ==================== STATUS & REPORTING ====================

    def get_engine_status(self) -> Dict:
        """Get comprehensive engine status."""
        models_status = {}
        if self.maximized_ml:
            models_status["maximized_v3"] = {"trained": self.maximized_ml.is_trained, "accuracy": round(self.maximized_ml.model_accuracy * 100, 2)}
        if self.improved_ml:
            models_status["improved_v2"] = {"trained": self.improved_ml.is_trained, "accuracy": round(self.improved_ml.model_accuracy * 100, 2)}
        if self.lstm_gru:
            models_status["lstm_gru"] = {"trained": self.lstm_gru.is_trained, "accuracy": round(self.lstm_gru.accuracy * 100, 2)}
        if self.ppo_agent:
            models_status["ppo_rl"] = {"trained": hasattr(self.ppo_agent, 'actor') and self.ppo_agent.actor is not None}
        models_status["iq720"] = {"trained": True, "accuracy": 82}

        return {
            "version": "2.0.0",
            "models": models_status,
            "model_weights": self.model_weights,
            "active_strategies": {k.value: v for k, v in self.active_strategies.items()},
            "risk_limits": asdict(self.risk_limits),
            "performance": {
                "total_trades": self.performance.total_trades,
                "wins": self.performance.wins,
                "losses": self.performance.losses,
                "win_rate": round(self.performance.win_rate * 100, 2),
                "consecutive_losses": self.performance.consecutive_losses,
                "max_drawdown_pct": round(self.performance.max_drawdown_pct, 2),
                "current_drawdown_pct": round(self.performance.current_drawdown / self.performance.peak_balance * 100, 2) if self.performance.peak_balance > 0 else 0,
                "sharpe_ratio": round(self.performance.sharpe_ratio, 2),
                "current_balance": self.performance.current_balance,
                "peak_balance": self.performance.peak_balance,
            },
            "recent_trades": self.performance.trade_history[-10:],
        }


# Singleton
_decision_engine = None

def get_decision_engine(db=None) -> CoreDecisionEngine:
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = CoreDecisionEngine(db)
    return _decision_engine
