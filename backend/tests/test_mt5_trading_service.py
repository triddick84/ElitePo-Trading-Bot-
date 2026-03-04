"""
MT5 Trading Service Integration Tests
=====================================
Tests for MetaTrader 5 API endpoints in simulation mode.
MT5 is running in simulation mode since actual MT5 terminal requires Windows.
All MT5 operations return simulated results.

Tests cover:
- GET /api/mt5/status - Get MT5 connection status
- POST /api/mt5/connect - Connect to MT5 (simulation mode)
- GET /api/mt5/account - Get account info
- GET /api/mt5/symbol/{symbol} - Get symbol info
- POST /api/mt5/order - Execute order
- POST /api/mt5/signal/process - Process signal through MT5
- GET /api/mt5/positions - Get open positions
- GET /api/mt5/history - Get trade history
- POST /api/signals/high-accuracy/generate - Generate high accuracy signal
- GET /api/signals/auto/status - Check auto generator status
- GET /api/pocket-option/realtime/status - Check PO connection
"""

import pytest
import requests
import os
from datetime import datetime


# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable is not set")


class TestMT5ConnectionStatus:
    """Tests for MT5 connection status endpoint"""
    
    def test_mt5_status_returns_success(self):
        """GET /api/mt5/status - Should return connection status"""
        response = requests.get(f"{BASE_URL}/api/mt5/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        assert "status" in data, "Response should have 'status' field"
        
        status = data["status"]
        assert "mt5_available" in status, "Status should contain 'mt5_available'"
        assert "configured" in status, "Status should contain 'configured'"
        assert "initialized" in status, "Status should contain 'initialized'"
        assert "connected" in status, "Status should contain 'connected'"
        
        print(f"MT5 Status: available={status.get('mt5_available')}, connected={status.get('connected')}")


class TestMT5Connection:
    """Tests for MT5 connect/disconnect endpoints"""
    
    def test_mt5_connect_with_credentials(self):
        """POST /api/mt5/connect - Should connect to MT5 (simulation mode)"""
        # Use test credentials from request
        params = {
            "login": 12345,
            "password": "test",
            "server": "Demo"
        }
        
        response = requests.post(f"{BASE_URL}/api/mt5/connect", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        assert "status" in data, "Response should have 'status' field"
        
        # In simulation mode, connection should always succeed
        assert data["success"] == True, f"Expected success=True in simulation mode, got {data}"
        
        status = data["status"]
        print(f"MT5 Connection: success={data['success']}, server={status.get('server')}")
    
    def test_mt5_connect_without_credentials(self):
        """POST /api/mt5/connect - Should use existing/env credentials"""
        response = requests.post(f"{BASE_URL}/api/mt5/connect")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        # Without credentials, may fail or use env vars - both are valid
        print(f"MT5 Connect (no creds): success={data.get('success')}")


class TestMT5AccountInfo:
    """Tests for MT5 account information endpoint"""
    
    def test_mt5_account_info(self):
        """GET /api/mt5/account - Should return account info"""
        # First connect to ensure we have a connection
        requests.post(f"{BASE_URL}/api/mt5/connect", params={
            "login": 12345,
            "password": "test",
            "server": "Demo"
        })
        
        response = requests.get(f"{BASE_URL}/api/mt5/account")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        
        if data["success"]:
            assert "account" in data, "Successful response should have 'account' field"
            account = data["account"]
            
            # Verify expected fields in simulated account
            assert "balance" in account, "Account should have 'balance'"
            assert "equity" in account, "Account should have 'equity'"
            assert "currency" in account, "Account should have 'currency'"
            assert "leverage" in account, "Account should have 'leverage'"
            
            print(f"MT5 Account: balance={account.get('balance')}, currency={account.get('currency')}")
        else:
            print(f"Account info not available (expected when not connected): {data.get('message')}")


class TestMT5SymbolInfo:
    """Tests for MT5 symbol information endpoint"""
    
    def test_mt5_symbol_info_eurusd(self):
        """GET /api/mt5/symbol/EURUSD - Should return EURUSD symbol info"""
        # First connect
        requests.post(f"{BASE_URL}/api/mt5/connect", params={
            "login": 12345,
            "password": "test",
            "server": "Demo"
        })
        
        response = requests.get(f"{BASE_URL}/api/mt5/symbol/EURUSD")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        
        if data["success"]:
            assert "symbol_info" in data, "Successful response should have 'symbol_info'"
            info = data["symbol_info"]
            
            # Verify expected fields
            assert "symbol" in info, "Symbol info should have 'symbol'"
            assert info["symbol"] == "EURUSD", f"Expected EURUSD, got {info.get('symbol')}"
            assert "bid" in info, "Symbol info should have 'bid'"
            assert "ask" in info, "Symbol info should have 'ask'"
            assert "spread" in info, "Symbol info should have 'spread'"
            
            print(f"EURUSD Info: bid={info.get('bid')}, ask={info.get('ask')}, spread={info.get('spread')}")
        else:
            print(f"Symbol info not available: {data.get('message')}")
    
    def test_mt5_symbol_info_gbpusd(self):
        """GET /api/mt5/symbol/GBPUSD - Should return GBPUSD symbol info"""
        response = requests.get(f"{BASE_URL}/api/mt5/symbol/GBPUSD")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"GBPUSD Symbol Info: success={data.get('success')}")


class TestMT5OrderExecution:
    """Tests for MT5 order execution endpoint"""
    
    def test_mt5_execute_buy_order(self):
        """POST /api/mt5/order - Execute BUY order (simulated)"""
        # First connect
        requests.post(f"{BASE_URL}/api/mt5/connect", params={
            "login": 12345,
            "password": "test",
            "server": "Demo"
        })
        
        params = {
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume": 0.1
        }
        
        response = requests.post(f"{BASE_URL}/api/mt5/order", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        assert "trade" in data, "Response should have 'trade' field"
        
        # In simulation mode, orders should succeed
        assert data["success"] == True, f"Expected order success in simulation mode, got {data}"
        
        trade = data["trade"]
        assert "ticket" in trade, "Trade should have 'ticket'"
        assert "volume" in trade, "Trade should have 'volume'"
        assert trade["volume"] == 0.1, f"Expected volume 0.1, got {trade.get('volume')}"
        
        print(f"BUY Order: ticket={trade.get('ticket')}, price={trade.get('price')}")
    
    def test_mt5_execute_sell_order(self):
        """POST /api/mt5/order - Execute SELL order (simulated)"""
        params = {
            "symbol": "EURUSD",
            "direction": "SELL",
            "volume": 0.05
        }
        
        response = requests.post(f"{BASE_URL}/api/mt5/order", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True, f"Expected SELL order success, got {data}"
        
        trade = data["trade"]
        print(f"SELL Order: ticket={trade.get('ticket')}, price={trade.get('price')}")
    
    def test_mt5_execute_call_order(self):
        """POST /api/mt5/order - Execute CALL order (should map to BUY)"""
        params = {
            "symbol": "GBPUSD",
            "direction": "CALL",
            "volume": 0.1
        }
        
        response = requests.post(f"{BASE_URL}/api/mt5/order", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True, f"Expected CALL order success, got {data}"
        print(f"CALL (BUY) Order: ticket={data['trade'].get('ticket')}")
    
    def test_mt5_execute_put_order(self):
        """POST /api/mt5/order - Execute PUT order (should map to SELL)"""
        params = {
            "symbol": "GBPUSD",
            "direction": "PUT",
            "volume": 0.1
        }
        
        response = requests.post(f"{BASE_URL}/api/mt5/order", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True, f"Expected PUT order success, got {data}"
        print(f"PUT (SELL) Order: ticket={data['trade'].get('ticket')}")


class TestMT5SignalProcessing:
    """Tests for MT5 signal processing endpoint"""
    
    def test_mt5_process_signal_high_confidence(self):
        """POST /api/mt5/signal/process - Process high confidence signal"""
        params = {
            "symbol": "EURUSD",
            "direction": "BUY",
            "confidence": 85.0,
            "volume": 0.1,
            "strategy_name": "Test Strategy"
        }
        
        response = requests.post(f"{BASE_URL}/api/mt5/signal/process", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        assert "executed" in data, "Response should have 'executed' field"
        
        # With 85% confidence, signal should be executed
        assert data["success"] == True, f"Expected high confidence signal to succeed, got {data}"
        assert data["executed"] == True, f"Expected signal to be executed, got {data}"
        
        print(f"Signal Processed: success={data['success']}, executed={data['executed']}")
    
    def test_mt5_process_signal_low_confidence(self):
        """POST /api/mt5/signal/process - Low confidence signal should not execute"""
        params = {
            "symbol": "EURUSD",
            "direction": "SELL",
            "confidence": 50.0,  # Below minimum threshold of 65%
            "volume": 0.1
        }
        
        response = requests.post(f"{BASE_URL}/api/mt5/signal/process", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        assert "executed" in data, "Response should have 'executed' field"
        
        # Low confidence signals should not be executed
        assert data["executed"] == False, f"Low confidence signal should not execute, got {data}"
        assert "reason" in data, "Should include reason for not executing"
        
        print(f"Low Confidence Signal: executed={data['executed']}, reason={data.get('reason')}")
    
    def test_mt5_process_signal_boundary_confidence(self):
        """POST /api/mt5/signal/process - Boundary confidence (65%) should execute"""
        params = {
            "symbol": "USDJPY",
            "direction": "CALL",
            "confidence": 65.0,  # Exactly at minimum threshold
            "volume": 0.1
        }
        
        response = requests.post(f"{BASE_URL}/api/mt5/signal/process", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # At exactly 65%, signal should be executed
        assert data["executed"] == True, f"Boundary confidence signal should execute, got {data}"
        
        print(f"Boundary Signal (65%): executed={data['executed']}")


class TestMT5Positions:
    """Tests for MT5 positions endpoint"""
    
    def test_mt5_get_positions(self):
        """GET /api/mt5/positions - Should return open positions"""
        response = requests.get(f"{BASE_URL}/api/mt5/positions")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        assert "positions" in data, "Response should have 'positions' field"
        assert "count" in data, "Response should have 'count' field"
        assert "total_profit" in data, "Response should have 'total_profit' field"
        
        positions = data["positions"]
        assert isinstance(positions, list), "Positions should be a list"
        
        print(f"Positions: count={data['count']}, total_profit={data['total_profit']}")


class TestMT5TradeHistory:
    """Tests for MT5 trade history endpoint"""
    
    def test_mt5_trade_history(self):
        """GET /api/mt5/history - Should return trade history"""
        response = requests.get(f"{BASE_URL}/api/mt5/history")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "executed" in data, "Response should have 'executed' field"
        assert "failed" in data, "Response should have 'failed' field"
        assert "total_executed" in data, "Response should have 'total_executed' field"
        assert "total_failed" in data, "Response should have 'total_failed' field"
        
        print(f"Trade History: executed={data['total_executed']}, failed={data['total_failed']}")
    
    def test_mt5_trade_history_with_limit(self):
        """GET /api/mt5/history?limit=10 - Should respect limit parameter"""
        response = requests.get(f"{BASE_URL}/api/mt5/history", params={"limit": 10})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        executed = data.get("executed", [])
        assert len(executed) <= 10, f"Executed trades should be <= 10, got {len(executed)}"
        
        print(f"Trade History (limit=10): returned {len(executed)} executed trades")


class TestHighAccuracySignalGeneration:
    """Tests for high accuracy signal generation endpoint"""
    
    def test_high_accuracy_signal_generation(self):
        """POST /api/signals/high-accuracy/generate - Generate high accuracy signal"""
        json_data = {
            "symbol": "EURUSD",
            "expiry_seconds": 60,
            "strategy": "trend_confirmation_1m"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/signals/high-accuracy/generate",
            json=json_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        
        if data.get("success") and data.get("signal"):
            signal = data["signal"]
            print(f"High Accuracy Signal: direction={signal.get('direction')}, confidence={signal.get('confidence')}")
        else:
            print(f"Signal generation result: {data.get('message', 'No signal generated')}")


class TestAutoSignalGeneratorStatus:
    """Tests for auto signal generator status endpoint"""
    
    def test_auto_signal_generator_status(self):
        """GET /api/signals/auto/status - Check auto generator status"""
        response = requests.get(f"{BASE_URL}/api/signals/auto/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled" in data, "Response should have 'enabled' field"
        
        print(f"Auto Generator Status: enabled={data.get('enabled')}, interval={data.get('interval_seconds')}")


class TestPocketOptionRealtimeStatus:
    """Tests for Pocket Option realtime status endpoint"""
    
    def test_pocket_option_realtime_status(self):
        """GET /api/pocket-option/realtime/status - Check PO connection"""
        response = requests.get(f"{BASE_URL}/api/pocket-option/realtime/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "connected" in data, "Response should have 'connected' field"
        
        print(f"Pocket Option Status: connected={data.get('connected')}, source={data.get('source')}")


class TestMT5EndToEndFlow:
    """End-to-end flow tests for MT5 trading"""
    
    def test_complete_trading_flow(self):
        """Test complete MT5 trading flow: connect -> check account -> place order -> view history"""
        # Step 1: Connect to MT5
        connect_response = requests.post(f"{BASE_URL}/api/mt5/connect", params={
            "login": 12345,
            "password": "test",
            "server": "Demo"
        })
        assert connect_response.status_code == 200
        connect_data = connect_response.json()
        assert connect_data["success"] == True, "Step 1 (Connect) failed"
        print("Step 1: Connected to MT5")
        
        # Step 2: Check account info
        account_response = requests.get(f"{BASE_URL}/api/mt5/account")
        assert account_response.status_code == 200
        account_data = account_response.json()
        assert account_data["success"] == True, "Step 2 (Account) failed"
        print(f"Step 2: Account balance = {account_data['account'].get('balance')}")
        
        # Step 3: Get symbol info
        symbol_response = requests.get(f"{BASE_URL}/api/mt5/symbol/EURUSD")
        assert symbol_response.status_code == 200
        symbol_data = symbol_response.json()
        assert symbol_data["success"] == True, "Step 3 (Symbol) failed"
        print(f"Step 3: EURUSD bid/ask = {symbol_data['symbol_info'].get('bid')}/{symbol_data['symbol_info'].get('ask')}")
        
        # Step 4: Place an order
        order_response = requests.post(f"{BASE_URL}/api/mt5/order", params={
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume": 0.1
        })
        assert order_response.status_code == 200
        order_data = order_response.json()
        assert order_data["success"] == True, "Step 4 (Order) failed"
        ticket = order_data["trade"].get("ticket")
        print(f"Step 4: Order placed, ticket = {ticket}")
        
        # Step 5: Check positions
        positions_response = requests.get(f"{BASE_URL}/api/mt5/positions")
        assert positions_response.status_code == 200
        positions_data = positions_response.json()
        assert positions_data["success"] == True, "Step 5 (Positions) failed"
        print(f"Step 5: Open positions count = {positions_data.get('count')}")
        
        # Step 6: Check trade history
        history_response = requests.get(f"{BASE_URL}/api/mt5/history")
        assert history_response.status_code == 200
        history_data = history_response.json()
        print(f"Step 6: Total executed trades = {history_data.get('total_executed')}")
        
        print("\n✅ Complete MT5 trading flow test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
