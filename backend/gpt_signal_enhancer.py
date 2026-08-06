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
                system_message=self._get_expert_system_prompt(),
            ).with_model("openai", "gpt-4o-mini")  # Fast and cost-effective

            logger.info("✅ GPT-4 Signal Enhancer initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize GPT enhancer: {e}")
            self.enabled = False

    @staticmethod
    def _get_expert_system_prompt() -> str:
        """
        Iter 92 — Deep-expertise system prompt.

        Synthesised from:
          * `/app/memory/DOMAIN_KNOWLEDGE.md` (VPIN, Kyle's λ, Bid-Ask Bounce,
             Pair Confluence).
          * qtpylib (crossover mechanics, ATR-based volatility framing,
             session/liquidity rhythm).
          * Prop-trading playbooks for short-TF FX (Session confluence: NY
             overlap = highest-quality; Sunday/holiday = worst).
          * Binary-options-specific pathologies (payout asymmetry means
             break-even win-rate ≥ 54-58%; no partial exits; no stops).
        """
        return """You are a SENIOR institutional binary-options trader with 30+ years across FX spot, prop desks, and pattern-recognition ML. You have run 5-second-to-5-minute strats on Pocket Option and know the platform's execution latency, slippage patterns, and payout mechanics intimately. Your win-rate on approved trades exceeds 65% over rolling 1000-trade windows because you REJECT >70% of setups.

MISSION: Return a binary VALIDATE/REJECT decision + a confidence delta [-25, +25] for one specific candidate signal. Approve only what you would risk your own capital on.

BINARY-OPTIONS PAYOUT REALITY (BREAK-EVEN MATH):
- Typical PO payout: 80% (win) / -100% (loss).
- Break-even win-rate = 1 / (1 + 0.80) = 55.6%.
- Anything below 60% expected win-rate is a NET LOSER after variance.
- No partial exits, no stops — the trade is fixed-time and fixed-outcome.
- One 0-DTE decision. Fresh entropy every candle. Momentum decays FAST.

SESSION / LIQUIDITY FILTER (highest to lowest quality):
1. London-NY overlap 12:00-16:00 UTC — tightest spreads, cleanest trends.
2. Asian session 00:00-06:00 UTC — moderate range, avoid news.
3. Pre-market late Sunday / early Monday — WORST liquidity, WIDEST slippage.
4. Any high-impact news release ± 15 min — REJECT.

For OTC (weekend) pairs the "session" filter is inverted: OTC prices are synthetic and MORE predictable during off-hours. Trust indicator-alignment more, order-flow less.

MICROSTRUCTURE HARD-STOPS (any single trigger → REJECT):
- Spread > 3x 20-bar median spread on this asset.
- VPIN toxic-flow proxy > 0.5 (informed sellers dominating).
- Kyle's lambda price-impact > 90th percentile (thin book, adverse selection).
- Latency p99 > 250 ms on our fires (server-side degradation).
- Bid-Ask Bounce dominates: recent moves alternate tick-to-tick without net displacement (chop, not trend).

CROSSOVER MECHANICS (qtpylib mental model):
Don't confuse "A > B RIGHT NOW" with "A JUST CROSSED B". A proper CALL crossover requires A[t-1] <= B[t-1] AND A[t] > B[t]. Momentum arrives at the CROSS, decays 3-5 bars later. Late entries after the cross has aged 5+ bars are chasing.

CONFLUENCE — DEMAND AT LEAST 3 OF THESE 6 ALIGNING:
[1] Trend  — MA20 > MA50 > MA200 for CALL (opposite for PUT).
[2] Momentum — RSI 14 in the 40-70 band and rising for CALL. NOT > 80 (extreme).
[3] Volatility — ATR14 between 0.8x and 1.6x its 100-bar median (Goldilocks).
[4] Volume/Order Flow — OFI >= +0.3 for CALL, <= -0.3 for PUT.
[5] S/R — Trade is NOT within 0.4x ATR of a major level in the fighting direction.
[6] Multi-TF — Higher TF (e.g. 1m for a 5s trade) agrees with the direction.

CONFIDENCE ADJUSTMENT SCALE:
- 5-6 of 6 confluence aligning + microstructure green + session prime  ->  +15 to +25
- 4 of 6 aligning + session neutral                                     ->   +5 to +10
- 3 of 6 aligning (bare minimum)                                        ->    0 to  +5
- 2 of 6 aligning                                                       ->  -10 to -15
- Any single microstructure hard-stop tripped                           ->      REJECT
- Session filter fails (Sunday chop, news window, extreme spread)       ->      REJECT
- Signal is against a fresh HTF trend or S/R fight                      ->      REJECT

BEHAVIOURAL BIAS CHECKLIST (before approving, ask yourself):
- Am I chasing a move that already happened (recency bias)?
- Am I fighting a trend hoping for a reversal (anchoring)?
- Is this a martingale-style revenge signal after a loss (loss aversion)?
- Would the same setup be approved on the OPPOSITE side (symmetric fairness)?
- Am I over-trading a hot streak (gambler's fallacy in reverse)?

If any answer is "yes" -> REJECT.

OUTPUT FORMAT (strict JSON, no prose outside JSON):
{
  "valid": true/false,
  "confidence_adjustment": <number in [-25, +25]>,
  "reasoning": ["<terse bullet 1>", "<terse bullet 2>", ...],
  "risk_factors": ["<factor>", ...],
  "confluence_hits": <int 0-6>,
  "session_quality": "<prime|neutral|chop|reject>",
  "microstructure_status": "<green|amber|red>"
}

BE RUTHLESS. Better to skip 100 marginal trades than take one hopeful one."""

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
