"""
Premium Signal Generator with Time & Session Filters
High-accuracy signal generation with session-based filtering and win rate tracking
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'gpt_signal_bot')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Collections for tracking
signal_performance = db['signal_performance']
hourly_stats = db['hourly_stats']


class TradingSession(Enum):
    """Major trading sessions"""
    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP_LONDON_NY = "london_ny_overlap"
    OVERLAP_TOKYO_LONDON = "tokyo_london_overlap"
    OFF_HOURS = "off_hours"


class MarketCondition(Enum):
    """Market conditions"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"
    UNCERTAIN = "uncertain"


@dataclass
class SessionInfo:
    """Trading session information"""
    session: TradingSession
    is_active: bool
    quality_score: float  # 0-100, higher = better for trading
    recommended_pairs: List[str]
    avoid_pairs: List[str]
    notes: str


@dataclass
class TimeFilter:
    """Time-based filtering results"""
    current_hour_utc: int
    current_session: TradingSession
    session_quality: float
    is_good_time: bool
    historical_win_rate: float
    recommendation: str


class SessionAnalyzer:
    """
    Analyzes current trading session and provides time-based filters
    """
    
    # Session hours in UTC
    SESSIONS = {
        TradingSession.SYDNEY: (21, 6),      # 21:00 - 06:00 UTC
        TradingSession.TOKYO: (0, 9),         # 00:00 - 09:00 UTC
        TradingSession.LONDON: (7, 16),       # 07:00 - 16:00 UTC
        TradingSession.NEW_YORK: (12, 21),    # 12:00 - 21:00 UTC
    }
    
    # Overlap periods (highest liquidity)
    OVERLAPS = {
        TradingSession.OVERLAP_LONDON_NY: (12, 16),      # 12:00 - 16:00 UTC
        TradingSession.OVERLAP_TOKYO_LONDON: (7, 9),     # 07:00 - 09:00 UTC
    }
    
    # Session quality scores (empirical)
    SESSION_QUALITY = {
        TradingSession.OVERLAP_LONDON_NY: 95,      # Best time to trade
        TradingSession.OVERLAP_TOKYO_LONDON: 85,
        TradingSession.LONDON: 80,
        TradingSession.NEW_YORK: 75,
        TradingSession.TOKYO: 65,
        TradingSession.SYDNEY: 50,
        TradingSession.OFF_HOURS: 30,
    }
    
    # Pairs best suited for each session
    SESSION_PAIRS = {
        TradingSession.SYDNEY: ["AUD_USD", "NZD_USD", "AUD_JPY", "AUD_NZD"],
        TradingSession.TOKYO: ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"],
        TradingSession.LONDON: ["EUR_USD", "GBP_USD", "EUR_GBP", "USD_CHF"],
        TradingSession.NEW_YORK: ["EUR_USD", "USD_CAD", "GBP_USD", "USD_MXN"],
        TradingSession.OVERLAP_LONDON_NY: ["EUR_USD", "GBP_USD", "USD_CHF", "EUR_GBP"],
        TradingSession.OVERLAP_TOKYO_LONDON: ["EUR_JPY", "GBP_JPY", "EUR_USD"],
    }
    
    # Hours to AVOID trading (historically low win rates)
    BAD_HOURS_UTC = [4, 5, 20, 21, 22, 23]  # Late night / early morning
    
    # Best hours for trading (historically high win rates)
    BEST_HOURS_UTC = [8, 9, 13, 14, 15]  # London open, NY open, overlap
    
    def __init__(self):
        self.hourly_performance = {}
        self._load_hourly_stats()
    
    def _load_hourly_stats(self):
        """Load historical hourly performance from database"""
        try:
            stats = list(hourly_stats.find({}, {"_id": 0}))
            for s in stats:
                hour = s.get("hour")
                if hour is not None:
                    self.hourly_performance[hour] = {
                        "total": s.get("total", 0),
                        "wins": s.get("wins", 0),
                        "win_rate": s.get("win_rate", 50.0)
                    }
        except Exception as e:
            logger.error(f"Error loading hourly stats: {e}")
    
    def get_current_session(self, utc_hour: int = None) -> TradingSession:
        """Determine current trading session"""
        if utc_hour is None:
            utc_hour = datetime.now(timezone.utc).hour
        
        # Check overlaps first (highest priority)
        for session, (start, end) in self.OVERLAPS.items():
            if start <= utc_hour < end:
                return session
        
        # Check main sessions
        for session, (start, end) in self.SESSIONS.items():
            if start <= end:
                if start <= utc_hour < end:
                    return session
            else:  # Crosses midnight
                if utc_hour >= start or utc_hour < end:
                    return session
        
        return TradingSession.OFF_HOURS
    
    def get_session_info(self, utc_hour: int = None) -> SessionInfo:
        """Get detailed session information"""
        if utc_hour is None:
            utc_hour = datetime.now(timezone.utc).hour
        
        session = self.get_current_session(utc_hour)
        quality = self.SESSION_QUALITY.get(session, 50)
        
        # Adjust quality based on historical performance
        if utc_hour in self.hourly_performance:
            hist_win_rate = self.hourly_performance[utc_hour].get("win_rate", 50)
            if hist_win_rate > 55:
                quality = min(100, quality + 10)
            elif hist_win_rate < 45:
                quality = max(0, quality - 15)
        
        # Further adjust for known bad hours
        if utc_hour in self.BAD_HOURS_UTC:
            quality = max(0, quality - 20)
        elif utc_hour in self.BEST_HOURS_UTC:
            quality = min(100, quality + 10)
        
        recommended = self.SESSION_PAIRS.get(session, [])
        avoid = []
        
        if session == TradingSession.SYDNEY:
            avoid = ["EUR_GBP", "EUR_CHF"]
        elif session == TradingSession.TOKYO:
            avoid = ["EUR_GBP", "GBP_CHF"]
        elif session == TradingSession.OFF_HOURS:
            avoid = ["All major pairs"]
        
        notes = self._get_session_notes(session, utc_hour)
        
        return SessionInfo(
            session=session,
            is_active=quality >= 50,
            quality_score=quality,
            recommended_pairs=recommended,
            avoid_pairs=avoid,
            notes=notes
        )
    
    def _get_session_notes(self, session: TradingSession, hour: int) -> str:
        """Get notes for current session"""
        if session == TradingSession.OVERLAP_LONDON_NY:
            return "🔥 BEST TIME: London-NY overlap. High liquidity, strong moves."
        elif session == TradingSession.OVERLAP_TOKYO_LONDON:
            return "✅ GOOD: Tokyo-London overlap. Good for EUR/JPY, GBP/JPY."
        elif session == TradingSession.LONDON:
            return "✅ London session active. Good volatility for EUR, GBP pairs."
        elif session == TradingSession.NEW_YORK:
            return "✅ NY session active. Watch USD pairs and news events."
        elif session == TradingSession.TOKYO:
            return "⚠️ Tokyo session. Best for JPY pairs, lower volatility."
        elif session == TradingSession.SYDNEY:
            return "⚠️ Sydney session. Lower liquidity, trade AUD/NZD pairs."
        else:
            return "❌ OFF HOURS: Low liquidity, avoid trading or use extreme caution."
    
    def analyze_time(self, symbol: str = None) -> TimeFilter:
        """Analyze current time for trading suitability"""
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        session = self.get_current_session(hour)
        session_info = self.get_session_info(hour)
        
        # Check historical performance for this hour
        hist_win_rate = 50.0
        if hour in self.hourly_performance:
            hist_win_rate = self.hourly_performance[hour].get("win_rate", 50.0)
        
        # Determine if good time
        is_good = session_info.quality_score >= 60
        
        # Check symbol compatibility
        if symbol:
            symbol_base = symbol.upper().replace("_OTC", "").replace("OTC", "")
            if symbol_base in session_info.avoid_pairs:
                is_good = False
            elif symbol_base in session_info.recommended_pairs:
                is_good = True
        
        # Build recommendation
        if is_good:
            if session_info.quality_score >= 80:
                recommendation = f"🔥 EXCELLENT time to trade. Session: {session.value}"
            else:
                recommendation = f"✅ Good time to trade. Session: {session.value}"
        else:
            if session_info.quality_score < 40:
                recommendation = f"❌ AVOID trading now. Session: {session.value}"
            else:
                recommendation = f"⚠️ Caution advised. Session: {session.value}"
        
        return TimeFilter(
            current_hour_utc=hour,
            current_session=session,
            session_quality=session_info.quality_score,
            is_good_time=is_good,
            historical_win_rate=hist_win_rate,
            recommendation=recommendation
        )
    
    def record_trade_result(self, hour: int, is_win: bool):
        """Record trade result for hourly statistics"""
        try:
            hourly_stats.update_one(
                {"hour": hour},
                {
                    "$inc": {
                        "total": 1,
                        "wins": 1 if is_win else 0
                    }
                },
                upsert=True
            )
            
            # Update local cache
            if hour not in self.hourly_performance:
                self.hourly_performance[hour] = {"total": 0, "wins": 0, "win_rate": 50.0}
            
            self.hourly_performance[hour]["total"] += 1
            if is_win:
                self.hourly_performance[hour]["wins"] += 1
            
            total = self.hourly_performance[hour]["total"]
            wins = self.hourly_performance[hour]["wins"]
            self.hourly_performance[hour]["win_rate"] = (wins / total * 100) if total > 0 else 50.0
            
            # Update database with win rate
            hourly_stats.update_one(
                {"hour": hour},
                {"$set": {"win_rate": self.hourly_performance[hour]["win_rate"]}}
            )
            
        except Exception as e:
            logger.error(f"Error recording trade result: {e}")
    
    def get_best_hours(self, top_n: int = 5) -> List[Dict]:
        """Get the best hours to trade based on historical data"""
        if not self.hourly_performance:
            # Return default best hours
            return [{"hour": h, "win_rate": 55.0, "note": "Default"} for h in self.BEST_HOURS_UTC[:top_n]]
        
        sorted_hours = sorted(
            [(h, d) for h, d in self.hourly_performance.items() if d.get("total", 0) >= 10],
            key=lambda x: x[1].get("win_rate", 0),
            reverse=True
        )
        
        return [
            {
                "hour": h,
                "win_rate": d.get("win_rate", 50),
                "total_trades": d.get("total", 0),
                "wins": d.get("wins", 0)
            }
            for h, d in sorted_hours[:top_n]
        ]
    
    def get_hours_to_avoid(self, threshold: float = 45.0) -> List[int]:
        """Get hours with win rate below threshold"""
        avoid = []
        
        for hour, data in self.hourly_performance.items():
            if data.get("total", 0) >= 10 and data.get("win_rate", 50) < threshold:
                avoid.append(hour)
        
        # Always include known bad hours
        for h in self.BAD_HOURS_UTC:
            if h not in avoid:
                avoid.append(h)
        
        return sorted(avoid)


