"""
MT5 and TradingView Integration Tests
=====================================
Tests for MetaTrader 5 and TradingView webhook integration endpoints.
MT5 runs in simulation mode (no native MetaTrader5 package on Linux).
TradingView webhooks are real but route to internal signal queue.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMT5Status:
    """MT5 connection status endpoint tests"""
    
    def test_mt5_status_returns_success(self):
        """GET /api/mt5/status - Returns MT5 connection status"""
        response = requests.get(f"{BASE_URL}/api/mt5/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "status" in data
        assert "connected" in data["status"]
        assert "mt5_available" in data["status"]
        print(f"MT5 Status: connected={data['status']['connected']}, mt5_available={data['status']['mt5_available']}")


class TestMT5Connect:
    """MT5 connection endpoint tests"""
    
    def test_mt5_connect_with_credentials(self):
        """POST /api/mt5/connect - Connects to MT5 with credentials"""
        params = {
            "login": 12345678,
            "password": "test",
            "server": "MetaQuotes-Demo"
        }
        response = requests.post(f"{BASE_URL}/api/mt5/connect", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "status" in data
        assert data["status"]["connected"] == True
        assert data["status"]["server"] == "MetaQuotes-Demo"
        assert data["status"]["login"] == 12345678
        print(f"MT5 Connected: server={data['status']['server']}, login={data['status']['login']}")
    
    def test_mt5_connect_without_credentials(self):
        """POST /api/mt5/connect - Connects using env credentials"""
        response = requests.post(f"{BASE_URL}/api/mt5/connect")
        assert response.status_code == 200
        
        data = response.json()
        # Should still succeed in simulation mode
        assert "status" in data


class TestMT5Account:
    """MT5 account info endpoint tests"""
    
    def test_mt5_account_info(self):
        """GET /api/mt5/account - Returns account info"""
        # First ensure connected
        requests.post(f"{BASE_URL}/api/mt5/connect", params={
            "login": 12345678,
            "password": "test",
            "server": "MetaQuotes-Demo"
        })
        
        response = requests.get(f"{BASE_URL}/api/mt5/account")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "account" in data
        
        account = data["account"]
        assert "balance" in account
        assert "equity" in account
        assert "profit" in account
        assert "leverage" in account
        assert account["balance"] == 10000.0  # Simulated balance
        assert account["leverage"] == 100
        print(f"MT5 Account: balance=${account['balance']}, equity=${account['equity']}, leverage=1:{account['leverage']}")


class TestMT5Symbol:
    """MT5 symbol info endpoint tests"""
    
    def test_mt5_symbol_eurusd(self):
        """GET /api/mt5/symbol/EURUSD - Returns symbol info"""
        response = requests.get(f"{BASE_URL}/api/mt5/symbol/EURUSD")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "symbol_info" in data
        
        info = data["symbol_info"]
        assert info["symbol"] == "EURUSD"
        assert "bid" in info
        assert "ask" in info
        assert "spread" in info
        assert "min_volume" in info
        assert "max_volume" in info
        print(f"EURUSD: bid={info['bid']}, ask={info['ask']}, spread={info['spread']}")
    
    def test_mt5_symbol_gbpusd(self):
        """GET /api/mt5/symbol/GBPUSD - Returns symbol info"""
        response = requests.get(f"{BASE_URL}/api/mt5/symbol/GBPUSD")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True


class TestMT5Order:
    """MT5 order execution endpoint tests"""
    
    def test_mt5_order_buy(self):
        """POST /api/mt5/order - Executes BUY order"""
        params = {
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume": 0.1
        }
        response = requests.post(f"{BASE_URL}/api/mt5/order", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "trade" in data
        
        trade = data["trade"]
        assert trade["success"] == True
        assert trade["ticket"] > 0
        assert trade["volume"] == 0.1
        print(f"BUY Order: ticket={trade['ticket']}, volume={trade['volume']}, price={trade['price']}")
    
    def test_mt5_order_sell(self):
        """POST /api/mt5/order - Executes SELL order"""
        params = {
            "symbol": "EURUSD",
            "direction": "SELL",
            "volume": 0.05
        }
        response = requests.post(f"{BASE_URL}/api/mt5/order", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["trade"]["success"] == True
        print(f"SELL Order: ticket={data['trade']['ticket']}")
    
    def test_mt5_order_call_direction(self):
        """POST /api/mt5/order - CALL direction maps to BUY"""
        params = {
            "symbol": "EURUSD",
            "direction": "CALL",
            "volume": 0.01
        }
        response = requests.post(f"{BASE_URL}/api/mt5/order", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
    
    def test_mt5_order_put_direction(self):
        """POST /api/mt5/order - PUT direction maps to SELL"""
        params = {
            "symbol": "EURUSD",
            "direction": "PUT",
            "volume": 0.01
        }
        response = requests.post(f"{BASE_URL}/api/mt5/order", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True


class TestMT5Disconnect:
    """MT5 disconnect endpoint tests"""
    
    def test_mt5_disconnect(self):
        """POST /api/mt5/disconnect - Disconnects MT5"""
        response = requests.post(f"{BASE_URL}/api/mt5/disconnect")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["message"] == "Disconnected from MT5"
        print("MT5 Disconnected successfully")


class TestTradingViewWebhook:
    """TradingView webhook endpoint tests"""
    
    def test_tv_webhook_buy_signal(self):
        """POST /api/tradingview/webhook - Receives BUY alert"""
        payload = {
            "action": "buy",
            "symbol": "EURUSD",
            "price": 1.0850,
            "destination": "pocket_option",
            "passphrase": "gpt-signal"
        }
        response = requests.post(f"{BASE_URL}/api/tradingview/webhook", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "alert" in data
        
        alert = data["alert"]
        assert alert["action"] == "buy"
        assert "EURUSD" in alert["symbol"]
        assert alert["is_valid"] == True
        assert alert["execution_status"] == "executed"
        print(f"TV Webhook BUY: alert_id={alert['alert_id']}, symbol={alert['symbol']}")
    
    def test_tv_webhook_sell_signal(self):
        """POST /api/tradingview/webhook - Receives SELL alert"""
        payload = {
            "action": "sell",
            "symbol": "GBPUSD",
            "price": 1.2500,
            "destination": "pocket_option",
            "passphrase": "gpt-signal"
        }
        response = requests.post(f"{BASE_URL}/api/tradingview/webhook", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["alert"]["action"] == "sell"
    
    def test_tv_webhook_call_signal(self):
        """POST /api/tradingview/webhook - Receives CALL alert (binary options)"""
        payload = {
            "action": "call",
            "symbol": "EURUSD",
            "destination": "pocket_option",
            "passphrase": "gpt-signal"
        }
        response = requests.post(f"{BASE_URL}/api/tradingview/webhook", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["alert"]["action"] == "call"
    
    def test_tv_webhook_put_signal(self):
        """POST /api/tradingview/webhook - Receives PUT alert (binary options)"""
        payload = {
            "action": "put",
            "symbol": "USDJPY",
            "destination": "pocket_option",
            "passphrase": "gpt-signal"
        }
        response = requests.post(f"{BASE_URL}/api/tradingview/webhook", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["alert"]["action"] == "put"
    
    def test_tv_webhook_without_price(self):
        """POST /api/tradingview/webhook - Works without price field"""
        payload = {
            "action": "buy",
            "symbol": "EURUSD",
            "destination": "pocket_option",
            "passphrase": "gpt-signal"
        }
        response = requests.post(f"{BASE_URL}/api/tradingview/webhook", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["alert"]["price"] == 0.0  # Default when not provided
    
    def test_tv_webhook_with_sl_tp(self):
        """POST /api/tradingview/webhook - Accepts stop_loss and take_profit"""
        payload = {
            "action": "buy",
            "symbol": "EURUSD",
            "price": 1.0850,
            "stop_loss": 1.0800,
            "take_profit": 1.0900,
            "destination": "pocket_option",
            "passphrase": "gpt-signal"
        }
        response = requests.post(f"{BASE_URL}/api/tradingview/webhook", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["alert"]["stop_loss"] == 1.0800
        assert data["alert"]["take_profit"] == 1.0900


class TestTradingViewStats:
    """TradingView stats endpoint tests"""
    
    def test_tv_stats(self):
        """GET /api/tradingview/stats - Returns alert statistics"""
        response = requests.get(f"{BASE_URL}/api/tradingview/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "stats" in data
        
        stats = data["stats"]
        assert "total_alerts" in stats
        assert "valid_alerts" in stats
        assert "executed_alerts" in stats
        assert "by_action" in stats
        assert "by_destination" in stats
        assert "by_symbol" in stats
        print(f"TV Stats: total={stats['total_alerts']}, valid={stats['valid_alerts']}, executed={stats['executed_alerts']}")


class TestTradingViewHistory:
    """TradingView history endpoint tests"""
    
    def test_tv_history(self):
        """GET /api/tradingview/history - Returns recent alert history"""
        response = requests.get(f"{BASE_URL}/api/tradingview/history?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        if len(data["alerts"]) > 0:
            alert = data["alerts"][0]
            assert "alert_id" in alert
            assert "action" in alert
            assert "symbol" in alert
            assert "timestamp" in alert
            print(f"TV History: {len(data['alerts'])} alerts found")


class TestTradingViewSetup:
    """TradingView setup instructions endpoint tests"""
    
    def test_tv_setup(self):
        """GET /api/tradingview/setup - Returns webhook setup instructions"""
        response = requests.get(f"{BASE_URL}/api/tradingview/setup")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "instructions" in data
        
        instructions = data["instructions"]
        assert "webhook_url" in instructions
        assert "method" in instructions
        assert "required_fields" in instructions
        assert "optional_fields" in instructions
        assert "example_message" in instructions
        assert "pine_script_template" in instructions
        assert "notes" in instructions
        print(f"TV Setup: webhook_url={instructions['webhook_url']}")


class TestTradingViewPineScript:
    """TradingView Pine Script template endpoint tests"""
    
    def test_tv_pine_script(self):
        """GET /api/tradingview/pine-script - Returns Pine Script template"""
        response = requests.get(f"{BASE_URL}/api/tradingview/pine-script")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "template" in data
        assert "Pine Script" in data["template"]
        assert "alertMessage" in data["template"]
        print("TV Pine Script template retrieved successfully")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_health_endpoint(self):
        """GET /api/health - Health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_telegram_bot_status(self):
        """GET /api/telegram-bot/status - Telegram bot status"""
        response = requests.get(f"{BASE_URL}/api/telegram-bot/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "status" in data
    
    def test_iq720_ensemble(self):
        """POST /api/signals/iq720-ensemble - IQ-720 signal generation"""
        payload = {
            "symbol": "EURUSD_otc",
            "timeframe": "1m"
        }
        response = requests.post(f"{BASE_URL}/api/signals/iq720-ensemble", json=payload)
        # May return 200 with signal or "conditions not met"
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
