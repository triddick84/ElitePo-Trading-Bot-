"""
Signal Setup Validator & Configuration Guide
Ensures users have correct Pocket Option settings to match signal generation conditions

This module generates detailed setup instructions for each signal,
ensuring the technical analysis conditions match the trading platform settings.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from pocket_option_timing_sync import pocket_option_sync

logger = logging.getLogger(__name__)


class SignalSetupValidator:
    """
    Validates and generates setup instructions for trading signals
    Ensures Pocket Option platform settings match signal generation conditions
    """
    
    def __init__(self):
        self.chart_type_display = {
            'japanese_candles': 'Japanese Candles',
            'heikin_ashi': 'Heikin Ashi',
            'line': 'Line Chart',
            'bars': 'Bars',
            'area': 'Area Chart'
        }
        
        self.timeframe_display = {
            '5s': '5 seconds',
            '15s': '15 seconds',
            '30s': '30 seconds',
            '1m': '1 minute',
            '2m': '2 minutes',
            '3m': '3 minutes',
            '5m': '5 minutes',
            '15m': '15 minutes',
            '30m': '30 minutes',
            '1h': '1 hour'
        }
        
        logger.info("✅ Signal Setup Validator initialized")
    
    def generate_setup_guide(
        self,
        signal: Dict,
        symbol: str,
        chart_type: str,
        timeframe: str,
        expiration: str,
        market_type: str = 'otc'
    ) -> Dict:
        """
        Generate comprehensive setup guide for a signal
        
        Args:
            signal: The generated signal dictionary
            symbol: Trading symbol (e.g., EURUSD)
            chart_type: Chart type used for analysis
            timeframe: Chart timeframe used for analysis
            expiration: Trade expiration time
            market_type: 'otc' or 'regular'
        
        Returns:
            Complete setup guide with step-by-step instructions
        """
        try:
            # Calculate next candle formation time
            chicago_time = pocket_option_sync.get_chicago_time()
            next_candle = pocket_option_sync.get_next_candle_formation_time(
                timeframe,
                market_type,
                apply_latency_compensation=True
            )
            
            # Calculate time until next candle
            seconds_to_candle = (next_candle - chicago_time).total_seconds()
            
            # Format symbol for display
            display_symbol = f"{symbol}_{market_type.upper()}"
            
            # Generate setup instructions
            setup_guide = {
                'signal_id': signal.get('id', 'N/A'),
                'strategy': signal.get('strategy', 'Unknown'),
                'direction': signal.get('direction', 'UNKNOWN'),
                'confidence': signal.get('confidence', 0),
                
                # Critical Settings
                'critical_settings': {
                    'asset': {
                        'required': display_symbol,
                        'description': f'Select {symbol} on {market_type.upper()} market',
                        'location': 'Asset Selection Dropdown (Top Left)',
                        'critical': True
                    },
                    'chart_timeframe': {
                        'required': self.timeframe_display.get(timeframe, timeframe),
                        'description': f'Set chart to {self.timeframe_display.get(timeframe, timeframe)} timeframe',
                        'location': 'Chart Timeframe Selector (Bottom Left)',
                        'critical': True
                    },
                    'chart_type': {
                        'required': self.chart_type_display.get(chart_type, chart_type),
                        'description': f'Set chart display to {self.chart_type_display.get(chart_type, chart_type)}',
                        'location': 'Chart Settings (Bottom Right)',
                        'critical': True
                    },
                    'expiration_time': {
                        'required': self.timeframe_display.get(expiration, expiration),
                        'description': f'Set trade expiration to {self.timeframe_display.get(expiration, expiration)}',
                        'location': 'Expiration Time Selector (Right Side)',
                        'critical': True
                    },
                    'market_type': {
                        'required': market_type.upper(),
                        'description': f'Ensure you\'re on {market_type.upper()} market (check asset suffix)',
                        'location': 'Asset name should end with _OTC',
                        'critical': True
                    }
                },
                
                # Timing Settings
                'timing_settings': {
                    'candle_sync_enabled': True,
                    'next_candle_time': next_candle.isoformat(),
                    'seconds_to_next_candle': round(seconds_to_candle, 1),
                    'optimal_entry_time': 'Within first 5-10 seconds of new candle',
                    'chicago_time_now': chicago_time.isoformat(),
                    'recommendation': self._get_timing_recommendation(seconds_to_candle)
                },
                
                # Bot Control Settings
                'bot_control': {
                    'auto_trading': False,
                    'manual_execution_required': True,
                    'sound_alerts': True,
                    'notification_settings': 'Enable for signal alerts'
                },
                
                # Technical Indicators (for verification)
                'indicators_used': self._extract_indicators(signal),
                
                # Step-by-Step Instructions
                'setup_steps': self._generate_setup_steps(
                    display_symbol,
                    chart_type,
                    timeframe,
                    expiration,
                    market_type,
                    seconds_to_candle
                ),
                
                # Validation Checklist
                'pre_trade_checklist': self._generate_checklist(
                    display_symbol,
                    chart_type,
                    timeframe,
                    expiration,
                    market_type
                ),
                
                # Risk Management
                'risk_management': {
                    'recommended_stake': signal.get('suggested_stake', 2.0),
                    'max_stake_percentage': '1-2% of account balance',
                    'stop_loss_rule': 'Max 3 consecutive losses, then pause',
                    'daily_limit': '5-10 trades maximum',
                    'confidence_threshold': 'Only trade signals with 85%+ confidence'
                },
                
                # Expected Technical Analysis Match
                'expected_conditions': self._generate_expected_conditions(signal, timeframe),
                
                # Warnings
                'warnings': self._generate_warnings(seconds_to_candle, signal)
            }
            
            return setup_guide
            
        except Exception as e:
            logger.error(f"Error generating setup guide: {e}")
            return self._get_fallback_guide(signal, symbol, timeframe, expiration)
    
    def _get_timing_recommendation(self, seconds_to_candle: float) -> str:
        """Generate timing recommendation based on time to next candle"""
        if seconds_to_candle < 5:
            return "⚡ EXECUTE NOW - Candle forming imminently"
        elif seconds_to_candle < 15:
            return f"⏰ WAIT {int(seconds_to_candle)}s - Prepare for entry"
        elif seconds_to_candle < 30:
            return f"⏳ Wait ~{int(seconds_to_candle)}s for optimal entry"
        elif seconds_to_candle < 60:
            return f"⌛ Wait {int(seconds_to_candle)}s - Review setup during wait"
        else:
            return f"📅 Next candle in {int(seconds_to_candle/60)}min {int(seconds_to_candle%60)}s"
    
    def _extract_indicators(self, signal: Dict) -> List[Dict]:
        """Extract technical indicators used in signal generation"""
        indicators = []
        tech_analysis = signal.get('technical_analysis', {})
        
        # Common indicators
        if 'rsi_7' in tech_analysis or 'rsi_14' in tech_analysis:
            rsi_val = tech_analysis.get('rsi_7') or tech_analysis.get('rsi_14')
            indicators.append({
                'name': 'RSI',
                'value': rsi_val,
                'setting': 'Period: 7 or 14'
            })
        
        if 'bb_position' in tech_analysis:
            indicators.append({
                'name': 'Bollinger Bands',
                'value': f"{tech_analysis['bb_position']:.1%} position",
                'setting': 'Period: 20, StdDev: 2'
            })
        
        if 'stochastic_k' in tech_analysis:
            indicators.append({
                'name': 'Stochastic',
                'value': f"K: {tech_analysis['stochastic_k']:.1f}",
                'setting': 'K: 14, D: 3, Smooth: 3'
            })
        
        if 'macd_histogram' in tech_analysis:
            indicators.append({
                'name': 'MACD',
                'value': f"Histogram: {tech_analysis['macd_histogram']:.5f}",
                'setting': 'Fast: 12, Slow: 26, Signal: 9'
            })
        
        if 'adx' in tech_analysis:
            indicators.append({
                'name': 'ADX',
                'value': f"{tech_analysis['adx']:.1f}",
                'setting': 'Period: 14'
            })
        
        return indicators
    
    def _generate_setup_steps(
        self,
        symbol: str,
        chart_type: str,
        timeframe: str,
        expiration: str,
        market_type: str,
        seconds_to_candle: float
    ) -> List[Dict]:
        """Generate step-by-step setup instructions"""
        steps = [
            {
                'step': 1,
                'action': 'Open Pocket Option Platform',
                'details': 'Go to https://pocketoption.com/ and login',
                'verification': 'Confirm you are logged in',
                'completed': False
            },
            {
                'step': 2,
                'action': f'Select Asset: {symbol}',
                'details': f'Click asset dropdown (top left) and select {symbol}',
                'verification': f'Asset name displays as {symbol}',
                'completed': False
            },
            {
                'step': 3,
                'action': f'Verify Market Type: {market_type.upper()}',
                'details': f'Ensure asset name shows _{market_type.upper()} suffix',
                'verification': f'Asset shows as {symbol} (not {symbol.replace("_OTC", "").replace("_otc", "")})',
                'completed': False
            },
            {
                'step': 4,
                'action': f'Set Chart Timeframe: {self.timeframe_display.get(timeframe, timeframe)}',
                'details': 'Click timeframe selector at bottom left of chart',
                'verification': f'Chart shows {self.timeframe_display.get(timeframe, timeframe)} candles',
                'completed': False
            },
            {
                'step': 5,
                'action': f'Set Chart Type: {self.chart_type_display.get(chart_type, chart_type)}',
                'details': 'Click chart settings icon (gear) at bottom right',
                'verification': f'Chart displays as {self.chart_type_display.get(chart_type, chart_type)}',
                'completed': False
            },
            {
                'step': 6,
                'action': f'Set Expiration Time: {self.timeframe_display.get(expiration, expiration)}',
                'details': 'Select expiration time from right-side panel',
                'verification': f'Expiration shows {self.timeframe_display.get(expiration, expiration)}',
                'completed': False
            },
            {
                'step': 7,
                'action': 'Enable Candle Synchronization',
                'details': 'This signal is timed to start at new candle formation',
                'verification': 'Wait for new candle to form before entry',
                'completed': False
            },
            {
                'step': 8,
                'action': f'Wait for Next Candle ({int(seconds_to_candle)}s)',
                'details': 'Monitor countdown to next candle formation',
                'verification': 'New candle appears on chart',
                'completed': False
            },
            {
                'step': 9,
                'action': 'Execute Trade at Candle Open',
                'details': f'Click {signal.get("direction", "BUY/SELL")} within first 5-10 seconds of new candle',
                'verification': 'Trade placed at optimal entry timing',
                'completed': False
            },
            {
                'step': 10,
                'action': 'Set Trade Amount',
                'details': f'Enter stake amount (recommended: ${signal.get("suggested_stake", 2.0)})',
                'verification': 'Amount follows risk management rules (1-2% of balance)',
                'completed': False
            }
        ]
        
        return steps
    
    def _generate_checklist(
        self,
        symbol: str,
        chart_type: str,
        timeframe: str,
        expiration: str,
        market_type: str
    ) -> List[Dict]:
        """Generate pre-trade validation checklist"""
        return [
            {
                'item': f'Asset is {symbol}',
                'category': 'Asset',
                'critical': True,
                'checked': False
            },
            {
                'item': f'Market type is {market_type.upper()}',
                'category': 'Market',
                'critical': True,
                'checked': False
            },
            {
                'item': f'Chart timeframe is {self.timeframe_display.get(timeframe, timeframe)}',
                'category': 'Chart',
                'critical': True,
                'checked': False
            },
            {
                'item': f'Chart type is {self.chart_type_display.get(chart_type, chart_type)}',
                'category': 'Chart',
                'critical': True,
                'checked': False
            },
            {
                'item': f'Expiration time is {self.timeframe_display.get(expiration, expiration)}',
                'category': 'Trade',
                'critical': True,
                'checked': False
            },
            {
                'item': 'New candle has just formed',
                'category': 'Timing',
                'critical': True,
                'checked': False
            },
            {
                'item': 'Technical indicators match signal conditions',
                'category': 'Validation',
                'critical': True,
                'checked': False
            },
            {
                'item': 'Trade amount follows risk management',
                'category': 'Risk',
                'critical': True,
                'checked': False
            }
        ]
    
    def _generate_expected_conditions(self, signal: Dict, timeframe: str) -> Dict:
        """Generate expected technical conditions to verify on chart"""
        tech = signal.get('technical_analysis', {})
        
        conditions = {
            'timeframe': timeframe,
            'description': 'Verify these conditions on your Pocket Option chart',
            'indicators': []
        }
        
        # RSI conditions
        if 'rsi_7' in tech:
            if tech['rsi_7'] < 30:
                conditions['indicators'].append(f"RSI(7) should be below 30 (currently: {tech['rsi_7']:.1f})")
            elif tech['rsi_7'] > 70:
                conditions['indicators'].append(f"RSI(7) should be above 70 (currently: {tech['rsi_7']:.1f})")
        
        if 'rsi_14' in tech:
            if tech['rsi_14'] < 30:
                conditions['indicators'].append(f"RSI(14) should be below 30 (currently: {tech['rsi_14']:.1f})")
            elif tech['rsi_14'] > 70:
                conditions['indicators'].append(f"RSI(14) should be above 70 (currently: {tech['rsi_14']:.1f})")
        
        # Bollinger Bands
        if 'bb_position' in tech:
            if tech['bb_position'] < 0.2:
                conditions['indicators'].append(f"Price at lower Bollinger Band (position: {tech['bb_position']:.1%})")
            elif tech['bb_position'] > 0.8:
                conditions['indicators'].append(f"Price at upper Bollinger Band (position: {tech['bb_position']:.1%})")
        
        # Stochastic
        if 'stochastic_k' in tech:
            if tech['stochastic_k'] < 20:
                conditions['indicators'].append(f"Stochastic in oversold zone (K: {tech['stochastic_k']:.1f})")
            elif tech['stochastic_k'] > 80:
                conditions['indicators'].append(f"Stochastic in overbought zone (K: {tech['stochastic_k']:.1f})")
        
        # MACD
        if 'macd_histogram' in tech:
            if tech['macd_histogram'] > 0:
                conditions['indicators'].append(f"MACD histogram positive (bullish momentum)")
            else:
                conditions['indicators'].append(f"MACD histogram negative (bearish momentum)")
        
        # ADX
        if 'adx' in tech:
            if tech['adx'] > 25:
                conditions['indicators'].append(f"ADX shows strong trend (ADX: {tech['adx']:.1f})")
        
        # Volume
        if 'volume_spike' in tech and tech['volume_spike']:
            conditions['indicators'].append("Volume spike present (high momentum)")
        
        return conditions
    
    def _generate_warnings(self, seconds_to_candle: float, signal: Dict) -> List[str]:
        """Generate important warnings for the trader"""
        warnings = []
        
        # Timing warnings
        if seconds_to_candle > 120:
            warnings.append("⚠️ Signal generated far from next candle - market conditions may change")
        
        if seconds_to_candle < 3:
            warnings.append("⚠️ Very tight timing - ensure you're ready to execute immediately")
        
        # Confidence warnings
        confidence = signal.get('confidence', 0)
        if confidence < 85:
            warnings.append(f"⚠️ Confidence below 85% ({confidence:.1f}%) - consider waiting for stronger signal")
        
        # Market warnings
        tech = signal.get('technical_analysis', {})
        if not tech.get('volume_spike') and 'volume_spike' in tech:
            warnings.append("⚠️ No volume spike detected - momentum may be weak")
        
        # Strategy warnings
        if signal.get('version') != 'V2_Enhanced':
            warnings.append("ℹ️ This signal is from original strategy - enhanced version provides higher accuracy")
        
        return warnings
    
    def _get_fallback_guide(self, signal: Dict, symbol: str, timeframe: str, expiration: str) -> Dict:
        """Fallback guide in case of errors"""
        return {
            'error': 'Could not generate complete setup guide',
            'basic_settings': {
                'asset': symbol,
                'timeframe': timeframe,
                'expiration': expiration,
                'direction': signal.get('direction', 'UNKNOWN')
            },
            'recommendation': 'Manually verify all settings match signal generation conditions'
        }


# Global instance
signal_setup_validator = SignalSetupValidator()
