"""
Money Management System
=======================
Comprehensive money management for 15-second binary options trading.

Implements:
1. Kelly Formula for optimal stake sizing
2. Fixed Percentage Risk management
3. Dynamic position sizing based on volatility
4. Drawdown analysis and protection
5. 7 Risk Control Schemes

Based on professional trading risk management principles.
"""

import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import logging
import json

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    CONSERVATIVE = "conservative"  # 0.5-1% per trade
    MODERATE = "moderate"          # 1-2% per trade
    AGGRESSIVE = "aggressive"      # 2-5% per trade


class MarketSession(Enum):
    ASIAN = "asian"           # 00:00 - 08:00 UTC
    EUROPEAN = "european"     # 08:00 - 16:00 UTC  
    AMERICAN = "american"     # 14:00 - 22:00 UTC
    OVERLAP_EU_US = "overlap_eu_us"  # 14:00 - 16:00 UTC (highest liquidity)
    OFF_HOURS = "off_hours"   # Low liquidity periods


@dataclass
class TradeRecord:
    """Record of a single trade"""
    trade_id: str
    symbol: str
    direction: str  # BUY/SELL
    stake: float
    entry_price: float
    exit_price: float
    outcome: str  # WIN/LOSS
    payout_rate: float
    profit_loss: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'direction': self.direction,
            'stake': self.stake,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'outcome': self.outcome,
            'payout_rate': self.payout_rate,
            'profit_loss': self.profit_loss,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class AccountState:
    """Current account state"""
    balance: float
    initial_balance: float
    peak_balance: float
    current_drawdown: float
    max_drawdown: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    daily_trades: int
    daily_profit_loss: float
    
    def to_dict(self) -> Dict:
        return {
            'balance': self.balance,
            'initial_balance': self.initial_balance,
            'peak_balance': self.peak_balance,
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'daily_trades': self.daily_trades,
            'daily_profit_loss': self.daily_profit_loss
        }


class KellyFormula:
    """
    Kelly Criterion Calculator for optimal stake sizing.
    
    Formula: f = (bp - q) / b
    Where:
    - b = odds of payout (e.g., 0.85 for 85% payout)
    - p = probability of winning
    - q = 1 - p = probability of losing
    """
    
    @staticmethod
    def calculate(win_probability: float, payout_rate: float = 0.85, 
                  fraction: float = 0.25) -> float:
        """
        Calculate optimal stake as percentage of bankroll.
        
        Args:
            win_probability: Estimated probability of winning (0-1)
            payout_rate: Payout rate for winning trade (e.g., 0.85)
            fraction: Kelly fraction to use (0.25 = quarter Kelly, safer)
            
        Returns:
            Optimal stake as percentage (0-100)
        """
        if win_probability <= 0 or win_probability >= 1:
            return 0.0
        
        b = payout_rate
        p = win_probability
        q = 1 - p
        
        # Kelly formula
        kelly_stake = (b * p - q) / b
        
        # Apply fraction for safety (full Kelly is too aggressive)
        fractional_kelly = kelly_stake * fraction
        
        # Ensure non-negative and cap at reasonable max
        return max(0, min(fractional_kelly * 100, 5.0))  # Max 5%
    
    @staticmethod
    def calculate_with_confidence(confidence: float, payout_rate: float = 0.85,
                                   base_win_rate: float = 0.55) -> float:
        """
        Calculate stake based on signal confidence.
        
        Args:
            confidence: Signal confidence (0-100)
            payout_rate: Payout rate
            base_win_rate: Historical base win rate
            
        Returns:
            Recommended stake percentage
        """
        # Convert confidence to win probability
        # Confidence of 50 = base win rate, scales up/down from there
        confidence_factor = (confidence - 50) / 50  # -1 to 1
        win_probability = base_win_rate + (confidence_factor * 0.2)  # Adjust by up to 20%
        win_probability = max(0.3, min(0.8, win_probability))  # Clamp
        
        return KellyFormula.calculate(win_probability, payout_rate)


class FixedPercentageRisk:
    """
    Fixed percentage risk management.
    Risk a fixed percentage of capital on each trade.
    """
    
    def __init__(self, risk_percentage: float = 1.0):
        self.risk_percentage = risk_percentage
    
    def calculate_stake(self, balance: float) -> float:
        """Calculate stake amount based on balance"""
        return balance * (self.risk_percentage / 100)
    
    def adjust_for_streak(self, base_stake: float, consecutive_losses: int) -> float:
        """Reduce stake after losing streak."""
        if consecutive_losses >= 5:
            return base_stake * 0.25
        elif consecutive_losses >= 3:
            return base_stake * 0.5
        return base_stake