class MarketConditionAnalyzer:
    """Analyzes market conditions using multiple indicators"""
    
    def __init__(self):
        pass
    
    def analyze(self, candles: List[Dict]) -> MarketCondition:
        """Determine current market condition"""
        if not candles or len(candles) < 20:
            return MarketCondition.UNCERTAIN
        
        closes = np.array([float(c.get('close', c.get('Close', 0))) for c in candles])
        highs = np.array([float(c.get('high', c.get('High', 0))) for c in candles])
        lows = np.array([float(c.get('low', c.get('Low', 0))) for c in candles])
        
        # Calculate ADX for trend strength
        adx = self._calculate_adx(highs, lows, closes, 14)
        
        # Calculate trend direction
        sma20 = np.mean(closes[-20:])
        sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma20
        
        # Calculate volatility
        atr = self._calculate_atr(highs, lows, closes, 14)
        avg_range = np.mean(highs[-20:] - lows[-20:])
        volatility_ratio = atr / avg_range if avg_range > 0 else 1.0
        
        # Determine condition
        if adx > 25:
            # Strong trend
            if closes[-1] > sma20 > sma50:
                return MarketCondition.TRENDING_UP
            elif closes[-1] < sma20 < sma50:
                return MarketCondition.TRENDING_DOWN
        
        if volatility_ratio > 1.5:
            return MarketCondition.VOLATILE
        elif volatility_ratio < 0.5:
            return MarketCondition.QUIET
        
        # Check for ranging
        high_20 = np.max(highs[-20:])
        low_20 = np.min(lows[-20:])
        range_pct = (high_20 - low_20) / low_20 * 100 if low_20 > 0 else 0
        
        if range_pct < 0.5 and adx < 20:
            return MarketCondition.RANGING
        
        return MarketCondition.UNCERTAIN
    
    def _calculate_adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calculate ADX (Average Directional Index)"""
        if len(closes) < period + 1:
            return 20.0  # Default neutral
        
        # Calculate +DM and -DM
        plus_dm = np.zeros(len(highs))
        minus_dm = np.zeros(len(lows))
        tr = np.zeros(len(closes))
        
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            plus_dm[i] = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm[i] = low_diff if low_diff > high_diff and low_diff > 0 else 0
            
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
        
        # Smooth with EMA
        atr = self._ema(tr[1:], period)
        plus_di = 100 * self._ema(plus_dm[1:], period) / atr if atr > 0 else 0
        minus_di = 100 * self._ema(minus_dm[1:], period) / atr if atr > 0 else 0
        
        # Calculate DX and ADX
        di_sum = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0
        
        return dx
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calculate ATR"""
        if len(closes) < period + 1:
            return 0.0
        
        tr = []
        for i in range(1, len(closes)):
            tr.append(max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            ))
        
        return np.mean(tr[-period:])
    
    def _ema(self, data: np.ndarray, period: int) -> float:
        """Calculate EMA"""
        if len(data) < period:
            return np.mean(data) if len(data) > 0 else 0
        
        k = 2 / (period + 1)
        ema = np.mean(data[:period])
        
        for i in range(period, len(data)):
            ema = data[i] * k + ema * (1 - k)
        
        return ema


