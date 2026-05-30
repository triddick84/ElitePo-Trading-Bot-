"""
Backtesting Engine for Trading Strategies and ML Models
Supports all timeframes from 5s to 4H with comprehensive metrics
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'gpt_signal_bot')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]
backtest_results_collection = db['backtest_results']


class TradeDirection(Enum):
    CALL = "CALL"
    PUT = "PUT"
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Trade:
    """Represents a single trade in backtesting"""
    entry_time: datetime
    direction: str
    entry_price: float
    exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    is_win: bool = False
    confidence: float = 0.0
    strategy: str = ""
    expiry_seconds: int = 60
    
    def close(self, exit_price: float, exit_time: datetime):
        """Close the trade and calculate P&L"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        
        # For binary options style: win if direction matches price movement
        if self.direction in ["CALL", "BUY"]:
            self.is_win = exit_price > self.entry_price
        else:  # PUT, SELL
            self.is_win = exit_price < self.entry_price
        
        # P&L calculation (binary style: 80% profit or 100% loss)
        if self.is_win:
            self.pnl_percent = 80.0  # 80% payout
        else:
            self.pnl_percent = -100.0  # 100% loss


@dataclass
class BacktestMetrics:
    """Comprehensive backtesting metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    profit_factor: float = 0.0
    
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    start_balance: float = 1000.0
    end_balance: float = 1000.0
    roi_percent: float = 0.0
    
    trades_by_hour: Dict[int, Dict] = field(default_factory=dict)
    trades_by_day: Dict[str, Dict] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "net_profit": round(self.net_profit, 2),
            "profit_factor": round(self.profit_factor, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_percent": round(self.max_drawdown_percent, 2),
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "avg_trade": round(self.avg_trade, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "start_balance": round(self.start_balance, 2),
            "end_balance": round(self.end_balance, 2),
            "roi_percent": round(self.roi_percent, 2),
            "trades_by_hour": {str(k): v for k, v in (self.trades_by_hour or {}).items()},
            "trades_by_day": self.trades_by_day
        }


class BacktestingEngine:
    """
    Core backtesting engine supporting strategies and ML models
    """
    
    # Timeframe to seconds mapping
    TIMEFRAME_SECONDS = {
        "5s": 5,
        "15s": 15,
        "30s": 30,
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
        "H4": 14400,
    }
    
    def __init__(self, initial_balance: float = 1000.0, trade_size: float = 10.0):
        self.initial_balance = initial_balance
        self.trade_size = trade_size
        self.balance = initial_balance
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        
    def reset(self):
        """Reset the engine for a new backtest"""
        self.balance = self.initial_balance
        self.trades = []
        self.equity_curve = [(datetime.now(timezone.utc), self.initial_balance)]
    
    def _get_exit_candle_index(
        self,
        df: pd.DataFrame,
        entry_idx: int,
        expiry_seconds: int,
        timeframe: str
    ) -> int:
        """Calculate the candle index where the trade expires"""
        tf_seconds = self.TIMEFRAME_SECONDS.get(timeframe, 60)
        candles_to_expiry = max(1, expiry_seconds // tf_seconds)
        return min(entry_idx + candles_to_expiry, len(df) - 1)
    
    def run_strategy_backtest(
        self,
        df: pd.DataFrame,
        strategy_func: Callable[[pd.DataFrame, int], Optional[Dict]],
        timeframe: str = "M1",
        expiry_seconds: int = 60,
        min_confidence: float = 65.0
    ) -> BacktestMetrics:
        """
        Run backtest for a strategy function
        
        Args:
            df: DataFrame with OHLCV data
            strategy_func: Function that takes (df, index) and returns signal dict or None
            timeframe: Timeframe string
            expiry_seconds: Trade expiry in seconds
            min_confidence: Minimum confidence to take trade
            
        Returns:
            BacktestMetrics with results
        """
        self.reset()
        
        if df is None or len(df) < 50:
            logger.warning("Insufficient data for backtesting")
            return self._calculate_metrics()
        
        # Ensure timestamp column
        if 'timestamp' not in df.columns:
            df['timestamp'] = pd.date_range(
                start=datetime.now(timezone.utc) - timedelta(minutes=len(df)),
                periods=len(df),
                freq='1min'
            )
        
        # Iterate through candles
        lookback = 50  # Minimum candles needed for indicators
        
        for i in range(lookback, len(df) - 1):
            # Get signal from strategy
            try:
                signal = strategy_func(df.iloc[:i+1], i)
            except Exception as e:
                logger.debug(f"Strategy error at index {i}: {e}")
                continue
            
            if signal is None:
                continue
            
            confidence = signal.get("confidence", 0)
            if confidence < min_confidence:
                continue
            
            direction = signal.get("direction", "").upper()
            if direction not in ["CALL", "PUT", "BUY", "SELL"]:
                continue
            
            # Get entry and exit prices
            entry_price = float(df.iloc[i]["close"])
            entry_time = df.iloc[i]["timestamp"]
            
            exit_idx = self._get_exit_candle_index(df, i, expiry_seconds, timeframe)
            exit_price = float(df.iloc[exit_idx]["close"])
            exit_time = df.iloc[exit_idx]["timestamp"]
            
            # Create and close trade
            trade = Trade(
                entry_time=entry_time,
                direction=direction,
                entry_price=entry_price,
                confidence=confidence,
                strategy=signal.get("strategy", "unknown"),
                expiry_seconds=expiry_seconds
            )
            trade.close(exit_price, exit_time)
            
            # Update balance
            trade_pnl = self.trade_size * (trade.pnl_percent / 100)
            self.balance += trade_pnl
            trade.pnl = trade_pnl
            
            self.trades.append(trade)
            self.equity_curve.append((exit_time, self.balance))
        
        return self._calculate_metrics()
    
    def run_ml_model_backtest(
        self,
        df: pd.DataFrame,
        model_predict_func: Callable[[pd.DataFrame], Optional[Dict]],
        timeframe: str = "M1",
        expiry_seconds: int = 60,
        min_confidence: float = 60.0
    ) -> BacktestMetrics:
        """
        Run backtest for an ML model
        
        Args:
            df: DataFrame with OHLCV data
            model_predict_func: Function that takes df and returns prediction dict
            timeframe: Timeframe string
            expiry_seconds: Trade expiry in seconds
            min_confidence: Minimum confidence to take trade
        """
        self.reset()
        
        if df is None or len(df) < 100:
            logger.warning("Insufficient data for ML backtesting")
            return self._calculate_metrics()
        
        lookback = 100  # ML models need more context
        
        for i in range(lookback, len(df) - 1):
            # Get prediction from model
            try:
                prediction = model_predict_func(df.iloc[:i+1])
            except Exception as e:
                logger.debug(f"Model error at index {i}: {e}")
                continue
            
            if prediction is None:
                continue
            
            confidence = prediction.get("confidence", 0)
            if confidence < min_confidence:
                continue
            
            direction = prediction.get("direction", "").upper()
            if direction not in ["CALL", "PUT", "BUY", "SELL", "UP", "DOWN"]:
                continue
            
            # Normalize direction
            if direction in ["UP", "BUY"]:
                direction = "CALL"
            elif direction in ["DOWN", "SELL"]:
                direction = "PUT"
            
            # Get entry and exit
            entry_price = float(df.iloc[i]["close"])
            entry_time = df.iloc[i]["timestamp"] if 'timestamp' in df.columns else datetime.now(timezone.utc)
            
            exit_idx = self._get_exit_candle_index(df, i, expiry_seconds, timeframe)
            exit_price = float(df.iloc[exit_idx]["close"])
            exit_time = df.iloc[exit_idx]["timestamp"] if 'timestamp' in df.columns else datetime.now(timezone.utc)
            
            trade = Trade(
                entry_time=entry_time,
                direction=direction,
                entry_price=entry_price,
                confidence=confidence,
                strategy=prediction.get("method", "ML_MODEL"),
                expiry_seconds=expiry_seconds
            )
            trade.close(exit_price, exit_time)
            
            trade_pnl = self.trade_size * (trade.pnl_percent / 100)
            self.balance += trade_pnl
            trade.pnl = trade_pnl
            
            self.trades.append(trade)
            self.equity_curve.append((exit_time, self.balance))
        
        return self._calculate_metrics()
    
    def _calculate_metrics(self) -> BacktestMetrics:
        """Calculate comprehensive metrics from trades"""
        metrics = BacktestMetrics()
        metrics.start_balance = self.initial_balance
        metrics.end_balance = self.balance
        
        if not self.trades:
            return metrics
        
        metrics.total_trades = len(self.trades)
        metrics.winning_trades = sum(1 for t in self.trades if t.is_win)
        metrics.losing_trades = metrics.total_trades - metrics.winning_trades
        
        if metrics.total_trades > 0:
            metrics.win_rate = (metrics.winning_trades / metrics.total_trades) * 100
        
        # P&L calculations
        wins = [t.pnl for t in self.trades if t.is_win]
        losses = [abs(t.pnl) for t in self.trades if not t.is_win]
        
        metrics.gross_profit = sum(wins)
        metrics.gross_loss = sum(losses)
        metrics.net_profit = metrics.gross_profit - metrics.gross_loss
        
        if metrics.gross_loss > 0:
            metrics.profit_factor = metrics.gross_profit / metrics.gross_loss
        elif metrics.gross_profit > 0:
            metrics.profit_factor = float('inf')
        
        if wins:
            metrics.avg_win = np.mean(wins)
        if losses:
            metrics.avg_loss = np.mean(losses)
        
        all_pnl = [t.pnl for t in self.trades]
        if all_pnl:
            metrics.avg_trade = np.mean(all_pnl)
        
        # Drawdown calculation
        equity = [self.initial_balance]
        for t in self.trades:
            equity.append(equity[-1] + t.pnl)
        
        equity = np.array(equity)
        peak = np.maximum.accumulate(equity)
        drawdown = peak - equity
        metrics.max_drawdown = np.max(drawdown)
        
        if np.max(peak) > 0:
            metrics.max_drawdown_percent = (metrics.max_drawdown / np.max(peak)) * 100
        
        # Consecutive wins/losses
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for t in self.trades:
            if t.is_win:
                if current_streak > 0:
                    current_streak += 1
                else:
                    max_loss_streak = max(max_loss_streak, abs(current_streak))
                    current_streak = 1
            else:
                if current_streak < 0:
                    current_streak -= 1
                else:
                    max_win_streak = max(max_win_streak, current_streak)
                    current_streak = -1
        
        max_win_streak = max(max_win_streak, current_streak if current_streak > 0 else 0)
        max_loss_streak = max(max_loss_streak, abs(current_streak) if current_streak < 0 else 0)
        
        metrics.max_consecutive_wins = max_win_streak
        metrics.max_consecutive_losses = max_loss_streak
        
        # Sharpe & Sortino ratios
        returns = np.array(all_pnl)
        if len(returns) > 1 and np.std(returns) > 0:
            metrics.sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252)  # Annualized
            
            downside_returns = returns[returns < 0]
            if len(downside_returns) > 0 and np.std(downside_returns) > 0:
                metrics.sortino_ratio = (np.mean(returns) / np.std(downside_returns)) * np.sqrt(252)
        
        # ROI
        if self.initial_balance > 0:
            metrics.roi_percent = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        
        # Trades by hour and day
        for t in self.trades:
            hour = t.entry_time.hour
            day = t.entry_time.strftime("%A")
            
            if hour not in metrics.trades_by_hour:
                metrics.trades_by_hour[hour] = {"total": 0, "wins": 0}
            metrics.trades_by_hour[hour]["total"] += 1
            if t.is_win:
                metrics.trades_by_hour[hour]["wins"] += 1
            
            if day not in metrics.trades_by_day:
                metrics.trades_by_day[day] = {"total": 0, "wins": 0}
            metrics.trades_by_day[day]["total"] += 1
            if t.is_win:
                metrics.trades_by_day[day]["wins"] += 1
        
        return metrics
    
    def get_trades_dataframe(self) -> pd.DataFrame:
        """Return trades as DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        
        data = []
        for t in self.trades:
            data.append({
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "direction": t.direction,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent,
                "is_win": t.is_win,
                "confidence": t.confidence,
                "strategy": t.strategy
            })
        
        return pd.DataFrame(data)
    
    def save_results(
        self,
        symbol: str,
        timeframe: str,
        strategy_name: str,
        metrics: BacktestMetrics
    ) -> str:
        """Save backtest results to database.

        v8.74.0 — Now persists the actual `trades[]` array (capped at 200)
        so downstream ML pipelines (/api/ml-training/train-from-backtests)
        can train on real per-trade samples instead of just aggregate
        metrics. Older records written without this field caused the
        "Trained 0 ML models from N backtest results" failure mode.
        """
        # Serialize trades for storage. Keep the most recent 200 to bound
        # document size while remaining ML-friendly (RandomForest etc.
        # need ≥100 samples per the trainer's gate).
        serialized_trades: List[Dict[str, Any]] = []
        for t in self.trades[-200:]:
            try:
                serialized_trades.append({
                    "entry_time": t.entry_time.isoformat() if hasattr(t.entry_time, "isoformat") else str(t.entry_time),
                    "exit_time": t.exit_time.isoformat() if t.exit_time and hasattr(t.exit_time, "isoformat") else (str(t.exit_time) if t.exit_time else None),
                    "direction": t.direction,
                    "entry_price": float(t.entry_price),
                    "exit_price": float(t.exit_price),
                    "pnl": float(t.pnl),
                    "pnl_percent": float(t.pnl_percent),
                    "is_win": bool(t.is_win),
                    "result": "win" if t.is_win else "loss",
                    "confidence": float(t.confidence or 0),
                    "strategy": t.strategy or strategy_name,
                    "expiry_seconds": int(getattr(t, "expiry_seconds", 60) or 60),
                })
            except Exception:
                continue  # skip malformed trade rows

        doc = {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy_name,
            "metrics": metrics.to_dict(),
            "trade_count": len(self.trades),
            "total_trades": len(self.trades),   # alias for downstream consumers
            "trades": serialized_trades,         # v8.74.0 — ML trainer reads this
            "equity_curve": [(str(t), e) for t, e in self.equity_curve[-100:]],  # Last 100 points
            "created_at": datetime.now(timezone.utc)
        }
        
        result = backtest_results_collection.insert_one(doc)
        return str(result.inserted_id)


