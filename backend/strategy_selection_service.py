"""
Strategy Selection Service
Manages user strategy preferences for each timeframe
"""

import logging
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
import os

logger = logging.getLogger(__name__)


class StrategySelectionService:
    """Manages strategy selection for different timeframes"""

    # Iter 67 — empirically-best default strategy per timeframe
    # (3-day EURUSD_OTC backtest, May 29 2026, see scripts/evaluate_default_strategies.py).
    # When `selections[tf] == 'default'` the routing layer resolves it to the
    # mapped strategy below. This is the single source of truth — change here
    # to update the live default everywhere.
    DEFAULT_STRATEGY_PER_TIMEFRAME = {
        '5s':  '5s_heikin_fractal',        # 54.2% WR, 83 signals — beats deep_confluence by +7.7%
        '15s': '15s_ema_cascade',          # 58.3% WR, 48 signals — beats deep_confluence by +6.1%
        '30s': 'momentum_buster',          # 75.0% WR, 16 signals (small sample — confirm on real trades)
        '1m':  '1m_triple_ema',            # best in field on M1 OTC (47.1%) — flag for retraining
        '2m':  'ema_pullback',             # carried over: trend continuation suits 2m
        '3m':  'ema_pullback',             # carried over
        '5m':  'ema_pullback',             # carried over
    }

    # Available strategies per timeframe
    AVAILABLE_STRATEGIES = {
        '5s': [
            {'id': 'default', 'name': 'Default 5s Strategy', 'description': 'Ultra Precision V2 with Bollinger Bands'},
            {'id': '5s_heikin_fractal', 'name': '🆕 Heikin Ashi Fractal 5s', 'description': 'Single-indicator: Williams Fractal (period 3) on Heikin Ashi candles. Up fractal/red → BUY (CALL); down fractal/green → SELL (PUT). 5s expiry on 5s timeframe.', 'win_rate': '70-80% (target)', 'beta': True},
            {'id': 'ema20_pullback_reversal', 'name': 'EMA 20 Pullback Reversal', 'description': 'EMA 20 trend + RSI-2 + BB(5,2.5) + Stoch(3,1,1) pullback reversal. Best for 5s expiry on volatile OTC pairs.', 'win_rate': '80-90%'},
            {'id': 'holly_crossover_5s', 'name': 'Holly Crossover 5s', 'description': 'EMA(12) x WMA(23) reversal crossover with S/R confirmation. Catches trend reversals.', 'win_rate': '75-85%'},
            {'id': 'turbo_precision_5s', 'name': 'Turbo Precision 5s', 'description': 'RSI + Stochastic RSI + EMA Ribbon. 4+ confirmations. Highest accuracy.', 'win_rate': '75-85%'},
            {'id': 'micro_compression_burst', 'name': 'Micro Compression Burst', 'description': 'BB breakout after 4-6 tight candles. 30s expiry. Best for calm/OTC markets.', 'win_rate': '75-85%'},
            {'id': 'keltner_breakout', 'name': 'Keltner Channel Breakout', 'description': 'EMA(20) + ATR(10) bands. Enter on breakout with volume.', 'win_rate': '70-80%'},
            {'id': 'candlestick_patterns', 'name': 'Candlestick Patterns', 'description': 'Engulfing, Hammer, Doji, Morning/Evening Star patterns', 'win_rate': '65-75%'},
            {'id': 'rsi_bb_scalp', 'name': 'RSI + Bollinger Scalp', 'description': 'RSI oversold/overbought with BB for quick scalps', 'win_rate': '70-80%'},
            {'id': 'proven_supertrend', 'name': 'ProvenSignals SuperTrend', 'description': 'ATR 10, Multiplier 5 - Trend following'},
        ],
        '15s': [
            {'id': 'default', 'name': 'Default 15s Strategy', 'description': 'Fractal-based reversal strategy'},
            {'id': 'holly_crossover_15s', 'name': '⭐⭐⭐ Holly Crossover 15s', 'description': 'EMA(12) x WMA(23) reversal crossover with S/R confirmation. Catches trend reversals.', 'win_rate': '75-85%'},
            {'id': 'momentum_buster_15s', 'name': '⭐⭐⭐ Momentum Buster 15s', 'description': 'Momentum(3) green/red bars with reversal detection. Ultra-fast scalping.', 'win_rate': '70-80%'},
            {'id': 'starc_cci_reversal', 'name': '⭐ STARC Bands + CCI Reversal', 'description': 'STARC(15,5,1.3) + CCI(10). 1m expiry. Smooth rhythmic markets.', 'win_rate': '70-80%'},
            {'id': 'macd_histogram', 'name': '⭐ MACD Histogram Reversal', 'description': 'MACD(12,26,9) histogram color change + divergence', 'win_rate': '70-80%'},
            {'id': 'candlestick_patterns', 'name': '⭐ Candlestick Patterns', 'description': 'Engulfing, Hammer, Doji, Morning/Evening Star patterns', 'win_rate': '65-75%'},
            {'id': 'rsi_bb_scalp', 'name': '⭐ RSI + Bollinger Scalp', 'description': 'RSI oversold/overbought with BB for quick scalps', 'win_rate': '70-80%'},
            {'id': 'stochastic_rsi_combo', 'name': '⭐ Stochastic + RSI Combo', 'description': 'Double confirmation with Stochastic and RSI', 'win_rate': '70-80%'},
            {'id': 'rsi_volume', 'name': 'RSI + Volume Reversal', 'description': 'RSI(14) oversold/overbought with volume spikes'},
            {'id': 'bollinger_ema', 'name': 'Bollinger + EMA Breakout', 'description': 'BB(20,2) breakouts confirmed by EMA(20)'},
            {'id': 'macd_rsi', 'name': 'MACD + RSI Trend', 'description': 'MACD(12,26,9) with RSI trend confirmation'},
            {'id': 'proven_rsi', 'name': 'ProvenSignals RSI', 'description': 'RSI Period 5 with divergence - Catches trend reversals'},
        ],
        '30s': [
            {'id': 'default', 'name': 'Default 30s Strategy', 'description': 'SuperTrend + MA Crossover'},
            {'id': 'holly_crossover_30s', 'name': '⭐⭐⭐ Holly Crossover 30s', 'description': 'EMA(12) x WMA(23) reversal crossover with S/R confirmation. Catches trend reversals.', 'win_rate': '75-85%'},
            {'id': 'golden_one_moment', 'name': '⭐⭐⭐ Golden One Moment', 'description': 'RSI(2) + Stochastic(4,3,3) mean reversion crossover. Precise 30s entries.', 'win_rate': '75-85%'},
            {'id': '30s_fibonacci_confluence', 'name': '🆕 Fibonacci Confluence 30s [BETA]', 'description': 'Fib levels (23.6/38.2/50/61.8/78.6) + trend EMA + reversal candle + volume spike. 3/4 confirms required.', 'win_rate': '75%+ (target)', 'beta': True},
            {'id': '30s_triple_confirmation', 'name': '🆕 Triple Confirmation 30s [BETA]', 'description': 'Supply/Demand zone + MA+OSMA trend + reversal candle + Volume Oscillator. All 3 layers must agree.', 'win_rate': '78%+ (target)', 'beta': True},
            {'id': 'dynamic_ema_rsi', 'name': '⭐ Dynamic EMA + RSI Zone', 'description': 'EMA(13)/EMA(50) with RSI(14) 45-55 zone. 1m expiry.', 'win_rate': '75-85%'},
            {'id': 'otc_reverse', 'name': '⭐ OTC Market Reverse', 'description': 'RSI(7) + EMA(21) for OTC markets. Inverse signals on 3 losses.', 'win_rate': '70-80%'},
            {'id': 'keltner_breakout', 'name': '⭐ Keltner Channel Breakout', 'description': 'EMA(20) + ATR(10) bands. Enter on breakout.', 'win_rate': '70-80%'},
            {'id': 'rsi_bb_scalp', 'name': '⭐ RSI + Bollinger Scalp', 'description': 'RSI oversold/overbought with BB for quick scalps', 'win_rate': '70-80%'},
            {'id': 'stochastic_rsi_combo', 'name': '⭐ Stochastic + RSI Combo', 'description': 'Double confirmation with Stochastic and RSI', 'win_rate': '70-80%'},
            {'id': 'psar_fractals', 'name': 'Parabolic SAR + Fractals', 'description': 'SAR trend with fractal breakouts'},
            {'id': 'stochastic_adx', 'name': 'Stochastic + ADX', 'description': 'Stochastic(8,3,3) with ADX(14) momentum'},
            {'id': 'psar_stochastic', 'name': 'SAR + Stochastic', 'description': 'Combined SAR and Stochastic signals'},
        ],
        '1m': [
            {'id': 'default', 'name': 'Default 1m Strategy', 'description': 'High Accuracy strategies (Triple Confirmation, Williams/MACD, Smart Money)'},
            {'id': '1m_21s_reversal', 'name': '⭐⭐⭐ 21-Second Reversal', 'description': 'Timing contrarian — fires opposite 4-5s trade at 21s-left on 1m candle. Paired with Tampermonkey for precise execution.', 'win_rate': '65-78%'},
            {'id': '1m_fibonacci_confluence', 'name': '🆕 Fibonacci Confluence 1m [BETA]', 'description': 'Fib levels + EMA20 trend + engulfing/hammer candle + volume spike. 3/4 confirms required.', 'win_rate': '75%+ (target)', 'beta': True},
            {'id': '1m_triple_confirmation', 'name': '🆕 Triple Confirmation 1m [BETA]', 'description': 'Supply/Demand zones + trend + reversal candle + Volume Oscillator. All 3 layers must agree.', 'win_rate': '78%+ (target)', 'beta': True},
            {'id': 'turbo_precision_1m', 'name': '⭐⭐⭐ Turbo Precision 1m', 'description': 'RSI + Stochastic RSI + EMA Ribbon. 4+ confirmations. Highest accuracy.', 'win_rate': '75-85%'},
            {'id': '1m_momentum_exhaustion', 'name': '⭐⭐⭐ Momentum Exhaustion Reversal', 'description': 'RSI-2 + Stochastic + BB + Candlestick patterns. Catches reversals at momentum extremes.', 'win_rate': '70-75%'},
            {'id': '1m_quad_crossover', 'name': '⭐⭐ Quad SMA/EMA Crossover', 'description': '2/5/10 SMA + 20 EMA crossovers. 4 rule system with trend/counter-trend signals.', 'win_rate': '80-85%'},
            {'id': 'zigzag_double_ma', 'name': '⭐ ZigZag + Double MA', 'description': 'ZigZag(5,4,3) + SMA(3)/SMA(6). Clear swings without spikes.', 'win_rate': '75-85%'},
            {'id': 'triple_supertrend', 'name': '⭐ Triple SuperTrend Confirmation', 'description': '3 SuperTrends + Heikin Ashi. 5m expiry. London/NY overlap.', 'win_rate': '80-90%'},
            {'id': 'ema_pullback', 'name': '⭐ EMA Pullback Strategy', 'description': 'EMA(8)/EMA(21) pullback entries. Strong trend continuation.', 'win_rate': '75-85%'},
            {'id': 'rsi_sr_reversal', 'name': '⭐ RSI + Support/Resistance Reversal', 'description': 'RSI(14) at 30/70 + S/R zones with doji confirmation', 'win_rate': '75-85%'},
            {'id': 'triple_confirmation', 'name': 'Triple Confirmation', 'description': '90%+ accuracy with 5 indicator confirmation'},
            {'id': 'smart_money', 'name': 'Smart Money ICT', 'description': 'Order blocks, FVGs, liquidity sweeps'},
        ],
        '2m': [
            {'id': 'default', 'name': 'Default 2m Strategy', 'description': 'Combined trend and momentum analysis'},
            {'id': 'ema_pullback', 'name': '⭐ EMA Pullback Strategy', 'description': 'EMA(8)/EMA(21) pullback entries. Strong trend continuation.', 'win_rate': '75-85%'},
            {'id': 'ema_macd_trend', 'name': '⭐ EMA + MACD Trend', 'description': 'EMA(9)/EMA(21) crossover with MACD confirmation', 'win_rate': '75-85%'},
            {'id': 'stochastic_rsi_combo', 'name': '⭐ Stochastic + RSI Combo', 'description': 'Double confirmation with Stochastic and RSI', 'win_rate': '70-80%'},
            {'id': 'triple_confirmation', 'name': 'Triple Confirmation', 'description': '90%+ accuracy with 5 indicator confirmation'},
        ],
        '3m': [
            {'id': 'default', 'name': 'Default 3m Strategy', 'description': 'Combined RSI + BB + MACD'},
            {'id': 'ema_pullback', 'name': '⭐ EMA Pullback Strategy', 'description': 'EMA(8)/EMA(21) pullback entries. Strong trend continuation.', 'win_rate': '75-85%'},
            {'id': 'ema_macd_trend', 'name': '⭐ EMA + MACD Trend', 'description': 'EMA(9)/EMA(21) crossover with MACD confirmation', 'win_rate': '75-85%'},
            {'id': 'ichimoku_cci', 'name': 'Ichimoku + CCI', 'description': 'Ichimoku Cloud with CCI momentum'},
            {'id': 'atr_sr', 'name': 'ATR + Support/Resistance', 'description': 'Volatility-based with key levels'},
            {'id': 'cci_rsi', 'name': 'CCI + RSI', 'description': 'Dual momentum confirmation'},
        ],
        '5m': [
            {'id': 'default', 'name': 'Default 5m Strategy', 'description': 'Combined RSI + BB + MACD'},
            {'id': '5m_fibonacci_confluence', 'name': '🆕 Fibonacci Confluence 5m [BETA]', 'description': 'Deeper Fib swings (40-bar lookback) + EMA20 trend + engulfing/hammer + volume. Best for 5m range-bound markets.', 'win_rate': '75%+ (target)', 'beta': True},
            {'id': '5m_triple_confirmation', 'name': '🆕 Triple Confirmation 5m [BETA]', 'description': 'Supply/Demand zones + MACD/MA trend + reversal candle + Volume Oscillator. All 3 layers required.', 'win_rate': '78%+ (target)', 'beta': True},
            {'id': 'ema_pullback', 'name': '⭐ EMA Pullback Strategy', 'description': 'EMA(8)/EMA(21) pullback entries. Strong trend continuation.', 'win_rate': '75-85%'},
            {'id': 'ema_macd_trend', 'name': '⭐ EMA + MACD Trend', 'description': 'EMA(9)/EMA(21) crossover with MACD confirmation', 'win_rate': '75-85%'},
            {'id': 'vwap_momentum', 'name': '⭐ VWAP Momentum', 'description': 'Volume-weighted momentum with EMA(9)', 'win_rate': '70-75%'},
            {'id': 'ichimoku_cci', 'name': 'Ichimoku + CCI', 'description': 'Ichimoku Cloud with CCI momentum'},
            {'id': 'atr_sr', 'name': 'ATR + Support/Resistance', 'description': 'Volatility-based with key levels'},
            {'id': 'cci_rsi', 'name': 'CCI + RSI', 'description': 'Dual momentum confirmation'},
        ],
    }
    
    def __init__(self):
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'trading_bot_db')
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db.strategy_selections
        # Iter 53: lazily merge in any strategies registered in strategy_registry
        # so newly-built strategies automatically appear in the UI dropdown
        # (prevents the "not showing up" issue we hit with 5s_heikin_fractal).
        self._auto_discovered = False
    
    def _auto_discover_from_registry(self):
        """
        Append any strategy_registry strategies missing from the curated
        AVAILABLE_STRATEGIES list. Curated entries (with descriptions /
        win-rate badges) always take precedence; this only adds NEW ones.
        Idempotent — runs at most once per process.
        """
        if self._auto_discovered:
            return
        self._auto_discovered = True
        try:
            from strategy_registry import strategy_registry
        except Exception as e:
            logger.warning(f"Could not import strategy_registry for auto-discovery: {e}")
            return
        
        added = 0
        for name, strat in strategy_registry.strategies.items():
            if strat is None:
                continue
            tf = getattr(strat, 'timeframe', None)
            if not tf or tf not in self.AVAILABLE_STRATEGIES:
                continue
            existing_ids = {s['id'] for s in self.AVAILABLE_STRATEGIES[tf]}
            if name in existing_ids:
                continue
            display_name = getattr(strat, 'name', name)
            acc = getattr(strat, 'accuracy_target', None)
            beta = bool(getattr(strat, 'beta', False))
            entry = {
                'id': name,
                'name': display_name if not beta else f'🆕 {display_name} [BETA]',
                'description': getattr(strat, 'description', f'Auto-discovered: {display_name}'),
            }
            if acc:
                entry['win_rate'] = f'{acc}% (target)' if isinstance(acc, (int, float)) else str(acc)
            if beta:
                entry['beta'] = True
            self.AVAILABLE_STRATEGIES[tf].append(entry)
            added += 1
        
        if added:
            logger.info(f"✨ Auto-discovered {added} strategies from registry into selection UI")
        
    async def get_selected_strategies(self) -> Dict[str, str]:
        """
        Get user's selected strategies for all timeframes.
        Returns dict of {timeframe: strategy_id}.

        Iter 67 — when a TF is set to 'default', we transparently resolve it
        to the empirical winner in DEFAULT_STRATEGY_PER_TIMEFRAME so the
        signal-generation layer always gets a concrete strategy id.
        """
        try:
            config = await self.collection.find_one({'type': 'strategy_selection'})
            raw = (config or {}).get('selections', {}) if config else {}
            # If nothing saved, start from a default sheet
            if not raw:
                raw = {tf: 'default' for tf in self.DEFAULT_STRATEGY_PER_TIMEFRAME}
            resolved = {}
            for tf, sid in raw.items():
                if sid == 'default':
                    resolved[tf] = self.DEFAULT_STRATEGY_PER_TIMEFRAME.get(tf, 'default')
                else:
                    resolved[tf] = sid
            return resolved
        except Exception as e:
            logger.error(f"Error getting selected strategies: {e}")
            return {}

    def resolve_default(self, timeframe: str) -> str:
        """Return the empirical-winner strategy id for `timeframe`, or 'default'."""
        return self.DEFAULT_STRATEGY_PER_TIMEFRAME.get(timeframe, 'default')

    async def get_raw_selections(self) -> Dict[str, str]:
        """Return saved selections as-is, without resolving 'default'."""
        try:
            config = await self.collection.find_one({'type': 'strategy_selection'})
            return (config or {}).get('selections', {}) if config else {}
        except Exception as e:
            logger.error(f"Error getting raw selections: {e}")
            return {}
    
    async def update_strategy_selection(self, timeframe: str, strategy_id: str) -> bool:
        """Update strategy selection for a specific timeframe"""
        try:
            # Validate timeframe and strategy
            if timeframe not in self.AVAILABLE_STRATEGIES:
                logger.error(f"Invalid timeframe: {timeframe}")
                return False

            # Iter 82 — accept 'default', curated/registry strategies, and any
            # published custom strategy that declares this timeframe.
            if not await self.is_valid_selection(timeframe, strategy_id):
                logger.error(
                    f"Invalid strategy ID {strategy_id} for timeframe {timeframe}"
                )
                return False
            
            # Update or create selection
            await self.collection.update_one(
                {'type': 'strategy_selection'},
                {'$set': {f'selections.{timeframe}': strategy_id}},
                upsert=True
            )
            
            logger.info(f"Updated strategy for {timeframe} to {strategy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating strategy selection: {e}")
            return False
    
    async def get_strategy_details(self, timeframe: str, strategy_id: str) -> Optional[Dict]:
        """Get details for a specific strategy"""
        try:
            if timeframe not in self.AVAILABLE_STRATEGIES:
                return None
            
            for strategy in self.AVAILABLE_STRATEGIES[timeframe]:
                if strategy['id'] == strategy_id:
                    return strategy
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting strategy details: {e}")
            return None
    
    def get_available_strategies(self, timeframe: str) -> List[Dict]:
        """Get all available strategies for a timeframe"""
        self._auto_discover_from_registry()
        return self.AVAILABLE_STRATEGIES.get(timeframe, [])
    
    def get_all_available_strategies(self) -> Dict[str, List[Dict]]:
        """Get all available strategies for all timeframes"""
        self._auto_discover_from_registry()
        return self.AVAILABLE_STRATEGIES

    # ------------------------------------------------------------------
    # Iter 82 — merge in published custom strategies.
    # Sync `get_available_strategies*` above returns ONLY curated + registry
    # entries so we don't touch every legacy caller. The async variants below
    # additionally merge in `is_published=True` docs from `custom_strategies`.
    # ------------------------------------------------------------------
    async def _fetch_published_customs(
        self, timeframe: Optional[str] = None
    ) -> List[Dict]:
        """Fetch published custom strategies (optionally filtered by TF)."""
        try:
            db = self.collection.database
            q: Dict[str, Any] = {"is_published": True}
            if timeframe:
                q["timeframes"] = timeframe
            docs = await db.custom_strategies.find(q, {"_id": 0}).to_list(500)
            # Coerce into the same shape as curated entries
            out = []
            for d in docs:
                out.append({
                    "id": d.get("id"),
                    "name": f"🛠 {d.get('name') or 'Custom Strategy'}",
                    "description": d.get("description") or "User-built custom strategy",
                    "custom": True,
                    "is_active": bool(d.get("is_active", True)),
                    "is_published": True,
                    "timeframes": d.get("timeframes") or [],
                    "win_rate": (
                        f"{d.get('win_rate', 0):.1f}%"
                        if isinstance(d.get('win_rate'), (int, float)) and d.get('win_rate')
                        else None
                    ),
                })
            return out
        except Exception as e:
            logger.warning(f"[strategy_selection] fetch_published_customs failed: {e}")
            return []

    async def get_available_strategies_with_customs(
        self, timeframe: str
    ) -> List[Dict]:
        """Curated + auto-discovered + published customs for one TF."""
        base = list(self.get_available_strategies(timeframe))
        customs = await self._fetch_published_customs(timeframe)
        # Prevent id collisions — customs win if same id somehow appears
        base_ids = {s.get("id") for s in base}
        merged = base + [c for c in customs if c.get("id") not in base_ids]
        return merged

    async def get_all_available_strategies_with_customs(
        self,
    ) -> Dict[str, List[Dict]]:
        """Same as `get_all_available_strategies` but includes published customs."""
        merged: Dict[str, List[Dict]] = {}
        for tf in self.AVAILABLE_STRATEGIES.keys():
            merged[tf] = list(self.AVAILABLE_STRATEGIES[tf])
        customs = await self._fetch_published_customs(None)
        for c in customs:
            for tf in (c.get("timeframes") or []):
                if tf not in merged:
                    merged[tf] = []
                if not any(s.get("id") == c.get("id") for s in merged[tf]):
                    merged[tf].append(c)
        return merged

    async def is_valid_selection(self, timeframe: str, strategy_id: str) -> bool:
        """
        True if `strategy_id` is a valid selection for `timeframe` — either
        curated/registry OR a published custom strategy that declares this TF.
        """
        if strategy_id == "default":
            return timeframe in self.DEFAULT_STRATEGY_PER_TIMEFRAME
        # Curated / registry
        if timeframe in self.AVAILABLE_STRATEGIES:
            if any(s["id"] == strategy_id for s in self.AVAILABLE_STRATEGIES[timeframe]):
                return True
        # Published customs
        customs = await self._fetch_published_customs(timeframe)
        return any(c.get("id") == strategy_id for c in customs)


# Global instance
strategy_selection_service = StrategySelectionService()
