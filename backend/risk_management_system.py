"""
Advanced Risk Management & Drawdown Protection System
======================================================
Focuses on risk-adjusted returns (Sharpe ratio) and drawdown management.

Features:
1. Real-time Sharpe Ratio calculation
2. Maximum Drawdown monitoring with alerts
3. Kelly Criterion position sizing
4. Dynamic risk adjustment based on performance
5. Daily/Weekly loss limits
6. Drawdown-based trading pause
7. Risk per trade management
8. Profit factor tracking

Author: GPT Signal Bot
Version: 1.0.0
"""

import numpy as np
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level states for dynamic management."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"
    PAUSED = "paused"


@dataclass
class TradeResult:
    """Record of a single trade."""
    timestamp: datetime
    direction: str  # CALL or PUT
    amount: float
    pnl: float  # Profit/Loss in dollars
    win: bool
    asset: str = "UNKNOWN"
    confidence: float = 0.0
    
    @property
    def return_pct(self) -> float:
        """Return as percentage of trade amount."""
        if self.amount > 0:
            return (self.pnl / self.amount) * 100
        return 0.0


@dataclass
class RiskMetrics:
    """Current risk metrics snapshot."""
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    current_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    risk_level: RiskLevel
    trades_today: int
    daily_pnl: float
    weekly_pnl: float
    kelly_fraction: float
    recommended_risk_pct: float


