"""
MetaTrader 5 Integration Service
================================

Connects trading signals to MetaTrader 5 for automated trade execution.
Supports BUY/SELL orders, position management, and account monitoring.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import MetaTrader5 (only available on Windows)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
    logger.info("MetaTrader5 package loaded successfully")
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None
    logger.warning("MetaTrader5 package not available - MT5 features will be simulated")


class MT5OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    BUY_LIMIT = "BUY_LIMIT"
    SELL_LIMIT = "SELL_LIMIT"
    BUY_STOP = "BUY_STOP"
    SELL_STOP = "SELL_STOP"


@dataclass
class MT5AccountInfo:
    """MetaTrader 5 account information"""
    login: int
    server: str
    balance: float
    equity: float
    profit: float
    margin: float
    margin_free: float
    margin_level: float
    currency: str
    leverage: int
    connected: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "login": self.login,
            "server": self.server,
            "balance": self.balance,
            "equity": self.equity,
            "profit": self.profit,
            "margin": self.margin,
            "margin_free": self.margin_free,
            "margin_level": self.margin_level,
            "currency": self.currency,
            "leverage": self.leverage,
            "connected": self.connected
        }


@dataclass
class MT5Position:
    """Open position in MetaTrader 5"""
    ticket: int
    symbol: str
    type: str  # BUY or SELL
    volume: float
    open_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    profit: float
    open_time: datetime
    magic: int = 0
    comment: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "type": self.type,
            "volume": self.volume,
            "open_price": self.open_price,
            "current_price": self.current_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "profit": self.profit,
            "open_time": self.open_time.isoformat() if self.open_time else None,
            "magic": self.magic,
            "comment": self.comment
        }


@dataclass
class MT5TradeResult:
    """Result of a trade execution"""
    success: bool
    ticket: int = 0
    order: int = 0
    volume: float = 0
    price: float = 0
    retcode: int = 0
    comment: str = ""
    error: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "ticket": self.ticket,
            "order": self.order,
            "volume": self.volume,
            "price": self.price,
            "retcode": self.retcode,
            "comment": self.comment,
            "error": self.error
        }


class MT5ConnectionManager:
    """Manages connection to MetaTrader 5 terminal"""
    
    def __init__(self):
        self.login: Optional[int] = None
        self.password: Optional[str] = None
        self.server: Optional[str] = None
        self.path: Optional[str] = None
        self.initialized: bool = False
        self.last_error: Optional[str] = None
        self.connected_at: Optional[datetime] = None
        
        # Load credentials from environment
        self._load_credentials()
    
    def _load_credentials(self):
        """Load MT5 credentials from environment variables"""
        self.login = os.environ.get('MT5_LOGIN')
        self.password = os.environ.get('MT5_PASSWORD')
        self.server = os.environ.get('MT5_SERVER')
        self.path = os.environ.get('MT5_PATH')
        
        if self.login:
            try:
                self.login = int(self.login)
            except ValueError:
                self.login = None
    
    def is_configured(self) -> bool:
        """Check if MT5 credentials are configured"""
        return all([self.login, self.password, self.server])
    
    def connect(self) -> bool:
        """Establish connection to MetaTrader 5"""
        if not MT5_AVAILABLE:
            logger.warning("MT5 not available - running in simulation mode")
            self.initialized = True
            self.connected_at = datetime.now(timezone.utc)
            return True
        
        if not self.is_configured():
            self.last_error = "MT5 credentials not configured"
            logger.error(self.last_error)
            return False
        
        try:
            # Initialize with credentials
            if self.path:
                result = mt5.initialize(
                    path=self.path,
                    login=self.login,
                    password=self.password,
                    server=self.server
                )
            else:
                result = mt5.initialize(
                    login=self.login,
                    password=self.password,
                    server=self.server
                )
            
            if result:
                self.initialized = True
                self.connected_at = datetime.now(timezone.utc)
                self.last_error = None
                logger.info(f"Connected to MT5: {self.server}")
                return True
            else:
                error = mt5.last_error()
                self.last_error = f"MT5 initialization failed: {error}"
                logger.error(self.last_error)
                return False
                
        except Exception as e:
            self.last_error = f"Connection exception: {str(e)}"
            logger.error(self.last_error)
            return False
    
    def disconnect(self):
        """Disconnect from MetaTrader 5"""
        if MT5_AVAILABLE and self.initialized:
            mt5.shutdown()
        self.initialized = False
        self.connected_at = None
        logger.info("Disconnected from MT5")
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        if not self.initialized:
            return False
        
        if not MT5_AVAILABLE:
            return True  # Simulation mode
        
        try:
            info = mt5.terminal_info()
            return info is not None and info.connected
        except:
            return False
    
    def get_status(self) -> Dict:
        """Get current connection status"""
        return {
            "configured": self.is_configured(),
            "initialized": self.initialized,
            "connected": self.is_connected(),
            "mt5_available": MT5_AVAILABLE,
            "server": self.server,
            "login": self.login,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_error": self.last_error
        }


class MT5TradingService:
    """
    MetaTrader 5 Trading Service
    
    Handles all trading operations including order execution,
    position management, and account monitoring.
    """
    
    # Magic number for identifying our trades
    MAGIC_NUMBER = 234000
    
    def __init__(self):
        self.connection = MT5ConnectionManager()
        self.executed_trades: List[Dict] = []
        self.failed_trades: List[Dict] = []
    
    def connect(self, login: int = None, password: str = None, server: str = None) -> Dict:
        """
        Connect to MetaTrader 5
        
        Args:
            login: MT5 account number (optional, uses env if not provided)
            password: MT5 password (optional, uses env if not provided)
            server: MT5 server name (optional, uses env if not provided)
        """
        if login:
            self.connection.login = login
        if password:
            self.connection.password = password
        if server:
            self.connection.server = server
        
        success = self.connection.connect()
        
        return {
            "success": success,
            "status": self.connection.get_status(),
            "error": self.connection.last_error if not success else None
        }
    
    def disconnect(self) -> Dict:
        """Disconnect from MetaTrader 5"""
        self.connection.disconnect()
        return {
            "success": True,
            "message": "Disconnected from MT5"
        }
    
    def get_account_info(self) -> Optional[MT5AccountInfo]:
        """Get current account information"""
        if not self.connection.is_connected():
            logger.warning("MT5 not connected")
            return None
        
        if not MT5_AVAILABLE:
            # Return simulated account info
            return MT5AccountInfo(
                login=self.connection.login or 0,
                server=self.connection.server or "Demo",
                balance=10000.0,
                equity=10000.0,
                profit=0.0,
                margin=0.0,
                margin_free=10000.0,
                margin_level=0.0,
                currency="USD",
                leverage=100,
                connected=True
            )
        
        try:
            info = mt5.account_info()
            if info is None:
                return None
            
            return MT5AccountInfo(
                login=info.login,
                server=info.server,
                balance=info.balance,
                equity=info.equity,
                profit=info.profit,
                margin=info.margin,
                margin_free=info.margin_free,
                margin_level=info.margin_level,
                currency=info.currency,
                leverage=info.leverage,
                connected=True
            )
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get information about a trading symbol"""
        if not self.connection.is_connected():
            return None
        
        if not MT5_AVAILABLE:
            # Return simulated symbol info
            return {
                "symbol": symbol,
                "bid": 1.1000,
                "ask": 1.1002,
                "spread": 0.0002,
                "digits": 5,
                "point": 0.00001,
                "min_volume": 0.01,
                "max_volume": 100.0,
                "volume_step": 0.01
            }
        
        try:
            # Select symbol in Market Watch
            if not mt5.symbol_select(symbol, True):
                logger.warning(f"Symbol {symbol} not found")
                return None
            
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            
            if info is None or tick is None:
                return None
            
            return {
                "symbol": symbol,
                "bid": tick.bid,
                "ask": tick.ask,
                "spread": tick.ask - tick.bid,
                "digits": info.digits,
                "point": info.point,
                "min_volume": info.volume_min,
                "max_volume": info.volume_max,
                "volume_step": info.volume_step
            }
        except Exception as e:
            logger.error(f"Error getting symbol info: {e}")
            return None
    
    def execute_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        price: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        comment: str = "Signal Bot"
    ) -> MT5TradeResult:
        """
        Execute a trading order
        
        Args:
            symbol: Trading symbol (e.g., EURUSD)
            direction: CALL/BUY or PUT/SELL
            volume: Lot size
            price: Entry price (uses market price if not specified)
            stop_loss: Stop loss price
            take_profit: Take profit price
            comment: Order comment
        """
        if not self.connection.is_connected():
            return MT5TradeResult(
                success=False,
                error="MT5 not connected"
            )
        
        # Normalize direction
        if direction.upper() in ["CALL", "BUY"]:
            order_type = "BUY"
        elif direction.upper() in ["PUT", "SELL"]:
            order_type = "SELL"
        else:
            return MT5TradeResult(
                success=False,
                error=f"Invalid direction: {direction}"
            )
        
        if not MT5_AVAILABLE:
            # Simulate order execution
            import random
            ticket = random.randint(100000, 999999)
            
            result = MT5TradeResult(
                success=True,
                ticket=ticket,
                order=ticket,
                volume=volume,
                price=price or 1.1000,
                retcode=10009,
                comment="Simulated order executed"
            )
            
            self.executed_trades.append({
                "symbol": symbol,
                "direction": order_type,
                "volume": volume,
                "price": result.price,
                "ticket": ticket,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "simulated": True
            })
            
            logger.info(f"Simulated {order_type} order: {symbol} {volume} lots")
            return result
        
        try:
            # Get current price if not specified
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return MT5TradeResult(
                    success=False,
                    error=f"Failed to get price for {symbol}"
                )
            
            if price is None:
                price = tick.ask if order_type == "BUY" else tick.bid
            
            # Determine MT5 order type
            mt5_order_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL
            
            # Create trade request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5_order_type,
                "price": price,
                "deviation": 20,
                "magic": self.MAGIC_NUMBER,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            if stop_loss is not None:
                request["sl"] = stop_loss
            if take_profit is not None:
                request["tp"] = take_profit
            
            # Check order validity
            check = mt5.order_check(request)
            if check.retcode != 0:
                logger.warning(f"Order check failed: {check.comment}")
            
            # Send order
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                trade_result = MT5TradeResult(
                    success=True,
                    ticket=result.deal,
                    order=result.order,
                    volume=result.volume,
                    price=result.price,
                    retcode=result.retcode,
                    comment="Order executed successfully"
                )
                
                self.executed_trades.append({
                    "symbol": symbol,
                    "direction": order_type,
                    "volume": volume,
                    "price": result.price,
                    "ticket": result.deal,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                logger.info(f"Order executed: {symbol} {order_type} {volume} lots @ {result.price}")
                return trade_result
            else:
                trade_result = MT5TradeResult(
                    success=False,
                    retcode=result.retcode,
                    error=result.comment
                )
                
                self.failed_trades.append({
                    "symbol": symbol,
                    "direction": order_type,
                    "volume": volume,
                    "error": result.comment,
                    "retcode": result.retcode,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                logger.error(f"Order failed: {result.comment}")
                return trade_result
                
        except Exception as e:
            logger.error(f"Order execution error: {e}")
            return MT5TradeResult(
                success=False,
                error=str(e)
            )
    
    def get_positions(self) -> List[MT5Position]:
        """Get all open positions"""
        if not self.connection.is_connected():
            return []
        
        if not MT5_AVAILABLE:
            # Return empty list in simulation mode
            return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            
            result = []
            for pos in positions:
                result.append(MT5Position(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    type="BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                    volume=pos.volume,
                    open_price=pos.price_open,
                    current_price=pos.price_current,
                    stop_loss=pos.sl,
                    take_profit=pos.tp,
                    profit=pos.profit,
                    open_time=datetime.fromtimestamp(pos.time, tz=timezone.utc),
                    magic=pos.magic,
                    comment=pos.comment
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def close_position(self, ticket: int, comment: str = "Closed by signal") -> MT5TradeResult:
        """Close an open position by ticket"""
        if not self.connection.is_connected():
            return MT5TradeResult(success=False, error="MT5 not connected")
        
        if not MT5_AVAILABLE:
            return MT5TradeResult(
                success=True,
                ticket=ticket,
                comment="Simulated position close"
            )
        
        try:
            # Get position
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return MT5TradeResult(success=False, error="Position not found")
            
            pos = position[0]
            
            # Determine close order type
            if pos.type == mt5.ORDER_TYPE_BUY:
                close_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(pos.symbol).bid
            else:
                close_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": self.MAGIC_NUMBER,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Position {ticket} closed successfully")
                return MT5TradeResult(
                    success=True,
                    ticket=ticket,
                    price=result.price,
                    comment="Position closed"
                )
            else:
                logger.error(f"Failed to close position: {result.comment}")
                return MT5TradeResult(
                    success=False,
                    error=result.comment,
                    retcode=result.retcode
                )
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return MT5TradeResult(success=False, error=str(e))
    
    def modify_position(
        self,
        ticket: int,
        stop_loss: float = None,
        take_profit: float = None
    ) -> MT5TradeResult:
        """Modify stop loss and/or take profit of an open position"""
        if not self.connection.is_connected():
            return MT5TradeResult(success=False, error="MT5 not connected")
        
        if not MT5_AVAILABLE:
            return MT5TradeResult(
                success=True,
                ticket=ticket,
                comment="Simulated position modification"
            )
        
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return MT5TradeResult(success=False, error="Position not found")
            
            pos = position[0]
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": pos.symbol,
                "sl": stop_loss if stop_loss is not None else pos.sl,
                "tp": take_profit if take_profit is not None else pos.tp,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Position {ticket} modified")
                return MT5TradeResult(
                    success=True,
                    ticket=ticket,
                    comment="Position modified"
                )
            else:
                return MT5TradeResult(
                    success=False,
                    error=result.comment,
                    retcode=result.retcode
                )
                
        except Exception as e:
            logger.error(f"Error modifying position: {e}")
            return MT5TradeResult(success=False, error=str(e))
    
    def process_signal(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        volume: float = 0.1,
        stop_loss: float = None,
        take_profit: float = None,
        strategy_name: str = "Signal Bot"
    ) -> Dict:
        """
        Process a trading signal and execute order if conditions are met
        
        Args:
            symbol: Trading symbol
            direction: CALL/BUY or PUT/SELL
            confidence: Signal confidence (0-100)
            volume: Trade volume in lots
            stop_loss: Stop loss price
            take_profit: Take profit price
            strategy_name: Name of the strategy generating the signal
        """
        # Minimum confidence threshold
        MIN_CONFIDENCE = 65
        
        if confidence < MIN_CONFIDENCE:
            return {
                "success": False,
                "executed": False,
                "reason": f"Confidence {confidence}% below minimum {MIN_CONFIDENCE}%"
            }
        
        # Get symbol info
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            return {
                "success": False,
                "executed": False,
                "reason": f"Symbol {symbol} not available"
            }
        
        # Execute the order
        result = self.execute_order(
            symbol=symbol,
            direction=direction,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"{strategy_name} - {confidence:.0f}%"
        )
        
        return {
            "success": result.success,
            "executed": result.success,
            "trade": result.to_dict(),
            "symbol_info": symbol_info
        }
    
    def get_trade_history(self, limit: int = 50) -> Dict:
        """Get recent trade history"""
        return {
            "executed": self.executed_trades[-limit:],
            "failed": self.failed_trades[-limit:],
            "total_executed": len(self.executed_trades),
            "total_failed": len(self.failed_trades)
        }


# Global instance
mt5_service = MT5TradingService()


def get_mt5_service() -> MT5TradingService:
    """Get the MT5 trading service instance"""
    return mt5_service