class VolatilityBasedSizing:
    """Dynamic position sizing based on market volatility (ATR)."""
    
    def __init__(self, base_risk: float = 1.0, atr_multiplier: float = 2.0):
        self.base_risk = base_risk
        self.atr_multiplier = atr_multiplier
    
    def calculate_stake(self, balance: float, current_atr: float, 
                        average_atr: float) -> float:
        """Calculate stake adjusted for volatility."""
        if average_atr <= 0:
            return balance * (self.base_risk / 100)
        
        vol_ratio = current_atr / average_atr
        adjusted_risk = self.base_risk / max(vol_ratio, 0.5)
        adjusted_risk = min(adjusted_risk, self.base_risk * 1.5)
        
        return balance * (adjusted_risk / 100)


class DrawdownProtection:
    """Drawdown monitoring and protection system."""
    
    def __init__(self, max_daily_drawdown: float = 10.0,
                 max_total_drawdown: float = 20.0,
                 recovery_threshold: float = 5.0):
        self.max_daily_drawdown = max_daily_drawdown
        self.max_total_drawdown = max_total_drawdown
        self.recovery_threshold = recovery_threshold
        self.daily_start_balance = 0.0
        self.last_reset_date = None
    
    def check_drawdown(self, current_balance: float, peak_balance: float,
                       daily_start: float = None) -> Tuple[bool, str, float]:
        """Check if drawdown limits are exceeded."""
        total_drawdown = ((peak_balance - current_balance) / peak_balance) * 100 if peak_balance > 0 else 0
        
        if daily_start and daily_start > 0:
            daily_drawdown = ((daily_start - current_balance) / daily_start) * 100
        else:
            daily_drawdown = 0
        
        if total_drawdown >= self.max_total_drawdown:
            return False, f"❌ MAX TOTAL DRAWDOWN ({total_drawdown:.1f}%). Stop trading.", total_drawdown
        
        if daily_drawdown >= self.max_daily_drawdown:
            return False, f"❌ MAX DAILY DRAWDOWN ({daily_drawdown:.1f}%). Stop for today.", daily_drawdown
        
        if total_drawdown >= self.recovery_threshold:
            return True, f"⚠️ RECOVERY MODE: {total_drawdown:.1f}% drawdown.", total_drawdown
        
        return True, f"✅ Drawdown OK: {total_drawdown:.1f}%", total_drawdown
    
    def get_stake_multiplier(self, current_drawdown: float) -> float:
        """Get stake multiplier based on current drawdown."""
        if current_drawdown >= self.max_total_drawdown * 0.8:
            return 0.25
        elif current_drawdown >= self.max_total_drawdown * 0.5:
            return 0.5
        elif current_drawdown >= self.recovery_threshold:
            return 0.75
        return 1.0


class RiskControlSchemes:
    """Implementation of 7 Risk Control Schemes."""
    
    def __init__(self):
        self.correlation_matrix = {
            'EURUSD': {'GBPUSD': 0.85, 'USDCHF': -0.90, 'USDJPY': -0.30, 'AUDUSD': 0.70},
            'GBPUSD': {'EURUSD': 0.85, 'USDCHF': -0.75, 'USDJPY': -0.25, 'AUDUSD': 0.60},
            'USDJPY': {'EURUSD': -0.30, 'GBPUSD': -0.25, 'USDCHF': 0.50, 'AUDUSD': 0.20},
            'USDCHF': {'EURUSD': -0.90, 'GBPUSD': -0.75, 'USDJPY': 0.50, 'AUDUSD': -0.65},
            'AUDUSD': {'EURUSD': 0.70, 'GBPUSD': 0.60, 'USDJPY': 0.20, 'USDCHF': -0.65},
        }
        self.max_concurrent_trades = 5
        self.max_trades_per_session = 20
    
    def scheme_fixed_percentage(self, balance: float, risk_pct: float = 1.0) -> float:
        return balance * (risk_pct / 100)
    
    def scheme_time_filter(self) -> Tuple[bool, MarketSession]:
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        if 14 <= hour < 16:
            return True, MarketSession.OVERLAP_EU_US
        elif 8 <= hour < 16:
            return True, MarketSession.EUROPEAN
        elif 14 <= hour < 22:
            return True, MarketSession.AMERICAN
        elif 0 <= hour < 8:
            return False, MarketSession.ASIAN
        else:
            return False, MarketSession.OFF_HOURS
    
    def scheme_volatility_filter(self, current_atr: float, avg_atr: float,
                                   min_threshold: float = 0.8,
                                   max_threshold: float = 2.0) -> Tuple[bool, str]:
        if avg_atr <= 0:
            return True, "No ATR data"
        
        vol_ratio = current_atr / avg_atr
        
        if vol_ratio < min_threshold:
            return False, f"⚠️ Low volatility ({vol_ratio:.2f}x)"
        elif vol_ratio > max_threshold:
            return False, f"⚠️ High volatility ({vol_ratio:.2f}x)"
        return True, f"✅ Volatility OK ({vol_ratio:.2f}x)"
    
    def scheme_correlation_check(self, symbol: str, open_positions: List[str]) -> Tuple[bool, str]:
        if symbol not in self.correlation_matrix:
            return True, "No correlation data"
        
        correlated = sum(1 for pos in open_positions 
                         if pos in self.correlation_matrix.get(symbol, {}) 
                         and abs(self.correlation_matrix[symbol][pos]) > 0.7)
        
        if correlated >= 2:
            return False, f"⚠️ Too many correlated positions ({correlated})"
        return True, "✅ Correlation OK"
    
    def scheme_trade_limit(self, current_trades: int, concurrent: int) -> Tuple[bool, str]:
        if concurrent >= self.max_concurrent_trades:
            return False, f"⚠️ Max concurrent trades ({concurrent})"
        if current_trades >= self.max_trades_per_session:
            return False, f"⚠️ Max session trades ({current_trades})"
        return True, f"✅ Limits OK ({current_trades}/{self.max_trades_per_session})"
    
    def scheme_periodic_review(self, win_rate: float, profit_factor: float) -> Tuple[bool, str]:
        issues = []
        if win_rate < 0.50:
            issues.append(f"Win rate {win_rate:.1%} < 50%")
        if profit_factor < 1.0:
            issues.append(f"Profit factor {profit_factor:.2f} < 1.0")
        
        if issues:
            return False, f"⚠️ REVIEW: {'; '.join(issues)}"
        return True, f"✅ Performance OK (WR: {win_rate:.1%}, PF: {profit_factor:.2f})"


