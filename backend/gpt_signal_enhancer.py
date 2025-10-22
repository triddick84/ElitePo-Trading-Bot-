"""
GPT-4 Powered Signal Enhancement Module
Uses OpenAI GPT-4 for advanced feature analysis and signal validation

Capabilities:
- Real-time market condition analysis
- Feature importance ranking
- Pattern recognition enhancement
- Signal confidence validation
- Multi-timeframe context analysis
- Sentiment-aware adjustments
"""

import os
import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    GPT_AVAILABLE = True
except ImportError:
    logger.warning("emergentintegrations not available. GPT enhancement disabled.")
    GPT_AVAILABLE = False

class GPTSignalEnhancer:
    """
    GPT-4 powered signal enhancement for ultra-short timeframe trading
    
    Uses GPT-4's reasoning capabilities to:
    - Analyze market microstructure
    - Validate signal logic
    - Enhance confidence scores
    - Provide reasoning improvements
    """
    
    def __init__(self):
        self.api_key = os.getenv('EMERGENT_LLM_KEY')
        self.enabled = GPT_AVAILABLE and self.api_key is not None
        
        if not self.enabled:
            logger.warning("GPT Signal Enhancer disabled - missing API key or library")
            return
        
        # Initialize GPT-4 chat
        try:
            self.chat = LlmChat(
                api_key=self.api_key,
                session_id=f"trading_signal_enhancer_{datetime.now().strftime('%Y%m%d')}",
                system_message="""You are an expert quantitative trading analyst specializing in ultra-short timeframe binary options trading (5-second to 1-minute).

Your role is to analyze market conditions and technical indicators to provide:
1. Signal validation (confirm or reject proposed signals)
2. Confidence score adjustments (-20 to +20 points)
3. Enhanced reasoning (2-3 key points)
4. Risk warnings if conditions are unfavorable

Focus on:
- Market microstructure (order flow, liquidity, volatility)
- Technical indicator alignment
- Support/Resistance context
- Risk factors (wide spreads, low volume, high volatility)

Respond in JSON format with: {"valid": true/false, "confidence_adjustment": number, "reasoning": [string], "risk_factors": [string]}"""
            ).with_model("openai", "gpt-4o-mini")  # Fast and cost-effective
            
            logger.info("✅ GPT-4 Signal Enhancer initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize GPT enhancer: {e}")
            self.enabled = False
    
    async def enhance_signal(
        self,
        signal: str,
        confidence: float,
        features: Dict,
        technical_analysis: Dict,
        timeframe: str
    ) -> Dict:
        """
        Enhance signal using GPT-4 analysis
        
        Args:
            signal: Proposed signal direction (CALL/PUT)
            confidence: Current confidence score
            features: Engineered features (OFI, VWAP, etc.)
            technical_analysis: Technical indicators (RSI, EMA, etc.)
            timeframe: Trading timeframe (5s, 15s, 1m)
        
        Returns:
            Dictionary with validation result and enhancements
        """
        if not self.enabled:
            return {
                'enhanced': False,
                'valid': True,
                'confidence_adjustment': 0,
                'reasoning': [],
                'risk_factors': []
            }
        
        try:
            # Construct analysis prompt
            prompt = self._build_analysis_prompt(
                signal, confidence, features, technical_analysis, timeframe
            )
            
            # Get GPT-4 analysis
            user_message = UserMessage(text=prompt)
            response = await self.chat.send_message(user_message)
            
            # Parse response
            result = self._parse_gpt_response(response)
            result['enhanced'] = True
            
            logger.info(f"🤖 GPT-4 Enhanced: {signal} - Adjustment: {result.get('confidence_adjustment', 0):+.1f}%")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in GPT enhancement: {e}")
            return {
                'enhanced': False,
                'valid': True,
                'confidence_adjustment': 0,
                'reasoning': [],
                'risk_factors': []
            }
    
    def _build_analysis_prompt(
        self,
        signal: str,
        confidence: float,
        features: Dict,
        technical_analysis: Dict,
        timeframe: str
    ) -> str:
        """Build comprehensive analysis prompt for GPT-4"""
        
        # Extract key features
        ofi = features.get('ofi', 0)
        spread = features.get('spread', 0)
        vwap_distance = features.get('vwap_distance', 0)
        volume_profile = features.get('volume_profile', 0)
        
        # Extract technical indicators
        rsi = technical_analysis.get('rsi_2', technical_analysis.get('rsi_14', 50))
        ema_distance = technical_analysis.get('ema_distance', 0)
        stoch = technical_analysis.get('stoch_k', 50)
        bb_position = technical_analysis.get('bb_position', 0.5)
        
        # Support/Resistance
        sr_info = ""
        if 'nearest_support' in technical_analysis and technical_analysis['nearest_support']:
            sr_info += f"Near Support: {technical_analysis['nearest_support'].get('price', 'N/A')}\n"
        if 'nearest_resistance' in technical_analysis and technical_analysis['nearest_resistance']:
            sr_info += f"Near Resistance: {technical_analysis['nearest_resistance'].get('price', 'N/A')}\n"
        
        # Reversal detection
        reversal_info = ""
        if technical_analysis.get('reversal_detected'):
            reversal_info = f"Reversal Detected: {technical_analysis.get('reversal_type', 'Unknown')}"
        
        prompt = f"""Analyze this {timeframe} trading signal for validation:

**Proposed Signal:** {signal}
**Current Confidence:** {confidence:.1f}%
**Timeframe:** {timeframe}

**Market Microstructure:**
- Order Flow Imbalance (OFI): {ofi:.3f} (positive=buying pressure, negative=selling)
- Bid-Ask Spread: {spread:.4f} (wider=less liquid)
- VWAP Distance: {vwap_distance:.3%} (negative=below VWAP, positive=above)
- Volume Profile Signal: {volume_profile:.3f}

**Technical Indicators:**
- RSI: {rsi:.1f} (< 30 oversold, > 70 overbought)
- EMA Distance: {ema_distance:.3%} (negative=below EMA, positive=above)
- Stochastic: {stoch:.1f} (< 20 oversold, > 80 overbought)
- Bollinger Band Position: {bb_position:.2%} (0%=lower band, 100%=upper band)

**Support/Resistance:**
{sr_info if sr_info else "No S/R data available"}

**Reversal Analysis:**
{reversal_info if reversal_info else "No reversal detected"}

**Task:**
1. Validate if this {signal} signal makes sense given the data
2. Suggest confidence adjustment (-20 to +20 points)
3. Provide 2-3 key reasoning points
4. Identify any risk factors

Respond in JSON format only:
{{"valid": true/false, "confidence_adjustment": number, "reasoning": ["point1", "point2"], "risk_factors": ["risk1", "risk2"]}}"""
        
        return prompt
    
    def _parse_gpt_response(self, response: str) -> Dict:
        """Parse GPT-4 JSON response"""
        try:
            import json
            import re
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate and sanitize
                return {
                    'valid': bool(result.get('valid', True)),
                    'confidence_adjustment': max(-20, min(20, float(result.get('confidence_adjustment', 0)))),
                    'reasoning': result.get('reasoning', [])[:3],  # Max 3 points
                    'risk_factors': result.get('risk_factors', [])[:3]
                }
            else:
                logger.warning("Could not extract JSON from GPT response")
                return self._default_response()
                
        except Exception as e:
            logger.error(f"Error parsing GPT response: {e}")
            return self._default_response()
    
    def _default_response(self) -> Dict:
        """Default response if parsing fails"""
        return {
            'valid': True,
            'confidence_adjustment': 0,
            'reasoning': [],
            'risk_factors': []
        }
    
    async def analyze_market_regime(self, df, timeframe: str) -> Dict:
        """
        Analyze overall market regime for context
        
        Returns:
            Dictionary with market regime analysis
        """
        if not self.enabled:
            return {'regime': 'unknown', 'analysis': []}
        
        try:
            # Calculate market characteristics
            recent_volatility = df['close'].pct_change().std() * 100
            trend_strength = abs(df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20]
            volume_trend = df['volume'].iloc[-5:].mean() / df['volume'].iloc[-20:-5].mean() if 'volume' in df else 1.0
            
            prompt = f"""Analyze the current market regime for {timeframe} trading:

**Market Statistics:**
- Recent Volatility: {recent_volatility:.2f}%
- Trend Strength: {trend_strength:.2%}
- Volume Trend: {volume_trend:.2f}x (> 1 = increasing volume)

Classify the market as: TRENDING, RANGING, VOLATILE, or QUIET
Provide 2-3 actionable insights for this regime.

Respond in JSON: {{"regime": "type", "insights": ["insight1", "insight2"], "trade_suitability": "high/medium/low"}}"""
            
            user_message = UserMessage(text=prompt)
            response = await self.chat.send_message(user_message)
            
            # Parse response
            import json
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            
            return {'regime': 'unknown', 'insights': [], 'trade_suitability': 'medium'}
            
        except Exception as e:
            logger.error(f"Error analyzing market regime: {e}")
            return {'regime': 'unknown', 'insights': [], 'trade_suitability': 'medium'}

# Create singleton instance
gpt_signal_enhancer = GPTSignalEnhancer()