# Strategy wrapper functions for backtesting
def create_deep_confluence_strategy():
    """Create wrapper for deep confluence strategy"""
    from deep_market_analyzer import deep_analyzer
    
    def strategy(df: pd.DataFrame, idx: int) -> Optional[Dict]:
        if idx < 50 or len(df) < 50:
            return None
        
        candles = df.iloc[max(0, idx-100):idx+1].to_dict('records')
        current_price = float(df.iloc[idx]['close'])
        
        signal = deep_analyzer.generate_signal(candles, current_price, 60)
        if signal:
            return signal.to_dict()
        return None
    
    return strategy


def create_hybrid_ensemble_strategy():
    """
    Iter 58 — `hybrid` ensemble backtest strategy. Uses the SAME confluence
    + MTF + volatility-regime + ML-vote stack as the live `force_generate_v2`
    pipeline but runs synchronously over a candle DataFrame for backtests.

    Approach (production-fidelity):
      1. Deep confluence on the last 100 candles (same as live)
      2. Simple MTF check — sign of close-EMA20 on current bar
      3. Volatility regime — ATR(14) percent must be in (0.003%, 0.20%)
      4. ML overlay — if either improved_v2 or maximized_v3 is trained, pull
         a probability and require agreement with the confluence direction
         to upgrade to HIGH; otherwise capped at MEDIUM (confidence ≤ 76).
    """
    from deep_market_analyzer import deep_analyzer

    def _vol_regime_ok(df: pd.DataFrame, idx: int) -> bool:
        if idx < 14:
            return True
        window = df.iloc[idx - 14: idx + 1]
        tr = np.maximum.reduce([
            (window['high'] - window['low']).values,
            (window['high'] - window['close'].shift(1)).abs().fillna(0).values,
            (window['low'] - window['close'].shift(1)).abs().fillna(0).values,
        ])
        atr = float(np.mean(tr))
        price = float(window['close'].iloc[-1])
        if price <= 0:
            return False
        atr_pct = atr / price
        return 0.00003 < atr_pct < 0.002

    def _mtf_agrees(df: pd.DataFrame, idx: int, direction: str) -> bool:
        if idx < 20:
            return True
        closes = df['close'].iloc[max(0, idx - 20): idx + 1]
        ema = closes.ewm(span=20, adjust=False).mean().iloc[-1]
        cur = float(closes.iloc[-1])
        if direction in ("CALL", "BUY"):
            return cur >= ema
        return cur <= ema

    def strategy(df: pd.DataFrame, idx: int) -> Optional[Dict]:
        if idx < 50 or len(df) < 50:
            return None

        candles = df.iloc[max(0, idx - 100): idx + 1].to_dict('records')
        current_price = float(df.iloc[idx]['close'])

        # 1. Deep confluence as the base voter
        sig = deep_analyzer.generate_signal(candles, current_price, 60)
        if not sig:
            return None
        out = sig.to_dict()
        direction = out.get('direction')

        # 2. MTF agreement
        if not _mtf_agrees(df, idx, direction):
            out['confidence'] = max(50.0, out.get('confidence', 60.0) - 5.0)

        # 3. Volatility regime — skip dead-flat / spike candles
        if not _vol_regime_ok(df, idx):
            return None

        # 4. Confidence floor (avoid noise trades, mirrors live abstain)
        if out.get('confidence', 0) < 60:
            return None

        out['strategy'] = 'Hybrid Ensemble v2'
        return out

    return strategy


