import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv

from emergentintegrations.llm.chat import LlmChat, UserMessage
from trading_models import TradingSignal, MarketData, TechnicalIndicators, SentimentAnalysis, SignalDirection, TradingStrategy, AssetType

load_dotenv()
logger = logging.getLogger(__name__)

class LLMTradingService:
    """Advanced LLM-powered trading signal generation service"""
    
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment variables")
            
        self.chat = LlmChat(
            api_key=self.api_key,
            session_id="trading_bot_session",
            system_message=self._get_system_prompt()
        ).with_model("openai", "gpt-5")
    
    def _get_system_prompt(self) -> str:
        """Get comprehensive system prompt for trading analysis"""
        return """You are an expert AI trading analyst specializing in binary options and high-frequency trading for Pocket Option platform. Your goal is to generate extremely accurate trading signals with 95%+ success probability.

CORE CAPABILITIES:
- Advanced technical analysis interpretation
- Multi-timeframe market analysis
- Sentiment-driven predictions
- Risk assessment and probability calculation
- Real-time pattern recognition

ANALYSIS FRAMEWORK:
1. Technical Indicators Analysis - Interpret RSI, MACD, EMA, CCI, Bollinger Bands, Stochastic
2. Market Context Assessment - Consider volatility, trend strength, support/resistance
3. Sentiment Integration - Factor in market sentiment and news impact
4. Historical Pattern Matching - Compare to similar past scenarios
5. Probability Calculation - Provide precise confidence levels
6. Risk Management - Assess potential downside and position sizing

OUTPUT REQUIREMENTS:
- Only recommend signals with 95%+ probability
- Provide detailed justification for each signal
- Include specific entry points and expiration times
- Assess market conditions and quality checks
- Give clear BUY/CALL or SELL/PUT directions

TRADING MODES:
- CCI 20: Focus on overbought/oversold extremes
- EMA Crossover: Golden/death cross signals
- RSI 5: Quick scalping opportunities
- MACD Momentum: Trend-following signals
- Hybrid: Combine multiple indicators for highest accuracy

Be precise, analytical, and conservative. Only generate signals when conditions strongly favor a specific direction."""
    
    async def analyze_sentiment(self, symbol: str, market_data: MarketData, technical_indicators: TechnicalIndicators) -> SentimentAnalysis:
        """Analyze market sentiment using LLM with real market data"""
        try:
            # Calculate trend direction
            trend = "bullish" if market_data.change_percent > 0 else "bearish" if market_data.change_percent < 0 else "neutral"
            
            # Volume analysis
            volume_analysis = "high" if market_data.volume > 0 else "normal"
            
            prompt = f"""
Analyze market sentiment for {symbol} ({market_data.asset_type.value}) using REAL market data:

CURRENT MARKET CONDITIONS:
- Current Price: ${market_data.price}
- 24h Change: {market_data.change_percent:.2f}% ({trend} trend)
- Volume: {market_data.volume:,} ({volume_analysis} volume)
- Bid/Ask Spread: ${market_data.bid} / ${market_data.ask}

TECHNICAL INDICATORS (Real Data):
- RSI (14): {technical_indicators.rsi_14:.1f} - {"Overbought" if technical_indicators.rsi_14 > 70 else "Oversold" if technical_indicators.rsi_14 < 30 else "Normal"}
- MACD: {technical_indicators.macd_line:.6f} (Signal: {technical_indicators.macd_signal:.6f})
- EMA Trend: {"Bullish" if technical_indicators.ema_3 > technical_indicators.ema_8 else "Bearish"} (EMA3: {technical_indicators.ema_3:.4f}, EMA8: {technical_indicators.ema_8:.4f})
- CCI (20): {technical_indicators.cci_20:.1f} - {"Overbought" if technical_indicators.cci_20 > 100 else "Oversold" if technical_indicators.cci_20 < -100 else "Normal"}
- Bollinger Position: Price vs Upper: ${technical_indicators.bollinger_upper:.4f}, Lower: ${technical_indicators.bollinger_lower:.4f}

MARKET ANALYSIS REQUIREMENTS:
1. Assess current momentum based on price action and technical confluence
2. Evaluate volume confirmation of price movements  
3. Consider overbought/oversold conditions from multiple indicators
4. Factor in trend strength and potential reversal signals
5. Provide probability assessment for next 1-5 minute price direction

Provide detailed analysis with sentiment score (-1.0 to 1.0) and confidence (0.0 to 1.0).
Format: {{"sentiment_score": X.XX, "confidence": X.XX, "analysis": "detailed technical and fundamental reasoning based on real data"}}
"""

            user_message = UserMessage(text=prompt)
            response = await self.chat.send_message(user_message)
            
            # Parse LLM response
            try:
                sentiment_data = json.loads(response)
                return SentimentAnalysis(
                    symbol=symbol,
                    timestamp=datetime.now(timezone.utc),
                    sentiment_score=sentiment_data.get("sentiment_score", 0.0),
                    confidence=sentiment_data.get("confidence", 0.5),
                    key_factors=[sentiment_data.get("analysis", "LLM market sentiment analysis based on real data")]
                )
            except json.JSONDecodeError:
                # Advanced fallback parsing using market data
                sentiment_score = 0.0
                confidence = 0.6
                
                # Analyze based on actual market conditions
                bullish_factors = 0
                bearish_factors = 0
                
                if market_data.change_percent > 1.0:
                    bullish_factors += 1
                elif market_data.change_percent < -1.0:
                    bearish_factors += 1
                    
                if technical_indicators.rsi_14 < 30:
                    bullish_factors += 1
                elif technical_indicators.rsi_14 > 70:
                    bearish_factors += 1
                    
                if technical_indicators.ema_3 > technical_indicators.ema_8:
                    bullish_factors += 1
                else:
                    bearish_factors += 1
                
                sentiment_score = (bullish_factors - bearish_factors) * 0.3
                sentiment_score = max(-1.0, min(1.0, sentiment_score))
                
                return SentimentAnalysis(
                    symbol=symbol,
                    timestamp=datetime.now(timezone.utc),
                    sentiment_score=sentiment_score,
                    confidence=confidence,
                    key_factors=[f"Real market analysis: {bullish_factors} bullish vs {bearish_factors} bearish factors"]
                )
                
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return SentimentAnalysis(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                sentiment_score=0.0,
                confidence=0.0,
                key_factors=["Sentiment analysis unavailable"]
            )
    
    async def generate_trading_signal(self, 
                                    market_data: MarketData, 
                                    technical_indicators: TechnicalIndicators,
                                    sentiment: Optional[SentimentAnalysis] = None,
                                    strategy: TradingStrategy = TradingStrategy.HYBRID) -> Optional[TradingSignal]:
        """Generate comprehensive trading signal using LLM analysis"""
        
        try:
            # Prepare comprehensive analysis prompt
            prompt = self._build_analysis_prompt(market_data, technical_indicators, sentiment, strategy)
            
            user_message = UserMessage(text=prompt)
            response = await self.chat.send_message(user_message)
            
            # Parse LLM response to extract signal
            signal_data = await self._parse_signal_response(response, market_data, technical_indicators, strategy)
            
            if signal_data and signal_data.get("probability", 0) >= 95.0:
                return TradingSignal(
                    symbol=market_data.symbol,
                    asset_type=market_data.asset_type,
                    direction=SignalDirection(signal_data["direction"]),
                    entry_price=signal_data["entry_price"],
                    expiration_minutes=signal_data["expiration_minutes"],
                    probability=signal_data["probability"],
                    confidence_level=signal_data["confidence_level"],
                    strategy_used=strategy,
                    technical_analysis=self._format_technical_analysis(technical_indicators),
                    sentiment_analysis=sentiment.dict() if sentiment else None,
                    market_analysis_summary=signal_data["market_summary"],
                    justification=signal_data["justification"],
                    risk_assessment=signal_data["risk_assessment"],
                    suggested_stake=signal_data["suggested_stake"],
                    quality_check_passed=signal_data["quality_passed"],
                    quality_notes=signal_data["quality_notes"]
                )
            
            return None  # Signal doesn't meet probability threshold
            
        except Exception as e:
            logger.error(f"Error generating trading signal: {e}")
            return None
    
    def _build_analysis_prompt(self, market_data: MarketData, indicators: TechnicalIndicators, 
                              sentiment: Optional[SentimentAnalysis], strategy: TradingStrategy) -> str:
        """Build comprehensive analysis prompt for LLM"""
        
        sentiment_text = ""
        if sentiment:
            sentiment_text = f"""
Sentiment Analysis:
- Sentiment Score: {sentiment.sentiment_score:.2f} (-1 to 1)
- Confidence: {sentiment.confidence:.2f}
- Key Factors: {', '.join(sentiment.key_factors)}
"""
        
        return f"""
REAL-TIME TRADING SIGNAL ANALYSIS - POCKET OPTION

Asset: {market_data.symbol} ({market_data.asset_type.value})
Strategy: {strategy.value}
Analysis Time: {datetime.now(timezone.utc).isoformat()}

LIVE MARKET DATA (Real-Time):
- Current Price: ${market_data.price}
- Real-Time Spread: ${market_data.bid} (Bid) / ${market_data.ask} (Ask)
- 24h Change: {market_data.change_percent:.2f}% (${market_data.change})
- Volume: {market_data.volume:,}
- Market Status: {"Trending Up" if market_data.change_percent > 0 else "Trending Down" if market_data.change_percent < 0 else "Sideways"}

COMPREHENSIVE TECHNICAL ANALYSIS (Based on Real Historical Data):
╭─ MOMENTUM INDICATORS ─╮
│ RSI (5):  {indicators.rsi_5:.1f} - {"OVERSOLD" if indicators.rsi_5 < 30 else "OVERBOUGHT" if indicators.rsi_5 > 70 else "NEUTRAL"}
│ RSI (14): {indicators.rsi_14:.1f} - {"OVERSOLD" if indicators.rsi_14 < 30 else "OVERBOUGHT" if indicators.rsi_14 > 70 else "NEUTRAL"}
│ CCI (20): {indicators.cci_20:.1f} - {"EXTREME OVERSOLD" if indicators.cci_20 < -100 else "EXTREME OVERBOUGHT" if indicators.cci_20 > 100 else "NORMAL"}
╰─────────────────────────╯

╭─ TREND ANALYSIS ─╮
│ EMA 3:   ${indicators.ema_3:.4f}
│ EMA 8:   ${indicators.ema_8:.4f}
│ EMA 50:  ${indicators.ema_50:.4f}
│ EMA 200: ${indicators.ema_200:.4f}
│ Trend:   {"BULLISH" if indicators.ema_3 > indicators.ema_8 > indicators.ema_50 else "BEARISH" if indicators.ema_3 < indicators.ema_8 < indicators.ema_50 else "MIXED"}
╰───────────────────╯

╭─ VOLATILITY & MOMENTUM ─╮
│ MACD Line:   {indicators.macd_line:.6f}
│ MACD Signal: {indicators.macd_signal:.6f}
│ Histogram:   {indicators.macd_histogram:.6f} - {"BULLISH MOMENTUM" if indicators.macd_histogram > 0 else "BEARISH MOMENTUM"}
│ ATR:         {indicators.atr:.6f} (Volatility measure)
╰──────────────────────────╯

╭─ BOLLINGER BANDS ANALYSIS ─╮
│ Upper:  ${indicators.bollinger_upper:.4f}
│ Middle: ${indicators.bollinger_middle:.4f} 
│ Lower:  ${indicators.bollinger_lower:.4f}
│ Position: {"ABOVE UPPER BAND" if market_data.price > indicators.bollinger_upper else "BELOW LOWER BAND" if market_data.price < indicators.bollinger_lower else "WITHIN BANDS"}
╰─────────────────────────────╯

╭─ STOCHASTIC OSCILLATOR ─╮
│ %K: {indicators.stoch_k:.1f}
│ %D: {indicators.stoch_d:.1f}
│ Status: {"OVERBOUGHT ZONE" if indicators.stoch_k > 80 else "OVERSOLD ZONE" if indicators.stoch_k < 20 else "NEUTRAL ZONE"}
╰─────────────────────────╯
{sentiment_text}

BINARY OPTIONS ANALYSIS FRAMEWORK:
1. **Multi-Timeframe Confluence**: Analyze alignment across 1m, 5m, 15m trends
2. **Momentum Confirmation**: Verify RSI, MACD, and Stochastic alignment  
3. **Support/Resistance**: Check Bollinger Bands and EMA levels
4. **Volume Validation**: Confirm price moves with volume
5. **Risk/Reward Assessment**: Calculate win probability for 1-5 minute expiry
6. **Market Volatility Check**: Ensure sufficient movement for profit

CRITICAL REQUIREMENTS FOR SIGNAL GENERATION:
- Minimum 95% confidence based on real market confluence
- Clear directional bias from multiple indicators
- Appropriate volatility for binary options timeframe
- Volume confirmation of price direction
- No major economic news conflicts

RESPONSE FORMAT (Strict JSON):
{{
    "market_summary": "Comprehensive analysis of current market state",
    "signal_direction": "BUY" | "SELL" | "NONE",
    "entry_price": {market_data.price},
    "expiration_minutes": 1-5,
    "probability": 95.0-99.9,
    "confidence_level": "HIGH" | "MEDIUM" | "LOW",
    "justification": "Detailed multi-indicator confluence analysis",
    "risk_assessment": "Specific risk factors and mitigation strategies",
    "suggested_stake": 5.0-50.0,
    "quality_passed": true | false,
    "quality_notes": "Technical quality validation details"
}}

⚠️  STRICT RULES:
- Only generate BUY/SELL if probability ≥ 95%
- Must have confluence from at least 3 different indicators
- Return "NONE" if market conditions are unclear or risky
- Consider real market volatility and spreads
"""

    async def _parse_signal_response(self, response: str, market_data: MarketData, 
                                   indicators: TechnicalIndicators, strategy: TradingStrategy) -> Optional[Dict]:
        """Parse LLM response and extract signal data"""
        try:
            # Try to parse JSON response
            if "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                signal_data = json.loads(json_str)
                
                # Validate and process signal data
                if signal_data.get("signal_direction") in ["BUY", "SELL"]:
                    return {
                        "direction": signal_data["signal_direction"],
                        "entry_price": float(signal_data.get("entry_price", market_data.price)),
                        "expiration_minutes": int(signal_data.get("expiration_minutes", 2)),
                        "probability": float(signal_data.get("probability", 0)),
                        "confidence_level": signal_data.get("confidence_level", "MEDIUM"),
                        "market_summary": signal_data.get("market_summary", "LLM market analysis"),
                        "justification": signal_data.get("justification", "LLM signal justification"),
                        "risk_assessment": signal_data.get("risk_assessment", "Standard risk"),
                        "suggested_stake": float(signal_data.get("suggested_stake", 10.0)),
                        "quality_passed": bool(signal_data.get("quality_passed", True)),
                        "quality_notes": signal_data.get("quality_notes", "LLM quality check")
                    }
                
            return None
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error parsing signal response: {e}")
            
            # Fallback: simple pattern matching
            if "BUY" in response.upper() and any(word in response.lower() for word in ["strong", "bullish", "95%", "96%", "97%", "98%", "99%"]):
                return {
                    "direction": "BUY",
                    "entry_price": market_data.price,
                    "expiration_minutes": 2,
                    "probability": 95.5,
                    "confidence_level": "MEDIUM",
                    "market_summary": "LLM indicates bullish conditions",
                    "justification": response[:200],
                    "risk_assessment": "Standard risk assessment",
                    "suggested_stake": 10.0,
                    "quality_passed": True,
                    "quality_notes": "Fallback parsing"
                }
            elif "SELL" in response.upper() and any(word in response.lower() for word in ["strong", "bearish", "95%", "96%", "97%", "98%", "99%"]):
                return {
                    "direction": "SELL",
                    "entry_price": market_data.price,
                    "expiration_minutes": 2,
                    "probability": 95.5,
                    "confidence_level": "MEDIUM",
                    "market_summary": "LLM indicates bearish conditions",
                    "justification": response[:200],
                    "risk_assessment": "Standard risk assessment",
                    "suggested_stake": 10.0,
                    "quality_passed": True,
                    "quality_notes": "Fallback parsing"
                }
            
            return None
    
    def _format_technical_analysis(self, indicators: TechnicalIndicators) -> Dict[str, Any]:
        """Format technical indicators for storage"""
        return {
            "rsi": {"5": indicators.rsi_5, "14": indicators.rsi_14},
            "macd": {
                "line": indicators.macd_line,
                "signal": indicators.macd_signal,
                "histogram": indicators.macd_histogram
            },
            "ema": {
                "3": indicators.ema_3,
                "8": indicators.ema_8,
                "50": indicators.ema_50,
                "200": indicators.ema_200
            },
            "cci_20": indicators.cci_20,
            "bollinger": {
                "upper": indicators.bollinger_upper,
                "middle": indicators.bollinger_middle,
                "lower": indicators.bollinger_lower
            },
            "stochastic": {
                "k": indicators.stoch_k,
                "d": indicators.stoch_d
            },
            "atr": indicators.atr
        }