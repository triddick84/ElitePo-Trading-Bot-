from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid

class TradingMode(str, Enum):
    DEMO = "demo"
    LIVE = "live"

class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    CALL = "CALL"
    PUT = "PUT"

class TradingStrategy(str, Enum):
    CCI_20 = "cci_20"
    EMA_CROSSOVER = "ema_crossover"
    RSI_5 = "rsi_5"
    MACD_MOMENTUM = "macd_momentum"
    HYBRID = "hybrid"
    PLATFORM_SIGNALS = "platform_signals"

class AssetType(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"
    STOCKS = "stocks"
    COMMODITIES = "commodities"
    INDICES = "indices"
    OTC = "otc"

class ChartType(str, Enum):
    JAPANESE_CANDLES = "japanese_candles"
    LINE = "line"
    BARS = "bars"
    HEIKIN_ASHI = "heikin_ashi"

# Data Models
class MarketData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    asset_type: AssetType
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
class TechnicalIndicators(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    timestamp: datetime
    rsi_5: Optional[float] = None
    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    ema_3: Optional[float] = None
    ema_8: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    cci_20: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    atr: Optional[float] = None

class SentimentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    timestamp: datetime
    sentiment_score: float  # -1 to 1 (bearish to bullish)
    confidence: float  # 0 to 1
    news_sentiment: Optional[float] = None
    social_sentiment: Optional[float] = None
    sources: List[str] = []
    key_factors: List[str] = []

class TradingSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    asset_type: AssetType
    direction: SignalDirection
    entry_price: float
    expiration_minutes: float  # Supports fractional minutes for sub-minute expirations (e.g., 0.5 for 30s)
    timeframe: str = "1m"  # Pocket Option timeframe (5s, 15s, 30s, 1m, 2m, 3m, 5m, 10m, 15m, 30m)
    market_type: str = "regular"  # "regular" or "otc"
    probability: float  # 0 to 100
    confidence_level: str  # "HIGH", "MEDIUM", "LOW"
    strategy_used: TradingStrategy
    technical_analysis: Dict[str, Any]
    sentiment_analysis: Optional[Dict[str, Any]] = None
    market_analysis_summary: str
    justification: str
    risk_assessment: str
    suggested_stake: float
    precision_entry_time: Optional[datetime] = None  # Real entry time for trade execution (Chicago timezone)
    popup_display_time: Optional[datetime] = None  # When to show popup (10s before entry for force generate)
    countdown_duration: Optional[int] = 10  # Countdown timer duration in seconds
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # Chicago timezone synchronized
    
    # Quality check fields
    quality_check_passed: bool = True
    quality_notes: str = ""
    
    # Performance tracking
    actual_outcome: Optional[str] = None  # "WIN", "LOSS"
    profit_loss: Optional[float] = None
    closed_at: Optional[datetime] = None

class BacktestResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy: TradingStrategy
    symbol: str
    start_date: datetime
    end_date: datetime
    total_signals: int
    winning_signals: int
    losing_signals: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    total_return: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TradingConfiguration(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(default="default_user")
    trading_mode: TradingMode = TradingMode.DEMO
    active_strategies: List[TradingStrategy] = [TradingStrategy.HYBRID]
    target_assets: List[AssetType] = [AssetType.FOREX, AssetType.CRYPTO]
    selected_assets: List[str] = ['EURUSD_regular', 'BTCUSD_regular']  # Specific asset selections
    selected_expirations: List[str] = ['1m', '2m']  # Trade expiration times (5s, 15s, 30s, 1m, 2m, 3m, 5m)
    chart_type: ChartType = ChartType.JAPANESE_CANDLES  # Chart type for signal generation
    risk_tolerance: str = "medium"  # low, medium, high
    max_stake_per_trade: float = 10.0
    max_daily_trades: int = 50
    min_probability_threshold: float = Field(default=80.0, ge=50.0, le=99.0)
    auto_trading_enabled: bool = False
    invert_signals: bool = False  # Global invert signals setting
    sound_alerts_enabled: bool = True  # Sound alerts for new signals
    candle_sync_enabled: bool = False  # Wait for candle formation before generating signals (Pocket Option sync)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PerformanceMetrics(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: datetime
    total_signals: int
    winning_signals: int
    losing_signals: int
    win_rate: float
    profit_loss: float
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    max_drawdown: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FlexibleStrategyRequest(BaseModel):
    """Request model for flexible trading strategy with customizable parameters"""
    asset_symbol: str = Field(..., description="Trading symbol (e.g., EURUSD, BTCUSD)")
    market_type: str = Field(default='regular', description="Market type: 'regular' or 'otc'")
    chart_timeframe: str = Field(default='30s', description="Chart timeframe for analysis (5s, 10s, 15s, 30s, 1m, 2m, 3m, 5m)")
    trade_duration_seconds: int = Field(default=82, ge=5, le=3600, description="Trade/signal expiration in seconds (e.g., 82 = 1m 22s)")
    force_signal: bool = Field(default=False, description="Force signal generation based on current market state")
    
    # Customizable indicator parameters
    sma_fast: int = Field(default=6, ge=1, le=50, description="Fast SMA period")
    sma_slow: int = Field(default=12, ge=1, le=100, description="Slow SMA period")
    supertrend_atr_period: int = Field(default=2, ge=1, le=50, description="SuperTrend ATR period")
    supertrend_multiplier: float = Field(default=2.2, ge=0.1, le=10.0, description="SuperTrend multiplier")
    ao_short_period: int = Field(default=6, ge=1, le=50, description="Awesome Oscillator short period")
    ao_long_period: int = Field(default=12, ge=1, le=100, description="Awesome Oscillator long period")


class AdaptiveStrategyConfig(BaseModel):
    """Configuration for Adaptive Market Condition System"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(default="default_user")
    
    # Enable/Disable adaptive system
    enabled: bool = Field(default=True, description="Enable adaptive market condition detection")
    
    # ADX Thresholds for market condition detection
    adx_trending_threshold: float = Field(default=25.0, ge=15.0, le=50.0, description="ADX > this value = Trending market")
    adx_ranging_threshold: float = Field(default=20.0, ge=10.0, le=30.0, description="ADX < this value = Ranging market")
    
    # Trending Market Indicators (user can select multiple)
    trending_indicators: List[str] = Field(
        default=["MACD", "Parabolic_SAR", "EMA"],
        description="Indicators for trending markets. Options: MACD, Parabolic_SAR, EMA, RSI, Stochastic, Bollinger_Bands"
    )
    
    # Ranging/Volatile Market Indicators (user can select multiple)
    ranging_indicators: List[str] = Field(
        default=["RSI", "Volume", "Bollinger_Bands", "EMA"],
        description="Indicators for ranging/volatile markets. Options: RSI, Volume, Bollinger_Bands, EMA, MACD, Stochastic"
    )
    
    # Strategy preferences
    trending_execution_delay: float = Field(default=3.0, ge=0.5, le=10.0, description="Execution delay for trending markets (seconds)")
    ranging_execution_delay: float = Field(default=1.5, ge=0.5, le=10.0, description="Execution delay for ranging markets (seconds)")
    ranging_signal_threshold: float = Field(default=80.0, ge=70.0, le=95.0, description="Higher threshold for ranging markets to filter noise")
    
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AdaptiveStrategyUpdateRequest(BaseModel):
    """Request model for updating adaptive strategy configuration"""
    enabled: Optional[bool] = None
    adx_trending_threshold: Optional[float] = Field(None, ge=15.0, le=50.0)
    adx_ranging_threshold: Optional[float] = Field(None, ge=10.0, le=30.0)
    trending_indicators: Optional[List[str]] = None
    ranging_indicators: Optional[List[str]] = None
    trending_execution_delay: Optional[float] = Field(None, ge=0.5, le=10.0)
    ranging_execution_delay: Optional[float] = Field(None, ge=0.5, le=10.0)
    ranging_signal_threshold: Optional[float] = Field(None, ge=70.0, le=95.0)