class RiskManager:
    """
    Advanced Risk Management System for binary options trading.
    Implements Sharpe ratio tracking, drawdown protection, and dynamic position sizing.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize Risk Manager.
        
        Args:
            config: Configuration dictionary with risk parameters
        """
        config = config or {}
        
        # Account settings
        self.initial_balance = config.get('initial_balance', 1000.0)
        self.current_balance = self.initial_balance
        self.peak_balance = self.initial_balance
        
        # Risk parameters
        self.max_risk_per_trade = config.get('max_risk_per_trade', 0.02)  # 2%
        self.min_risk_per_trade = config.get('min_risk_per_trade', 0.005)  # 0.5%
        self.base_risk_per_trade = config.get('base_risk_per_trade', 0.01)  # 1%
        
        # Drawdown limits
        self.max_drawdown_limit = config.get('max_drawdown_limit', 0.15)  # 15%
        self.drawdown_warning = config.get('drawdown_warning', 0.08)  # 8%
        self.drawdown_critical = config.get('drawdown_critical', 0.12)  # 12%
        
        # Daily/Weekly limits
        self.daily_loss_limit = config.get('daily_loss_limit', 0.05)  # 5%
        self.weekly_loss_limit = config.get('weekly_loss_limit', 0.10)  # 10%
        self.max_trades_per_day = config.get('max_trades_per_day', 50)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 5)
        
        # Sharpe ratio parameters
        self.risk_free_rate = config.get('risk_free_rate', 0.02)  # 2% annual
        self.min_sharpe_for_trading = config.get('min_sharpe_for_trading', -0.5)
        
        # Trade history
        self.trade_history: List[TradeResult] = []
        self.daily_trades: deque = deque(maxlen=1000)  # Last 1000 trades
        
        # State tracking
        self.risk_level = RiskLevel.NORMAL
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.is_trading_paused = False
        self.pause_reason = None
        self.pause_until = None
        
        # Performance tracking
        self.session_start_time = datetime.now(timezone.utc)
        self.daily_start_balance = self.initial_balance
        self.weekly_start_balance = self.initial_balance
        
        logger.info(f"🛡️ Risk Manager initialized: Max DD {self.max_drawdown_limit*100}%, "
                   f"Daily limit {self.daily_loss_limit*100}%, Max trades/day {self.max_trades_per_day}")
    
    def update_balance(self, new_balance: float):
        """Update current balance and track peak."""
        self.current_balance = new_balance
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
    
    def record_trade(self, trade: TradeResult):
        """
        Record a completed trade and update all metrics.
        
        Args:
            trade: TradeResult object with trade details
        """
        self.trade_history.append(trade)
        self.daily_trades.append(trade)
        
        # Update balance
        self.current_balance += trade.pnl
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        # Update consecutive counters
        if trade.win:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        # Check risk conditions
        self._check_risk_conditions()
        
        logger.info(f"📊 Trade recorded: {'WIN' if trade.win else 'LOSS'} ${trade.pnl:.2f} | "
                   f"Balance: ${self.current_balance:.2f} | DD: {self.get_current_drawdown()*100:.1f}%")
    
    def _check_risk_conditions(self):
        """Check all risk conditions and update risk level."""
        current_dd = self.get_current_drawdown()
        daily_pnl_pct = self.get_daily_pnl() / self.daily_start_balance if self.daily_start_balance > 0 else 0
        trades_today = self.get_trades_today()
        
        # Check for trading pause conditions
        pause_reasons = []
        
        # Max drawdown reached
        if current_dd >= self.max_drawdown_limit:
            pause_reasons.append(f"Max drawdown reached: {current_dd*100:.1f}%")
            self.risk_level = RiskLevel.PAUSED
        
        # Daily loss limit reached
        elif daily_pnl_pct <= -self.daily_loss_limit:
            pause_reasons.append(f"Daily loss limit reached: {daily_pnl_pct*100:.1f}%")
            self.risk_level = RiskLevel.PAUSED
        
        # Too many consecutive losses
        elif self.consecutive_losses >= self.max_consecutive_losses:
            pause_reasons.append(f"Consecutive losses: {self.consecutive_losses}")
            self.risk_level = RiskLevel.PAUSED
        
        # Max trades per day
        elif trades_today >= self.max_trades_per_day:
            pause_reasons.append(f"Max daily trades reached: {trades_today}")
            self.risk_level = RiskLevel.PAUSED
        
        # Set risk level based on conditions
        elif current_dd >= self.drawdown_critical:
            self.risk_level = RiskLevel.CRITICAL
        elif current_dd >= self.drawdown_warning:
            self.risk_level = RiskLevel.HIGH
        elif self.consecutive_losses >= 3:
            self.risk_level = RiskLevel.ELEVATED
        else:
            self.risk_level = RiskLevel.NORMAL
        
        # Handle pause
        if pause_reasons:
            self.is_trading_paused = True
            self.pause_reason = "; ".join(pause_reasons)
            self.pause_until = datetime.now(timezone.utc) + timedelta(hours=1)
            logger.warning(f"⚠️ TRADING PAUSED: {self.pause_reason}")
        elif self.is_trading_paused and datetime.now(timezone.utc) > (self.pause_until or datetime.min.replace(tzinfo=timezone.utc)):
            # Auto-resume after pause period
            self.is_trading_paused = False
            self.pause_reason = None
            logger.info("✅ Trading resumed after pause period")
    
    def get_current_drawdown(self) -> float:
        """Calculate current drawdown from peak."""
        if self.peak_balance <= 0:
            return 0.0
        return (self.peak_balance - self.current_balance) / self.peak_balance
    
    def get_max_drawdown(self) -> float:
        """Calculate maximum historical drawdown."""
        if len(self.trade_history) < 2:
            return self.get_current_drawdown()
        
        # Calculate running max drawdown
        balance = self.initial_balance
        peak = balance
        max_dd = 0.0
        
        for trade in self.trade_history:
            balance += trade.pnl
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def calculate_sharpe_ratio(self, period_days: int = 30) -> float:
        """
        Calculate Sharpe ratio for the specified period.
        
        Args:
            period_days: Number of days to calculate over
            
        Returns:
            Annualized Sharpe ratio
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        recent_trades = [t for t in self.trade_history if t.timestamp >= cutoff]
        
        if len(recent_trades) < 5:
            return 0.0
        
        # Calculate returns
        returns = [t.return_pct / 100 for t in recent_trades]
        
        if len(returns) < 2:
            return 0.0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming ~20 trades per day)
        trades_per_year = len(recent_trades) / period_days * 252
        risk_free_per_trade = self.risk_free_rate / trades_per_year
        
        sharpe = (avg_return - risk_free_per_trade) / std_return
        
        # Annualize Sharpe
        annualized_sharpe = sharpe * np.sqrt(trades_per_year)
        
        return annualized_sharpe
    
    def calculate_sortino_ratio(self, period_days: int = 30) -> float:
        """
        Calculate Sortino ratio (uses downside deviation only).
        
        Args:
            period_days: Number of days to calculate over
            
        Returns:
            Annualized Sortino ratio
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        recent_trades = [t for t in self.trade_history if t.timestamp >= cutoff]
        
        if len(recent_trades) < 5:
            return 0.0
        
        returns = [t.return_pct / 100 for t in recent_trades]
        
        avg_return = np.mean(returns)
        
        # Calculate downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]
        if len(negative_returns) < 2:
            return 999.99 if avg_return > 0 else 0.0  # Use large finite value instead of inf
        
        downside_dev = np.std(negative_returns)
        
        if downside_dev == 0:
            return 999.99 if avg_return > 0 else 0.0  # Use large finite value instead of inf
        
        trades_per_year = len(recent_trades) / period_days * 252
        risk_free_per_trade = self.risk_free_rate / trades_per_year
        
        sortino = (avg_return - risk_free_per_trade) / downside_dev
        annualized_sortino = sortino * np.sqrt(trades_per_year)
        
        return annualized_sortino
    
    def calculate_kelly_fraction(self) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing.
        
        Kelly % = W - [(1-W) / R]
        Where:
            W = Win probability
            R = Win/Loss ratio
        
        Returns:
            Kelly fraction (0-1)
        """
        if len(self.trade_history) < 10:
            return self.base_risk_per_trade
        
        wins = [t for t in self.trade_history if t.win]
        losses = [t for t in self.trade_history if not t.win]
        
        if len(losses) == 0:
            return self.max_risk_per_trade
        
        win_rate = len(wins) / len(self.trade_history)
        
        avg_win = np.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = abs(np.mean([t.pnl for t in losses])) if losses else 1
        
        if avg_loss == 0:
            return self.max_risk_per_trade
        
        win_loss_ratio = avg_win / avg_loss
        
        # Kelly formula
        kelly = win_rate - ((1 - win_rate) / win_loss_ratio)
        
        # Apply half-Kelly for safety
        half_kelly = kelly / 2
        
        # Clamp to min/max risk
        return max(self.min_risk_per_trade, min(self.max_risk_per_trade, half_kelly))
    
    def get_recommended_position_size(self, confidence: float = 0.5) -> float:
        """
        Calculate recommended position size based on current risk conditions.
        
        Args:
            confidence: Signal confidence (0-1)
            
        Returns:
            Recommended trade amount in dollars
        """
        if self.is_trading_paused:
            return 0.0
        
        # Base risk from Kelly
        kelly_risk = self.calculate_kelly_fraction()
        
        # Adjust based on risk level
        risk_multipliers = {
            RiskLevel.NORMAL: 1.0,
            RiskLevel.ELEVATED: 0.75,
            RiskLevel.HIGH: 0.5,
            RiskLevel.CRITICAL: 0.25,
            RiskLevel.PAUSED: 0.0
        }
        
        risk_multiplier = risk_multipliers.get(self.risk_level, 0.5)
        
        # Adjust based on confidence
        confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5 to 1.0
        
        # Adjust based on current drawdown
        dd_multiplier = 1.0 - (self.get_current_drawdown() * 2)  # Reduce size as DD increases
        dd_multiplier = max(0.25, dd_multiplier)
        
        # Calculate final risk percentage
        final_risk_pct = kelly_risk * risk_multiplier * confidence_multiplier * dd_multiplier
        
        # Calculate position size
        position_size = self.current_balance * final_risk_pct
        
        # Apply minimum trade size
        min_trade = max(1.0, self.current_balance * 0.001)
        
        return max(min_trade, round(position_size, 2))
    
    def get_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        wins = [t for t in self.trade_history if t.win]
        losses = [t for t in self.trade_history if not t.win]
        
        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
        
        if gross_loss == 0:
            return 999.99 if gross_profit > 0 else 0.0  # Use large finite value instead of inf
        
        return gross_profit / gross_loss
    
    def get_win_rate(self) -> float:
        """Calculate overall win rate."""
        if len(self.trade_history) == 0:
            return 0.0
        wins = sum(1 for t in self.trade_history if t.win)
        return wins / len(self.trade_history)
    
    def get_daily_pnl(self) -> float:
        """Calculate today's P&L."""
        today = datetime.now(timezone.utc).date()
        today_trades = [t for t in self.trade_history if t.timestamp.date() == today]
        return sum(t.pnl for t in today_trades)
    
    def get_weekly_pnl(self) -> float:
        """Calculate this week's P&L."""
        week_start = datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_trades = [t for t in self.trade_history if t.timestamp >= week_start]
        return sum(t.pnl for t in week_trades)
    
    def get_trades_today(self) -> int:
        """Get number of trades today."""
        today = datetime.now(timezone.utc).date()
        return sum(1 for t in self.trade_history if t.timestamp.date() == today)
    
    def get_metrics(self) -> RiskMetrics:
        """Get comprehensive risk metrics snapshot."""
        wins = [t for t in self.trade_history if t.win]
        losses = [t for t in self.trade_history if not t.win]
        
        return RiskMetrics(
            sharpe_ratio=round(self.calculate_sharpe_ratio(), 2),
            sortino_ratio=round(self.calculate_sortino_ratio(), 2),
            max_drawdown=round(self.get_max_drawdown() * 100, 2),
            current_drawdown=round(self.get_current_drawdown() * 100, 2),
            win_rate=round(self.get_win_rate() * 100, 2),
            profit_factor=round(self.get_profit_factor(), 2),
            avg_win=round(np.mean([t.pnl for t in wins]), 2) if wins else 0,
            avg_loss=round(abs(np.mean([t.pnl for t in losses])), 2) if losses else 0,
            risk_level=self.risk_level,
            trades_today=self.get_trades_today(),
            daily_pnl=round(self.get_daily_pnl(), 2),
            weekly_pnl=round(self.get_weekly_pnl(), 2),
            kelly_fraction=round(self.calculate_kelly_fraction() * 100, 2),
            recommended_risk_pct=round(self.get_recommended_position_size(0.7) / self.current_balance * 100, 2) if self.current_balance > 0 else 0
        )
    
    def can_trade(self, confidence: float = 0.5) -> Tuple[bool, str]:
        """
        Check if trading is allowed based on current conditions.
        
        Args:
            confidence: Signal confidence (0-1)
            
        Returns:
            Tuple of (can_trade, reason)
        """
        # Check if paused
        if self.is_trading_paused:
            return False, f"Trading paused: {self.pause_reason}"
        
        # Check drawdown
        if self.get_current_drawdown() >= self.max_drawdown_limit:
            return False, f"Max drawdown exceeded: {self.get_current_drawdown()*100:.1f}%"
        
        # Check daily limits
        if self.get_trades_today() >= self.max_trades_per_day:
            return False, f"Daily trade limit reached: {self.get_trades_today()}"
        
        daily_pnl_pct = self.get_daily_pnl() / self.daily_start_balance if self.daily_start_balance > 0 else 0
        if daily_pnl_pct <= -self.daily_loss_limit:
            return False, f"Daily loss limit reached: {daily_pnl_pct*100:.1f}%"
        
        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"Too many consecutive losses: {self.consecutive_losses}"
        
        # Check Sharpe ratio (if enough history)
        if len(self.trade_history) > 20:
            sharpe = self.calculate_sharpe_ratio()
            if sharpe < self.min_sharpe_for_trading:
                return False, f"Sharpe ratio too low: {sharpe:.2f}"
        
        # All checks passed
        return True, "OK"
    
    def reset_daily(self):
        """Reset daily counters (call at start of trading day)."""
        self.daily_start_balance = self.current_balance
        logger.info(f"📅 Daily reset: Start balance ${self.daily_start_balance:.2f}")
    
    def reset_weekly(self):
        """Reset weekly counters (call at start of trading week)."""
        self.weekly_start_balance = self.current_balance
        self.reset_daily()
        logger.info(f"📅 Weekly reset: Start balance ${self.weekly_start_balance:.2f}")
    
    def force_resume(self):
        """Force resume trading (use with caution)."""
        self.is_trading_paused = False
        self.pause_reason = None
        self.pause_until = None
        self.consecutive_losses = 0
        self.risk_level = RiskLevel.ELEVATED
        logger.warning("⚠️ Trading force resumed - use caution!")
    
    def to_dict(self) -> Dict:
        """Export risk manager state to dictionary."""
        metrics = self.get_metrics()
        return {
            "current_balance": round(self.current_balance, 2),
            "peak_balance": round(self.peak_balance, 2),
            "initial_balance": round(self.initial_balance, 2),
            "total_trades": len(self.trade_history),
            "risk_level": self.risk_level.value,
            "is_paused": self.is_trading_paused,
            "pause_reason": self.pause_reason,
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "metrics": {
                "sharpe_ratio": metrics.sharpe_ratio,
                "sortino_ratio": metrics.sortino_ratio,
                "max_drawdown_pct": metrics.max_drawdown,
                "current_drawdown_pct": metrics.current_drawdown,
                "win_rate_pct": metrics.win_rate,
                "profit_factor": metrics.profit_factor,
                "avg_win": metrics.avg_win,
                "avg_loss": metrics.avg_loss,
                "kelly_fraction_pct": metrics.kelly_fraction,
                "recommended_risk_pct": metrics.recommended_risk_pct,
                "trades_today": metrics.trades_today,
                "daily_pnl": metrics.daily_pnl,
                "weekly_pnl": metrics.weekly_pnl
            },
            "limits": {
                "max_risk_per_trade_pct": self.max_risk_per_trade * 100,
                "max_drawdown_limit_pct": self.max_drawdown_limit * 100,
                "daily_loss_limit_pct": self.daily_loss_limit * 100,
                "max_trades_per_day": self.max_trades_per_day,
                "max_consecutive_losses": self.max_consecutive_losses
            }
        }


# Global instance with default config
risk_manager = RiskManager({
    'initial_balance': 1000.0,
    'max_risk_per_trade': 0.02,
    'max_drawdown_limit': 0.15,
    'daily_loss_limit': 0.05,
    'max_trades_per_day': 50
})


def get_risk_manager() -> RiskManager:
    """Get global risk manager instance."""
    return risk_manager
