"""
MetaTrader 5 ZeroMQ Bridge Service
==================================

Connects to MT5 terminal via ZeroMQ for remote trading operations.
This allows Linux servers to communicate with MT5 running on Windows.

Architecture:
- MT5 Terminal (Windows) runs ZeroMQ EA (JsonAPI.mq5)
- This service connects to MT5's ZeroMQ sockets
- Supports: Market orders, pending orders, position management, account info

Setup Requirements:
1. MT5 terminal running on Windows with ZeroMQ EA
2. EA configured with PUB port (e.g., 15555) and PUSH port (e.g., 15556)
3. Firewall allowing connections from this server
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading
import time

logger = logging.getLogger(__name__)

# Try to import ZeroMQ
try:
    import zmq
    import zmq.asyncio
    ZMQ_AVAILABLE = True
    logger.info("ZeroMQ package loaded successfully")
except ImportError:
    ZMQ_AVAILABLE = False
    zmq = None
    logger.warning("ZeroMQ not available - install with: pip install pyzmq")


class MT5ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MT5OrderType(Enum):
    BUY = "OP_BUY"
    SELL = "OP_SELL"
    BUY_LIMIT = "OP_BUYLIMIT"
    SELL_LIMIT = "OP_SELLLIMIT"
    BUY_STOP = "OP_BUYSTOP"
    SELL_STOP = "OP_SELLSTOP"


@dataclass
class MT5ZMQConfig:
    """Configuration for ZeroMQ connection to MT5"""
    host: str = "localhost"  # MT5 terminal IP address
    sub_port: int = 15555    # Subscribe to tick data
    push_port: int = 15556   # Send commands
    pull_port: int = 15557   # Receive responses
    timeout_ms: int = 5000   # Socket timeout
    reconnect_interval: int = 5  # Seconds between reconnection attempts
    
    @classmethod
    def from_env(cls) -> "MT5ZMQConfig":
        return cls(
            host=os.environ.get("MT5_ZMQ_HOST", "localhost"),
            sub_port=int(os.environ.get("MT5_ZMQ_SUB_PORT", "15555")),
            push_port=int(os.environ.get("MT5_ZMQ_PUSH_PORT", "15556")),
            pull_port=int(os.environ.get("MT5_ZMQ_PULL_PORT", "15557")),
            timeout_ms=int(os.environ.get("MT5_ZMQ_TIMEOUT", "5000")),
        )


@dataclass
class MT5TickData:
    """Real-time tick data from MT5"""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    time: datetime
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "spread": round((self.ask - self.bid) * 10000, 1),  # In pips for forex
            "volume": self.volume,
            "time": self.time.isoformat() if self.time else None
        }


@dataclass
class MT5OrderRequest:
    """Order request to send to MT5"""
    action: str  # "TRADE" or "CLOSE"
    symbol: str
    order_type: MT5OrderType
    volume: float
    price: float = 0  # 0 for market orders
    stop_loss: float = 0
    take_profit: float = 0
    magic: int = 123456  # EA magic number
    comment: str = "GPT Signal Bot"
    ticket: int = 0  # For closing positions
    
    def to_zmq_message(self) -> Dict:
        """Convert to ZeroMQ message format expected by MT5 EA"""
        return {
            "action": self.action,
            "actionType": self.order_type.value if isinstance(self.order_type, MT5OrderType) else self.order_type,
            "symbol": self.symbol,
            "volume": self.volume,
            "price": self.price,
            "stoploss": self.stop_loss,
            "takeprofit": self.take_profit,
            "magic": self.magic,
            "comment": self.comment,
            "ticket": self.ticket
        }


@dataclass
class MT5OrderResponse:
    """Response from MT5 after order execution"""
    success: bool
    ticket: int = 0
    message: str = ""
    error_code: int = 0
    
    @classmethod
    def from_zmq_response(cls, response: Dict) -> "MT5OrderResponse":
        return cls(
            success=response.get("_response", "") == "OK" or response.get("error", False) is False,
            ticket=response.get("ticket", 0),
            message=response.get("_response", response.get("message", "")),
            error_code=response.get("error_code", 0)
        )


class MT5ZeroMQBridge:
    """
    ZeroMQ bridge for communicating with MetaTrader 5
    """
    
    def __init__(self, config: Optional[MT5ZMQConfig] = None):
        self.config = config or MT5ZMQConfig.from_env()
        self.status = MT5ConnectionStatus.DISCONNECTED
        
        self.context = None
        self.sub_socket = None  # Receive ticks
        self.push_socket = None  # Send orders
        self.pull_socket = None  # Receive responses
        
        self.tick_callbacks: List[Callable[[MT5TickData], None]] = []
        self.is_running = False
        self.tick_thread = None
        
        # Simulated data for when not connected
        self.simulated = True
        self.simulated_account = {
            "login": 12345678,
            "server": "Simulated-Server",
            "balance": 10000.0,
            "equity": 10000.0,
            "profit": 0.0,
            "margin": 0.0,
            "margin_free": 10000.0,
            "margin_level": 0.0,
            "currency": "USD",
            "leverage": 100
        }
        self.simulated_positions = []
        self.position_counter = 1000000
        
        logger.info(f"MT5 ZeroMQ Bridge initialized - Host: {self.config.host}")
    
    async def connect(self) -> bool:
        """Connect to MT5 ZeroMQ sockets"""
        if not ZMQ_AVAILABLE:
            logger.warning("ZeroMQ not available, running in simulation mode")
            self.simulated = True
            self.status = MT5ConnectionStatus.CONNECTED
            return True
        
        try:
            self.status = MT5ConnectionStatus.CONNECTING
            
            # Create async context
            self.context = zmq.asyncio.Context()
            
            # Subscribe socket for tick data
            self.sub_socket = self.context.socket(zmq.SUB)
            self.sub_socket.connect(f"tcp://{self.config.host}:{self.config.sub_port}")
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all
            self.sub_socket.setsockopt(zmq.RCVTIMEO, self.config.timeout_ms)
            
            # Push socket for sending orders
            self.push_socket = self.context.socket(zmq.PUSH)
            self.push_socket.connect(f"tcp://{self.config.host}:{self.config.push_port}")
            self.push_socket.setsockopt(zmq.SNDTIMEO, self.config.timeout_ms)
            
            # Pull socket for receiving responses
            self.pull_socket = self.context.socket(zmq.PULL)
            self.pull_socket.connect(f"tcp://{self.config.host}:{self.config.pull_port}")
            self.pull_socket.setsockopt(zmq.RCVTIMEO, self.config.timeout_ms)
            
            self.status = MT5ConnectionStatus.CONNECTED
            self.simulated = False
            logger.info(f"Connected to MT5 ZeroMQ at {self.config.host}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MT5 ZeroMQ: {e}")
            self.status = MT5ConnectionStatus.ERROR
            self.simulated = True
            return False
    
    def disconnect(self):
        """Disconnect from MT5 ZeroMQ"""
        self.is_running = False
        
        if self.sub_socket:
            self.sub_socket.close()
        if self.push_socket:
            self.push_socket.close()
        if self.pull_socket:
            self.pull_socket.close()
        if self.context:
            self.context.term()
        
        self.status = MT5ConnectionStatus.DISCONNECTED
        logger.info("Disconnected from MT5 ZeroMQ")
    
    async def send_command(self, command: Dict) -> Dict:
        """Send command to MT5 and receive response"""
        if self.simulated:
            return await self._simulate_command(command)
        
        try:
            # Send command
            message = json.dumps(command)
            await self.push_socket.send_string(message)
            
            # Receive response
            response_str = await self.pull_socket.recv_string()
            response = json.loads(response_str)
            
            return response
            
        except Exception as e:
            logger.error(f"ZeroMQ command error: {e}")
            return {"error": True, "message": str(e)}
    
    async def _simulate_command(self, command: Dict) -> Dict:
        """Simulate MT5 command response"""
        action = command.get("action", "")
        
        if action == "TRADE":
            # Simulate order execution
            self.position_counter += 1
            order_type = command.get("actionType", "OP_BUY")
            
            position = {
                "ticket": self.position_counter,
                "symbol": command.get("symbol", "EURUSD"),
                "type": "BUY" if "BUY" in order_type else "SELL",
                "volume": command.get("volume", 0.01),
                "open_price": command.get("price", 1.0850),
                "stop_loss": command.get("stoploss", 0),
                "take_profit": command.get("takeprofit", 0),
                "profit": 0.0,
                "open_time": datetime.now(timezone.utc).isoformat()
            }
            self.simulated_positions.append(position)
            
            return {
                "_response": "OK",
                "ticket": self.position_counter,
                "message": f"Simulated {position['type']} order opened"
            }
        
        elif action == "CLOSE":
            ticket = command.get("ticket", 0)
            self.simulated_positions = [p for p in self.simulated_positions if p["ticket"] != ticket]
            return {
                "_response": "OK",
                "ticket": ticket,
                "message": "Simulated position closed"
            }
        
        elif action == "GET_POSITIONS":
            return {
                "_response": "OK",
                "positions": self.simulated_positions
            }
        
        elif action == "GET_ACCOUNT":
            return {
                "_response": "OK",
                "account": self.simulated_account
            }
        
        return {"_response": "OK", "message": "Simulated response"}
    
    async def place_market_order(
        self,
        symbol: str,
        order_type: str,  # "BUY" or "SELL"
        volume: float,
        stop_loss: float = 0,
        take_profit: float = 0,
        comment: str = "GPT Signal Bot"
    ) -> MT5OrderResponse:
        """Place a market order"""
        mt5_order_type = MT5OrderType.BUY if order_type.upper() == "BUY" else MT5OrderType.SELL
        
        request = MT5OrderRequest(
            action="TRADE",
            symbol=symbol,
            order_type=mt5_order_type,
            volume=volume,
            price=0,  # Market order
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=comment
        )
        
        response = await self.send_command(request.to_zmq_message())
        return MT5OrderResponse.from_zmq_response(response)
    
    async def close_position(self, ticket: int) -> MT5OrderResponse:
        """Close an open position by ticket"""
        command = {
            "action": "CLOSE",
            "ticket": ticket
        }
        response = await self.send_command(command)
        return MT5OrderResponse.from_zmq_response(response)
    
    async def close_all_positions(self, symbol: Optional[str] = None) -> List[MT5OrderResponse]:
        """Close all positions, optionally filtered by symbol"""
        positions = await self.get_positions()
        results = []
        
        for pos in positions:
            if symbol is None or pos.get("symbol") == symbol:
                result = await self.close_position(pos.get("ticket", 0))
                results.append(result)
        
        return results
    
    async def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        response = await self.send_command({"action": "GET_POSITIONS"})
        return response.get("positions", [])
    
    async def get_account_info(self) -> Dict:
        """Get account information"""
        response = await self.send_command({"action": "GET_ACCOUNT"})
        return response.get("account", {})
    
    async def get_symbol_info(self, symbol: str) -> Dict:
        """Get symbol information"""
        response = await self.send_command({
            "action": "GET_SYMBOL",
            "symbol": symbol
        })
        return response
    
    def get_status(self) -> Dict:
        """Get bridge connection status"""
        return {
            "status": self.status.value,
            "host": self.config.host,
            "sub_port": self.config.sub_port,
            "push_port": self.config.push_port,
            "simulated": self.simulated,
            "zmq_available": ZMQ_AVAILABLE
        }


class MT5TradingIntegration:
    """
    High-level MT5 trading integration
    Combines ZeroMQ bridge with signal processing
    """
    
    def __init__(self):
        self.bridge = MT5ZeroMQBridge()
        self.is_connected = False
        self.trade_history: List[Dict] = []
        
    async def initialize(self) -> bool:
        """Initialize MT5 connection"""
        self.is_connected = await self.bridge.connect()
        return self.is_connected
    
    async def execute_signal(
        self,
        signal: Dict,
        volume: float = 0.01
    ) -> Dict:
        """
        Execute a trading signal on MT5
        
        Args:
            signal: Signal dict with direction, symbol, etc.
            volume: Lot size
        """
        direction = signal.get("direction", "").upper()
        symbol = signal.get("symbol", "EURUSD")
        
        # Normalize symbol for MT5
        mt5_symbol = symbol.replace("_OTC", "").replace("_", "")
        
        # Determine order type
        if direction in ["CALL", "BUY"]:
            order_type = "BUY"
        elif direction in ["PUT", "SELL"]:
            order_type = "SELL"
        else:
            return {"success": False, "error": f"Invalid direction: {direction}"}
        
        # Calculate SL/TP if provided in signal
        stop_loss = signal.get("stop_loss_price", 0)
        take_profit = signal.get("take_profit_price", 0)
        
        # Place order
        result = await self.bridge.place_market_order(
            symbol=mt5_symbol,
            order_type=order_type,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"GPT Signal: {signal.get('strategy_name', 'auto')}"
        )
        
        # Record trade
        trade_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal": signal,
            "order_type": order_type,
            "symbol": mt5_symbol,
            "volume": volume,
            "result": {
                "success": result.success,
                "ticket": result.ticket,
                "message": result.message
            }
        }
        self.trade_history.append(trade_record)
        
        return trade_record
    
    async def get_status(self) -> Dict:
        """Get MT5 integration status"""
        account = await self.bridge.get_account_info() if self.is_connected else {}
        positions = await self.bridge.get_positions() if self.is_connected else []
        
        return {
            "connected": self.is_connected,
            "bridge_status": self.bridge.get_status(),
            "account": account,
            "open_positions": len(positions),
            "positions": positions,
            "trade_count": len(self.trade_history)
        }


# Global instances
mt5_zmq_bridge = MT5ZeroMQBridge()
mt5_integration = MT5TradingIntegration()


def get_mt5_bridge() -> MT5ZeroMQBridge:
    return mt5_zmq_bridge


def get_mt5_integration() -> MT5TradingIntegration:
    return mt5_integration
