"""
Money Management System for Pocket Option Trading
Implements advanced capital allocation, Martingale recovery, and profit targeting strategies
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

class AssetPayoutConfig(BaseModel):
    """Configuration for asset-specific payout percentages"""
    asset: str = Field(..., description="Asset symbol (e.g., EURUSD)")
    market_type: str = Field(..., description="Market type: 'regular' or 'otc'")
    payout_percentage: float = Field(..., ge=0, le=200, description="Payout % (e.g., 80 for 80%)")
    
    @validator('market_type')
    def validate_market_type(cls, v):
        if v not in ['regular', 'otc']:
            raise ValueError("market_type must be 'regular' or 'otc'")
        return v

class RiskManagementConfig(BaseModel):
    """Risk management rules configuration"""
    max_consecutive_losses: int = Field(default=5, ge=1, le=20, description="Max losses before stopping Martingale")
    max_stake_percentage: float = Field(default=10.0, ge=0.1, le=50.0, description="Max stake as % of balance")
    min_balance_threshold: float = Field(default=10.0, ge=0, description="Min balance before pausing trading")
    stop_loss_percentage: float = Field(default=30.0, ge=0, le=100, description="Stop if balance drops this % from starting")

class ProfitTarget(BaseModel):
    """Target profit calculation configuration"""
    target_amount: float = Field(..., gt=0, description="Desired profit amount (e.g., 50.00)")
    target_trades: int = Field(..., gt=0, description="Number of trades to reach target")
    strategy: str = Field(default="split_evenly", description="Strategy: 'split_evenly' or 'progressive'")
    
    @validator('strategy')
    def validate_strategy(cls, v):
        if v not in ['split_evenly', 'progressive']:
            raise ValueError("strategy must be 'split_evenly' or 'progressive'")
        return v

class TradeResult(BaseModel):
    """Result of a completed trade"""
    trade_id: str
    asset: str
    market_type: str
    direction: str  # CALL or PUT
    stake_amount: float
    payout_percentage: float
    won: bool
    profit_loss: float
    balance_after: float
    timestamp: datetime
    martingale_level: int = 0

class MoneyManagementSystem:
    """
    Advanced Money Management System for Binary Options Trading
    
    Features:
    - Target profit calculation (split evenly or progressive)
    - Martingale loss recovery with exact amount calculation
    - Per-asset payout percentage management
    - Comprehensive risk management controls
    - Real-time balance tracking
    """
    
    def __init__(
        self,
        starting_balance: float,
        asset_payouts: Dict[str, AssetPayoutConfig],
        risk_config: RiskManagementConfig
    ):
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.asset_payouts = asset_payouts  # Key: "ASSET_markettype"
        self.risk_config = risk_config
        
        # Trading state
        self.trade_history: List[TradeResult] = []
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.total_trades = 0
        self.total_profit_loss = 0.0
        
        # Martingale state
        self.martingale_active = False
        self.martingale_level = 0
        self.martingale_total_loss = 0.0
        self.martingale_sequence_trades: List[TradeResult] = []
        
        # Target profit state
        self.current_profit_target: Optional[ProfitTarget] = None
        self.trades_toward_target = 0
        
    def get_asset_payout_key(self, asset: str, market_type: str) -> str:
        """Generate key for asset payout lookup"""
        return f"{asset}_{market_type}"
    
    def get_payout_percentage(self, asset: str, market_type: str) -> float:
        """
        Get payout percentage for specific asset and market type
        
        Args:
            asset: Asset symbol
            market_type: 'regular' or 'otc'
            
        Returns:
            Payout percentage
            
        Raises:
            ValueError: If asset/market combination not configured
        """
        key = self.get_asset_payout_key(asset, market_type)
        
        if key not in self.asset_payouts:
            raise ValueError(
                f"Payout not configured for {asset} {market_type}. "
                f"Please configure payout percentage first."
            )
        
        return self.asset_payouts[key].payout_percentage
    
    def set_profit_target(self, target: ProfitTarget) -> Dict:
        """
        Set a new profit target and calculate trade amounts
        
        Args:
            target: ProfitTarget configuration
            
        Returns:
            Dictionary with calculation details
        """
        self.current_profit_target = target
        self.trades_toward_target = 0
        
        logger.info(f"Setting profit target: ${target.target_amount:.2f} in {target.target_trades} trades")
        
        if target.strategy == 'split_evenly':
            # Simple: divide target amount by number of trades
            # Account for fact that we need net profit (stake is returned on win)
            result = self._calculate_split_evenly(target)
        else:  # progressive
            # Progressive: compound wins to reach target faster
            result = self._calculate_progressive(target)
        
        return result
    
    def _calculate_split_evenly(self, target: ProfitTarget) -> Dict:
        """
        Calculate stake for split evenly strategy
        
        Formula: stake × payout% = profit per trade
        So: stake = (target_amount / target_trades) / (payout% / 100)
        
        Example: Want $50 in 10 trades with 80% payout
        Profit per trade = $50 / 10 = $5
        Stake needed = $5 / 0.80 = $6.25 per trade
        """
        profit_per_trade = target.target_amount / target.target_trades
        
        # Get average payout (user should ideally target similar payout assets)
        avg_payout = self._get_average_payout()
        
        stake_per_trade = profit_per_trade / (avg_payout / 100)
        
        # Calculate max balance needed (in case all trades lose before winning)
        max_drawdown = stake_per_trade * target.target_trades
        
        return {
            'strategy': 'split_evenly',
            'target_amount': target.target_amount,
            'target_trades': target.target_trades,
            'profit_per_trade': profit_per_trade,
            'average_payout_pct': avg_payout,
            'stake_per_trade': round(stake_per_trade, 2),
            'total_risk': round(stake_per_trade * target.target_trades, 2),
            'max_drawdown_estimate': round(max_drawdown, 2),
            'recommended_balance': round(max_drawdown * 1.5, 2),
            'affordable': self.current_balance >= stake_per_trade
        }
    
    def _calculate_progressive(self, target: ProfitTarget) -> Dict:
        """
        Calculate progressive compounding strategy
        
        Start with base stake, reinvest profits to compound growth
        """
        # Start with 1% of balance or minimum needed
        base_stake = max(self.current_balance * 0.01, 1.0)
        
        avg_payout = self._get_average_payout()
        payout_multiplier = avg_payout / 100
        
        # Simulate progressive strategy
        cumulative_profit = 0.0
        current_stake = base_stake
        stakes = []
        
        for i in range(target.target_trades):
            # Win this trade
            profit = current_stake * payout_multiplier
            cumulative_profit += profit
            stakes.append(current_stake)
            
            # Stop if we've reached target
            if cumulative_profit >= target.target_amount:
                break
            
            # Compound: next stake includes profit
            current_stake = base_stake + (cumulative_profit * 0.5)  # Reinvest 50% of profits
        
        trades_needed = len(stakes)
        
        return {
            'strategy': 'progressive',
            'target_amount': target.target_amount,
            'requested_trades': target.target_trades,
            'actual_trades_needed': trades_needed,
            'base_stake': round(base_stake, 2),
            'average_payout_pct': avg_payout,
            'stake_sequence': [round(s, 2) for s in stakes],
            'first_stake': round(stakes[0], 2),
            'last_stake': round(stakes[-1], 2),
            'total_risk': round(sum(stakes), 2),
            'recommended_balance': round(sum(stakes) * 1.5, 2),
            'affordable': self.current_balance >= base_stake
        }
    
    def _get_average_payout(self) -> float:
        """Calculate average payout percentage across configured assets"""
        if not self.asset_payouts:
            # Default to 80% if no assets configured
            logger.warning("No asset payouts configured, using default 80%")
            return 80.0
        
        total = sum(config.payout_percentage for config in self.asset_payouts.values())
        return total / len(self.asset_payouts)
    
    def calculate_next_stake(
        self,
        asset: str,
        market_type: str,
        is_forced: bool = False
    ) -> Dict:
        """
        Calculate stake amount for next trade
        
        Considers:
        - Current profit target (if active)
        - Martingale recovery (if active)
        - Risk management limits
        
        Args:
            asset: Asset symbol
            market_type: 'regular' or 'otc'
            is_forced: Whether to skip some safety checks
            
        Returns:
            Dictionary with stake calculation details
        """
        # Check if trading is allowed
        if not is_forced:
            can_trade, reason = self._check_can_trade()
            if not can_trade:
                return {
                    'can_trade': False,
                    'reason': reason,
                    'stake_amount': 0.0
                }
        
        # Get payout for this asset
        try:
            payout_pct = self.get_payout_percentage(asset, market_type)
        except ValueError as e:
            return {
                'can_trade': False,
                'reason': str(e),
                'stake_amount': 0.0
            }
        
        # Determine stake based on active strategy
        if self.martingale_active:
            # Martingale recovery mode
            stake = self._calculate_martingale_stake(asset, market_type, payout_pct)
            strategy = 'martingale_recovery'
        elif self.current_profit_target:
            # Profit target mode
            stake = self._calculate_target_stake(payout_pct)
            strategy = 'profit_target'
        else:
            # No active strategy - use base stake (1% of balance)
            stake = self.current_balance * 0.01
            strategy = 'base_stake'
        
        # Apply risk management limits
        max_stake = (self.current_balance * self.risk_config.max_stake_percentage) / 100
        if stake > max_stake:
            logger.warning(f"Stake ${stake:.2f} exceeds max allowed ${max_stake:.2f}, capping")
            stake = max_stake
        
        # Final check: can we afford this stake?
        affordable = stake <= self.current_balance
        
        return {
            'can_trade': affordable,
            'reason': 'OK' if affordable else f'Insufficient balance (need ${stake:.2f}, have ${self.current_balance:.2f})',
            'stake_amount': round(stake, 2),
            'strategy': strategy,
            'asset': asset,
            'market_type': market_type,
            'payout_percentage': payout_pct,
            'current_balance': round(self.current_balance, 2),
            'martingale_active': self.martingale_active,
            'martingale_level': self.martingale_level if self.martingale_active else 0,
            'consecutive_losses': self.consecutive_losses
        }
    
    def _calculate_martingale_stake(self, asset: str, market_type: str, payout_pct: float) -> float:
        """
        Calculate exact stake needed to recover all losses + target profit
        
        Formula: stake = (total_loss + target_profit) / (payout% / 100)
        
        Example: Lost $10 total, want to profit $5, payout is 80%
        stake = ($10 + $5) / 0.80 = $18.75
        If win: get back $18.75 + ($18.75 × 0.80) = $33.75
        Net: $33.75 - $18.75 - $10 (previous losses) = $5 profit ✓
        """
        # Total amount lost in this sequence
        total_loss = self.martingale_total_loss
        
        # Target profit per trade (if we have a profit target)
        if self.current_profit_target:
            target_profit = self.current_profit_target.target_amount / self.current_profit_target.target_trades
        else:
            # Default to recovering losses + 10% profit
            target_profit = total_loss * 0.10
        
        # Calculate exact stake needed
        # stake × (payout/100) = total_loss + target_profit
        # stake = (total_loss + target_profit) / (payout/100)
        payout_multiplier = payout_pct / 100
        stake = (total_loss + target_profit) / payout_multiplier
        
        logger.info(
            f"Martingale calculation: "
            f"Loss=${total_loss:.2f}, Target profit=${target_profit:.2f}, "
            f"Payout={payout_pct}%, Stake=${stake:.2f}"
        )
        
        return stake
    
    def _calculate_target_stake(self, payout_pct: float) -> float:
        """Calculate stake based on active profit target"""
        if self.current_profit_target.strategy == 'split_evenly':
            # Fixed stake per trade
            profit_per_trade = self.current_profit_target.target_amount / self.current_profit_target.target_trades
            stake = profit_per_trade / (payout_pct / 100)
        else:  # progressive
            # Increasing stake with compounding
            base_stake = self.current_balance * 0.01
            profit_so_far = self.total_profit_loss
            stake = base_stake + (profit_so_far * 0.5)  # Reinvest 50% of profits
        
        return stake
    
    def _check_can_trade(self) -> Tuple[bool, str]:
        """
        Check if trading is allowed based on risk management rules
        
        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        # Check minimum balance threshold
        if self.current_balance < self.risk_config.min_balance_threshold:
            return False, f"Balance below minimum threshold (${self.risk_config.min_balance_threshold:.2f})"
        
        # Check stop loss percentage
        loss_from_start = ((self.starting_balance - self.current_balance) / self.starting_balance) * 100
        if loss_from_start >= self.risk_config.stop_loss_percentage:
            return False, f"Stop loss triggered ({loss_from_start:.1f}% loss from starting balance)"
        
        # Check consecutive losses limit (only if Martingale active)
        if self.martingale_active and self.consecutive_losses >= self.risk_config.max_consecutive_losses:
            return False, f"Max consecutive losses reached ({self.consecutive_losses}/{self.risk_config.max_consecutive_losses})"
        
        return True, "OK"
    
    def record_trade_result(self, result: TradeResult) -> Dict:
        """
        Record a completed trade and update all states
        
        Args:
            result: TradeResult with trade outcome
            
        Returns:
            Dictionary with updated state information
        """
        # Add to history
        self.trade_history.append(result)
        self.total_trades += 1
        
        # Update balance
        self.current_balance = result.balance_after
        
        # Update profit/loss tracking
        self.total_profit_loss += result.profit_loss
        
        if result.won:
            # WIN
            logger.info(f"✅ WIN: {result.asset} {result.direction} - Profit: ${result.profit_loss:.2f}")
            
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            
            # If Martingale was active, sequence complete
            if self.martingale_active:
                logger.info(f"🎉 Martingale recovery successful after {self.martingale_level} levels")
                self._reset_martingale()
            
            # Update profit target progress
            if self.current_profit_target:
                self.trades_toward_target += 1
                if self.trades_toward_target >= self.current_profit_target.target_trades:
                    logger.info(f"🎯 Profit target reached! ${self.total_profit_loss:.2f}")
        
        else:
            # LOSS
            logger.info(f"❌ LOSS: {result.asset} {result.direction} - Loss: ${abs(result.profit_loss):.2f}")
            
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            
            # Activate or continue Martingale
            if not self.martingale_active:
                self.martingale_active = True
                self.martingale_level = 1
                self.martingale_total_loss = abs(result.profit_loss)
                self.martingale_sequence_trades = [result]
                logger.info(f"🔴 Martingale activated: Level {self.martingale_level}")
            else:
                self.martingale_level += 1
                self.martingale_total_loss += abs(result.profit_loss)
                self.martingale_sequence_trades.append(result)
                logger.warning(f"🔴 Martingale continues: Level {self.martingale_level}, Total loss: ${self.martingale_total_loss:.2f}")
        
        # Return updated state
        return self.get_state()
    
    def _reset_martingale(self):
        """Reset Martingale state after successful recovery"""
        self.martingale_active = False
        self.martingale_level = 0
        self.martingale_total_loss = 0.0
        self.martingale_sequence_trades = []
    
    def get_state(self) -> Dict:
        """
        Get current state of money management system
        
        Returns:
            Dictionary with comprehensive state information
        """
        # Calculate win rate
        if self.total_trades > 0:
            wins = sum(1 for t in self.trade_history if t.won)
            win_rate = (wins / self.total_trades) * 100
        else:
            win_rate = 0.0
        
        # Calculate profit/loss percentage
        pl_percentage = ((self.current_balance - self.starting_balance) / self.starting_balance) * 100
        
        return {
            'starting_balance': round(self.starting_balance, 2),
            'current_balance': round(self.current_balance, 2),
            'total_profit_loss': round(self.total_profit_loss, 2),
            'pl_percentage': round(pl_percentage, 2),
            'total_trades': self.total_trades,
            'win_rate': round(win_rate, 1),
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'martingale_state': {
                'active': self.martingale_active,
                'level': self.martingale_level,
                'total_loss': round(self.martingale_total_loss, 2),
                'sequence_trades': len(self.martingale_sequence_trades)
            },
            'profit_target': {
                'active': self.current_profit_target is not None,
                'target_amount': self.current_profit_target.target_amount if self.current_profit_target else 0,
                'trades_completed': self.trades_toward_target,
                'trades_total': self.current_profit_target.target_trades if self.current_profit_target else 0,
                'progress_pct': (self.trades_toward_target / self.current_profit_target.target_trades * 100) if self.current_profit_target else 0
            },
            'risk_management': {
                'can_trade': self._check_can_trade()[0],
                'reason': self._check_can_trade()[1],
                'max_consecutive_losses': self.risk_config.max_consecutive_losses,
                'max_stake_pct': self.risk_config.max_stake_percentage,
                'min_balance': self.risk_config.min_balance_threshold,
                'stop_loss_pct': self.risk_config.stop_loss_percentage
            }
        }
    
    def get_statistics(self) -> Dict:
        """
        Get detailed trading statistics
        
        Returns:
            Dictionary with comprehensive statistics
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'message': 'No trades recorded yet'
            }
        
        wins = [t for t in self.trade_history if t.won]
        losses = [t for t in self.trade_history if not t.won]
        
        # Calculate metrics
        total_won = sum(t.profit_loss for t in wins)
        total_lost = abs(sum(t.profit_loss for t in losses))
        avg_win = total_won / len(wins) if wins else 0
        avg_loss = total_lost / len(losses) if losses else 0
        
        # Profit factor
        profit_factor = total_won / total_lost if total_lost > 0 else float('inf')
        
        # Largest win/loss
        largest_win = max((t.profit_loss for t in wins), default=0)
        largest_loss = abs(min((t.profit_loss for t in losses), default=0))
        
        return {
            'total_trades': self.total_trades,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round((len(wins) / self.total_trades) * 100, 1),
            'total_profit': round(total_won, 2),
            'total_loss': round(total_lost, 2),
            'net_profit_loss': round(self.total_profit_loss, 2),
            'average_win': round(avg_win, 2),
            'average_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'largest_win': round(largest_win, 2),
            'largest_loss': round(largest_loss, 2),
            'current_balance': round(self.current_balance, 2),
            'roi_percentage': round(((self.current_balance - self.starting_balance) / self.starting_balance) * 100, 2)
        }