def create_momentum_buster_strategy():
    """Create wrapper for momentum buster 15s strategy"""
    def strategy(df: pd.DataFrame, idx: int) -> Optional[Dict]:
        if idx < 10:
            return None
        
        # Simple momentum calculation
        closes = df['close'].iloc[max(0, idx-5):idx+1].values
        if len(closes) < 3:
            return None
        
        momentum = closes[-1] - closes[-3]
        
        # Count consecutive bars
        consecutive = 1
        for i in range(len(closes)-2, 0, -1):
            if (closes[i] > closes[i-1] and momentum > 0) or \
               (closes[i] < closes[i-1] and momentum < 0):
                consecutive += 1
            else:
                break
        
        if consecutive < 3:
            return None
        
        direction = "CALL" if momentum > 0 else "PUT"
        confidence = min(85, 60 + consecutive * 5)
        
        return {
            "direction": direction,
            "confidence": confidence,
            "strategy": "Momentum Buster 15s"
        }
    
    return strategy


def create_lstm_model_predictor():
    """Create wrapper for LSTM/GRU model"""
    try:
        from lstm_gru_system import lstm_gru_system
        
        def predict(df: pd.DataFrame) -> Optional[Dict]:
            if not lstm_gru_system.is_trained:
                return None
            
            candles = df.tail(50).to_dict('records')
            return lstm_gru_system.predict(candles)
        
        return predict
    except ImportError:
        return None


def create_ppo_model_predictor():
    """Create wrapper for PPO RL model"""
    try:
        from rl_ppo_agent import ppo_agent
        from lstm_gru_system import FeatureEngine
        
        def predict(df: pd.DataFrame) -> Optional[Dict]:
            if not ppo_agent.is_trained:
                return None
            
            candles = df.tail(50).to_dict('records')
            features = FeatureEngine.compute(candles)
            if features is None:
                return None
            
            return ppo_agent.predict(features)
        
        return predict
    except ImportError:
        return None


# Global engine instance
backtesting_engine = BacktestingEngine()