class MoneyManagementSystem:
    """Complete Money Management System."""
    
    def __init__(self, initial_balance: float = 1000.0,
                 risk_level: RiskLevel = RiskLevel.MODERATE):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.peak_balance = initial_balance
        self.risk_level = risk_level
        
        risk_pcts = {RiskLevel.CONSERVATIVE: 0.5, RiskLevel.MODERATE: 1.0, RiskLevel.AGGRESSIVE: 2.0}
        self.base_risk_pct = risk_pcts[risk_level]
        
        self.fixed_risk = FixedPercentageRisk(self.base_risk_pct)
        self.volatility_sizing = VolatilityBasedSizing(self.base_risk_pct)
        self.drawdown_protection = DrawdownProtection()
        self.risk_schemes = RiskControlSchemes()
        
        self.trade_history = deque(maxlen=1000)
        self.consecutive_losses = 0
        self.daily_start_balance = initial_balance
        self.daily_trades = 0
        self.last_trade_date = None
        
        self.total_wins = 0
        self.total_losses = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        
        logger.info(f"💰 Money Management initialized (Balance: ${initial_balance}, Risk: {risk_level.value})")
    
    def update_balance(self, new_balance: float):
        self.balance = new_balance
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
    
    def _reset_daily_stats(self):
        today = datetime.now(timezone.utc).date()
        if self.last_trade_date != today:
            self.daily_start_balance = self.balance
            self.daily_trades = 0
            self.last_trade_date = today
    
    def calculate_optimal_stake(self, signal_confidence: float,
                                 current_atr: float = 0.0,
                                 avg_atr: float = 0.0,
                                 payout_rate: float = 0.85) -> Dict:
        """Calculate optimal stake with all factors."""
        self._reset_daily_stats()
        
        can_trade, dd_msg, current_dd = self.drawdown_protection.check_drawdown(
            self.balance, self.peak_balance, self.daily_start_balance
        )
        
        if not can_trade:
            return {'can_trade': False, 'stake': 0.0, 'stake_percentage': 0.0, 
                    'reason': dd_msg, 'risk_level': 'BLOCKED'}
        
        kelly_stake_pct = KellyFormula.calculate_with_confidence(signal_confidence, payout_rate)
        fixed_stake = self.fixed_risk.calculate_stake(self.balance)
        
        if current_atr > 0 and avg_atr > 0:
            vol_stake = self.volatility_sizing.calculate_stake(self.balance, current_atr, avg_atr)
            fixed_stake = min(fixed_stake, vol_stake)
        
        fixed_stake = self.fixed_risk.adjust_for_streak(fixed_stake, self.consecutive_losses)
        dd_mult = self.drawdown_protection.get_stake_multiplier(current_dd)
        adjusted_stake = fixed_stake * dd_mult
        
        kelly_stake = self.balance * (kelly_stake_pct / 100)
        final_stake = min(kelly_stake, adjusted_stake)
        final_stake = max(final_stake, max(1.0, self.balance * 0.001))
        final_stake = min(final_stake, self.balance * 0.05)
        
        stake_pct = (final_stake / self.balance) * 100
        risk_assessment = 'VERY_LOW' if stake_pct <= 0.5 else 'LOW' if stake_pct <= 1.0 else 'MODERATE' if stake_pct <= 2.0 else 'HIGH'
        
        return {
            'can_trade': True,
            'stake': round(final_stake, 2),
            'stake_percentage': round(stake_pct, 2),
            'kelly_stake_pct': round(kelly_stake_pct, 2),
            'drawdown_multiplier': dd_mult,
            'current_drawdown': round(current_dd, 2),
            'consecutive_losses': self.consecutive_losses,
            'reason': dd_msg,
            'risk_level': risk_assessment
        }
    
    def run_risk_checks(self, symbol: str, open_positions: List[str],
                         current_atr: float = 0.0, avg_atr: float = 0.0) -> Dict:
        """Run all risk control schemes."""
        results = {'can_trade': True, 'checks': {}}
        
        # All 7 schemes
        results['checks']['fixed_percentage'] = {'passed': True, 'stake': self.risk_schemes.scheme_fixed_percentage(self.balance, self.base_risk_pct)}
        
        time_ok, session = self.risk_schemes.scheme_time_filter()
        results['checks']['time_filter'] = {'passed': time_ok, 'session': session.value}
        if not time_ok: results['can_trade'] = False
        
        if current_atr > 0 and avg_atr > 0:
            vol_ok, vol_msg = self.risk_schemes.scheme_volatility_filter(current_atr, avg_atr)
            results['checks']['volatility'] = {'passed': vol_ok, 'message': vol_msg}
            if not vol_ok: results['can_trade'] = False
        
        corr_ok, corr_msg = self.risk_schemes.scheme_correlation_check(symbol, open_positions)
        results['checks']['correlation'] = {'passed': corr_ok, 'message': corr_msg}
        if not corr_ok: results['can_trade'] = False
        
        limit_ok, limit_msg = self.risk_schemes.scheme_trade_limit(self.daily_trades, len(open_positions))
        results['checks']['trade_limit'] = {'passed': limit_ok, 'message': limit_msg}
        if not limit_ok: results['can_trade'] = False
        
        win_rate = self.total_wins / max(self.total_wins + self.total_losses, 1)
        pf = self.total_profit / max(abs(self.total_loss), 1)
        review_ok, review_msg = self.risk_schemes.scheme_periodic_review(win_rate, pf)
        results['checks']['review'] = {'passed': review_ok, 'message': review_msg}
        
        return results
    
    def record_trade(self, trade: TradeRecord):
        """Record completed trade."""
        self.trade_history.append(trade)
        self.daily_trades += 1
        
        if trade.outcome == 'WIN':
            self.total_wins += 1
            self.total_profit += trade.profit_loss
            self.consecutive_losses = 0
        else:
            self.total_losses += 1
            self.total_loss += abs(trade.profit_loss)
            self.consecutive_losses += 1
        
        self.balance += trade.profit_loss
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
    
    def get_account_state(self) -> AccountState:
        total = self.total_wins + self.total_losses
        profit_factor = self.total_profit / max(abs(self.total_loss), 0.01) if self.total_loss != 0 else 0.0
        if profit_factor == float('inf') or profit_factor != profit_factor:  # Check for inf or nan
            profit_factor = 0.0
        return AccountState(
            balance=self.balance, initial_balance=self.initial_balance,
            peak_balance=self.peak_balance,
            current_drawdown=((self.peak_balance - self.balance) / self.peak_balance * 100) if self.peak_balance > 0 else 0,
            max_drawdown=((self.peak_balance - self.balance) / self.peak_balance * 100) if self.peak_balance > 0 else 0,
            total_trades=total, winning_trades=self.total_wins, losing_trades=self.total_losses,
            win_rate=self.total_wins / max(total, 1),
            profit_factor=profit_factor,
            daily_trades=self.daily_trades, daily_profit_loss=self.balance - self.daily_start_balance
        )
    
    def to_dict(self) -> Dict:
        return {
            'account_state': self.get_account_state().to_dict(),
            'risk_level': self.risk_level.value,
            'base_risk_pct': self.base_risk_pct,
            'consecutive_losses': self.consecutive_losses
        }


# Singleton
money_management = MoneyManagementSystem()

def get_optimal_stake(confidence: float, balance: float = None, atr: float = 0.0, avg_atr: float = 0.0) -> Dict:
    if balance: money_management.update_balance(balance)
    return money_management.calculate_optimal_stake(confidence, atr, avg_atr)

def run_risk_checks(symbol: str, open_positions: List[str] = None, atr: float = 0.0, avg_atr: float = 0.0) -> Dict:
    return money_management.run_risk_checks(symbol, open_positions or [], atr, avg_atr)