# Global instances
session_analyzer = SessionAnalyzer()
market_condition_analyzer = MarketConditionAnalyzer()


def get_time_filter(symbol: str = None) -> Dict:
    """Get time filter information for API response"""
    tf = session_analyzer.analyze_time(symbol)
    return {
        "hour_utc": tf.current_hour_utc,
        "session": tf.current_session.value,
        "quality": tf.session_quality,
        "is_good_time": tf.is_good_time,
        "historical_win_rate": round(tf.historical_win_rate, 1),
        "recommendation": tf.recommendation
    }


def should_trade_now(symbol: str = None, min_quality: float = 50.0) -> Tuple[bool, str]:
    """Quick check if we should trade now"""
    tf = session_analyzer.analyze_time(symbol)
    
    if tf.session_quality < min_quality:
        return False, tf.recommendation
    
    if not tf.is_good_time:
        return False, tf.recommendation
    
    return True, tf.recommendation


def get_market_condition(candles: List[Dict]) -> Dict:
    """Get market condition for API response"""
    condition = market_condition_analyzer.analyze(candles)
    
    recommendations = {
        MarketCondition.TRENDING_UP: "Trade with trend (CALL signals preferred)",
        MarketCondition.TRENDING_DOWN: "Trade with trend (PUT signals preferred)",
        MarketCondition.RANGING: "Trade reversals at support/resistance",
        MarketCondition.VOLATILE: "High volatility - reduce position size",
        MarketCondition.QUIET: "Low volatility - wait for breakout",
        MarketCondition.UNCERTAIN: "Mixed signals - proceed with caution",
    }
    
    return {
        "condition": condition.value,
        "recommendation": recommendations.get(condition, ""),
        "tradeable": condition in [
            MarketCondition.TRENDING_UP,
            MarketCondition.TRENDING_DOWN,
            MarketCondition.RANGING
        ]
    }


