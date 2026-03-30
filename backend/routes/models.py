"""Pydantic request/response models extracted from server.py."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from trading_models import TradingMode, TradingStrategy, AssetType, SignalDirection

# Enums needed by models
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class BotStartRequest(BaseModel):
    trading_mode: TradingMode = TradingMode.DEMO
    active_strategies: List[TradingStrategy] = [TradingStrategy.HYBRID]
    target_assets: List[AssetType] = [AssetType.FOREX, AssetType.CRYPTO]
    selected_assets: List[str] = ['EURUSD_regular', 'BTCUSD_regular']
    selected_expirations: List[str] = ['1m', '2m']
    risk_tolerance: str = "medium"
    max_stake_per_trade: float = 10.0
    max_daily_trades: int = 50
    min_probability_threshold: float = Field(default=80.0, ge=50.0, le=99.0)
    auto_trading_enabled: bool = False
    invert_signals: bool = False
    sound_alerts_enabled: bool = True
    popup_notifications: bool = True
    selected_timeframe: Optional[str] = '1m'
    selected_strategy: Optional[str] = ''
    chart_config: Optional[Dict[str, Any]] = None
    flexible_config: Optional[Dict[str, Any]] = None


class BotStatusResponse(BaseModel):
    is_running: bool
    current_mode: str
    active_strategies: List[str]
    signals_today: int
    performance: Dict[str, Any]
    auto_signal_generation: bool = False


class BacktestRequest(BaseModel):
    strategy: TradingStrategy
    symbol: str
    days: int = 30


class StrategySelectionRequest(BaseModel):
    timeframe: str
    strategy_id: str

class QuickAuthTestRequest(BaseModel):
    auth_message: str


class SSIDConnectRequest(BaseModel):
    ssid: str
    demo: bool = False


class DataCollectionStartRequest(BaseModel):
    """Request to start data collection"""
    assets: Optional[List[str]] = None
    timeframes: Optional[List[str]] = None



class TrainModelRequest(BaseModel):
    """Request to train a model"""
    asset: str
    timeframe: str
    confidence_threshold: Optional[float] = 0.75
    min_samples: Optional[int] = 500


class GenerateSignalRequest(BaseModel):
    """Request to generate a signal"""
    asset: str
    timeframe: str
    candles: List[Dict[str, Any]]


class UserRegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    settings: Optional[Dict] = None


class TelegramMessageRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None


class TelegramSettingsRequest(BaseModel):
    auto_trading_enabled: Optional[bool] = None
    demo_mode: Optional[bool] = None
    trade_amount: Optional[float] = None


class OandaConfigRequest(BaseModel):
    access_token: str
    account_id: str
    environment: str = "practice"


class AITrainingRequest(BaseModel):
    instrument: str = "EUR_USD"
    timeframe: str = "M1"
    candle_count: int = 500

class AISignalRequest(BaseModel):
    instrument: str = "EUR_USD"
    timeframe: str = "M1"
    custom_strategy_id: Optional[str] = None

class TradeResultRequest(BaseModel):
    signal_id: str
    outcome: str  # "WIN" or "LOSS"


class LargeDataRequest(BaseModel):
    instrument: str = "EUR_USD"
    granularity: str = "H1"
    from_time: str  # ISO format: "2024-01-01T00:00:00Z"
    to_time: str    # ISO format: "2024-12-31T23:59:59Z"


class TradingViewAlert(BaseModel):
    """Model for TradingView webhook alerts"""
    ticker: str
    action: str  # "buy", "sell", "call", "put"
    price: Optional[float] = None
    timeframe: Optional[str] = "1m"
    strategy: Optional[str] = "TradingView Alert"
    message: Optional[str] = ""


class MT5Config(BaseModel):
    """MetaTrader 5 configuration"""
    login: int
    password: str
    server: str
    path: Optional[str] = None


class MT5TradeRequest(BaseModel):
    """MT5 trade request"""
    symbol: str
    order_type: str  # "BUY" or "SELL"
    volume: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class ArbitrageCheckRequest(BaseModel):
    pairs: List[List[str]] = [["EUR_USD", "GBP_USD"], ["EUR_USD", "USD_JPY"]]