class AssetPerformanceTracker:
    """Tracks win rates per asset and per hour+asset combination, with direction-aware loss detection"""
    
    def __init__(self):
        self.asset_stats_collection = db['asset_performance']
        self.asset_hourly_collection = db['asset_hourly_performance']
        self.recent_trades_collection = db['recent_asset_trades']
    
    def record_result(self, symbol: str, direction: str, is_win: bool, hour_utc: int, session: str):
        """Record a trade result for asset-level tracking"""
        try:
            # Update asset-level stats
            self.asset_stats_collection.update_one(
                {"symbol": symbol},
                {
                    "$inc": {"total": 1, "wins": 1 if is_win else 0},
                    "$set": {"last_updated": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )
            
            # Update asset+hour combo stats
            self.asset_hourly_collection.update_one(
                {"symbol": symbol, "hour": hour_utc},
                {
                    "$inc": {"total": 1, "wins": 1 if is_win else 0},
                    "$set": {
                        "session": session,
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
            
            # Update direction-specific stats
            dir_key = f"wins_{direction.lower()}" if is_win else f"losses_{direction.lower()}"
            self.asset_stats_collection.update_one(
                {"symbol": symbol},
                {"$inc": {dir_key: 1}},
                upsert=True
            )
            
            # Store in recent trades for direction-loss detection
            self.recent_trades_collection.insert_one({
                "symbol": symbol,
                "direction": direction.upper(),
                "is_win": is_win,
                "hour_utc": hour_utc,
                "session": session,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Keep only last 20 trades per symbol
            count = self.recent_trades_collection.count_documents({"symbol": symbol})
            if count > 20:
                oldest = list(self.recent_trades_collection.find(
                    {"symbol": symbol}, {"_id": 1}
                ).sort("timestamp", 1).limit(count - 20))
                if oldest:
                    ids = [doc["_id"] for doc in oldest]
                    self.recent_trades_collection.delete_many({"_id": {"$in": ids}})
            
        except Exception as e:
            logger.error(f"Error recording asset result: {e}")
    
    def get_consecutive_direction_losses(self, symbol: str) -> Dict:
        """
        Detect consecutive same-direction losses for an asset.
        Returns: { "count": N, "direction": "CALL"|"PUT"|None, "should_invert": bool }
        """
        try:
            recent = list(self.recent_trades_collection.find(
                {"symbol": symbol},
                {"_id": 0, "direction": 1, "is_win": 1}
            ).sort("timestamp", -1).limit(10))
            
            if not recent:
                return {"count": 0, "direction": None, "should_invert": False}
            
            count = 0
            losing_dir = None
            
            for trade in recent:
                if not trade.get("is_win"):
                    if losing_dir is None:
                        losing_dir = trade.get("direction")
                        count = 1
                    elif trade.get("direction") == losing_dir:
                        count += 1
                    else:
                        break
                else:
                    break
            
            return {
                "count": count,
                "direction": losing_dir,
                "should_invert": count >= 2
            }
        except Exception as e:
            logger.error(f"Error getting direction losses: {e}")
            return {"count": 0, "direction": None, "should_invert": False}
    
    def get_direction_win_rate(self, symbol: str, direction: str) -> Dict:
        """Get win rate for a specific direction on a specific asset"""
        try:
            stats = self.asset_stats_collection.find_one({"symbol": symbol}, {"_id": 0})
            if not stats:
                return {"win_rate": 50.0, "total": 0}
            
            dir_lower = direction.lower()
            wins = stats.get(f"wins_{dir_lower}", 0)
            losses = stats.get(f"losses_{dir_lower}", 0)
            total = wins + losses
            
            return {
                "win_rate": round(wins / total * 100, 1) if total > 0 else 50.0,
                "total": total,
                "wins": wins,
                "losses": losses
            }
        except Exception as e:
            logger.error(f"Error getting direction win rate: {e}")
            return {"win_rate": 50.0, "total": 0}
    
    def get_asset_win_rate(self, symbol: str) -> Dict:
        """Get win rate for a specific asset"""
        try:
            stats = self.asset_stats_collection.find_one({"symbol": symbol}, {"_id": 0})
            if not stats or stats.get("total", 0) == 0:
                return {"symbol": symbol, "win_rate": 50.0, "total": 0, "data": "insufficient"}
            
            total = stats.get("total", 0)
            wins = stats.get("wins", 0)
            return {
                "symbol": symbol,
                "win_rate": round(wins / total * 100, 1) if total > 0 else 50.0,
                "total": total,
                "wins": wins,
                "data": "sufficient" if total >= 10 else "insufficient"
            }
        except Exception as e:
            logger.error(f"Error getting asset win rate: {e}")
            return {"symbol": symbol, "win_rate": 50.0, "total": 0, "data": "error"}
    
    def get_asset_hour_performance(self, symbol: str) -> List[Dict]:
        """Get performance by hour for a specific asset"""
        try:
            results = list(self.asset_hourly_collection.find(
                {"symbol": symbol},
                {"_id": 0}
            ).sort("hour", 1))
            
            for r in results:
                total = r.get("total", 0)
                wins = r.get("wins", 0)
                r["win_rate"] = round(wins / total * 100, 1) if total > 0 else 50.0
            
            return results
        except Exception as e:
            logger.error(f"Error getting asset hour performance: {e}")
            return []
    
    def get_all_asset_stats(self) -> List[Dict]:
        """Get win rates for all tracked assets"""
        try:
            results = list(self.asset_stats_collection.find({}, {"_id": 0}).sort("total", -1))
            for r in results:
                total = r.get("total", 0)
                wins = r.get("wins", 0)
                r["win_rate"] = round(wins / total * 100, 1) if total > 0 else 50.0
            return results
        except Exception as e:
            logger.error(f"Error getting all asset stats: {e}")
            return []
    
    def get_worst_assets(self, threshold: float = 45.0, min_trades: int = 10) -> List[str]:
        """Get assets with win rate below threshold"""
        try:
            results = list(self.asset_stats_collection.find(
                {"total": {"$gte": min_trades}},
                {"_id": 0}
            ))
            
            worst = []
            for r in results:
                total = r.get("total", 0)
                wins = r.get("wins", 0)
                win_rate = wins / total * 100 if total > 0 else 50.0
                if win_rate < threshold:
                    worst.append(r.get("symbol", ""))
            return worst
        except Exception as e:
            logger.error(f"Error getting worst assets: {e}")
            return []


# Global asset tracker instance
asset_tracker = AssetPerformanceTracker()


def apply_premium_filters(signal: Dict, symbol: str, candles: List[Dict] = None) -> Dict:
    """
    Apply premium signal filters to an existing signal.
    Adjusts confidence based on session quality, historical performance, and market conditions.
    Returns the signal with additional premium filter data.
    """
    now = datetime.now(timezone.utc)
    hour = now.hour
    
    # Get session info
    time_filter = session_analyzer.analyze_time(symbol)
    session_quality = time_filter.session_quality
    
    # Get asset historical performance
    asset_stats = asset_tracker.get_asset_win_rate(symbol)
    
    # Get market condition if candles available
    mkt_condition = None
    if candles and len(candles) >= 20:
        mkt_condition = market_condition_analyzer.analyze(candles)
    
    # Calculate confidence adjustment
    confidence_adj = 0.0
    filter_notes = []
    
    # 1. Session quality adjustment (-10 to +5)
    if session_quality >= 85:
        confidence_adj += 5
        filter_notes.append(f"Premium session quality ({session_quality})")
    elif session_quality >= 70:
        confidence_adj += 2
        filter_notes.append(f"Good session quality ({session_quality})")
    elif session_quality < 40:
        confidence_adj -= 10
        filter_notes.append(f"Poor session quality ({session_quality}) - caution")
    elif session_quality < 55:
        confidence_adj -= 5
        filter_notes.append(f"Below-average session ({session_quality})")
    
    # 2. Historical hour win rate adjustment (-5 to +3)
    hist_wr = time_filter.historical_win_rate
    if hist_wr > 60 and hour in session_analyzer.hourly_performance and session_analyzer.hourly_performance[hour].get("total", 0) >= 10:
        confidence_adj += 3
        filter_notes.append(f"Strong hour win rate ({hist_wr:.1f}%)")
    elif hist_wr < 45 and hour in session_analyzer.hourly_performance and session_analyzer.hourly_performance[hour].get("total", 0) >= 10:
        confidence_adj -= 5
        filter_notes.append(f"Weak hour win rate ({hist_wr:.1f}%) - avoid")
    
    # 3. Asset-specific adjustment (-5 to +3)
    if asset_stats.get("data") == "sufficient":
        asset_wr = asset_stats.get("win_rate", 50)
        if asset_wr > 60:
            confidence_adj += 3
            filter_notes.append(f"Strong asset ({symbol}: {asset_wr:.1f}%)")
        elif asset_wr < 40:
            confidence_adj -= 5
            filter_notes.append(f"Weak asset ({symbol}: {asset_wr:.1f}%) - avoid")
    
    # 4. Market condition adjustment (-5 to +3)
    if mkt_condition:
        if mkt_condition in [MarketCondition.TRENDING_UP, MarketCondition.TRENDING_DOWN]:
            confidence_adj += 3
            filter_notes.append(f"Trending market ({mkt_condition.value})")
        elif mkt_condition == MarketCondition.VOLATILE:
            confidence_adj -= 5
            filter_notes.append("High volatility - reduced confidence")
        elif mkt_condition == MarketCondition.QUIET:
            confidence_adj -= 3
            filter_notes.append("Quiet market - limited opportunity")
    
    # 5. Direction-aware loss detection (-8 to 0)
    # If recent trades show consecutive losses in the SAME direction as this signal, penalize heavily
    signal_direction = signal.get("direction", "").upper()
    dir_losses = asset_tracker.get_consecutive_direction_losses(symbol)
    invert_suggestion = False
    
    if dir_losses.get("should_invert") and dir_losses.get("direction") == signal_direction:
        loss_count = dir_losses.get("count", 0)
        penalty = min(loss_count * 4, 15)  # -4 per loss, max -15
        confidence_adj -= penalty
        filter_notes.append(
            f"WARNING: {loss_count} consecutive {signal_direction} losses on {symbol} - "
            f"consider inverting (penalty: -{penalty})"
        )
        invert_suggestion = True
    elif dir_losses.get("should_invert") and dir_losses.get("direction") != signal_direction:
        # Signal is already opposite of losing direction - this is good
        confidence_adj += 2
        filter_notes.append(
            f"Signal direction ({signal_direction}) opposite to losing streak ({dir_losses.get('direction')}) - favorable"
        )
    
    # Apply adjustment to signal confidence
    original_confidence = signal.get("confidence", 0)
    adjusted_confidence = max(0, min(99, original_confidence + confidence_adj))
    
    # Add premium filter data to signal
    signal["premium_filters"] = {
        "session": time_filter.current_session.value,
        "session_quality": session_quality,
        "is_good_time": time_filter.is_good_time,
        "historical_hour_win_rate": round(hist_wr, 1),
        "asset_win_rate": asset_stats.get("win_rate", 50.0),
        "asset_total_trades": asset_stats.get("total", 0),
        "market_condition": mkt_condition.value if mkt_condition else "unknown",
        "confidence_adjustment": round(confidence_adj, 1),
        "filter_notes": filter_notes,
        "recommendation": time_filter.recommendation,
        "invert_suggestion": invert_suggestion,
        "direction_loss_streak": dir_losses
    }
    signal["confidence"] = round(adjusted_confidence, 1)
    signal["original_confidence"] = round(original_confidence, 1)
    
    return signal
