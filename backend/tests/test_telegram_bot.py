"""
Telegram Bot Integration Tests
Tests all Telegram bot endpoints for iteration 29 bug fix verification
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pocket-option-ai-9.preview.emergentagent.com').rstrip('/')


class TestTelegramBotEndpoints:
    """Test Telegram Bot API endpoints"""
    
    def test_telegram_bot_status(self):
        """GET /api/telegram-bot/status - Returns bot status"""
        response = requests.get(f"{BASE_URL}/api/telegram-bot/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'status' in data
        
        status = data['status']
        assert 'is_running' in status
        assert 'auto_trading_enabled' in status
        assert 'demo_mode' in status
        assert 'trade_amount' in status
        assert 'bot_token_configured' in status
        assert status['bot_token_configured'] == True
        print(f"✅ Bot status: is_running={status['is_running']}, demo_mode={status['demo_mode']}")
    
    def test_telegram_bot_start(self):
        """POST /api/telegram-bot/start - Starts bot polling"""
        response = requests.post(f"{BASE_URL}/api/telegram-bot/start")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        # May return "Bot already running" if already started
        assert 'message' in data
        print(f"✅ Start response: {data['message']}")
    
    def test_telegram_bot_send_message(self):
        """POST /api/telegram-bot/send - Sends message to Telegram"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-bot/send",
            json={"message": "🧪 Pytest test message - iteration 29"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'message_id' in data
        print(f"✅ Message sent with ID: {data['message_id']}")
    
    def test_telegram_bot_settings_update(self):
        """PUT /api/telegram-bot/settings - Updates bot settings"""
        response = requests.put(
            f"{BASE_URL}/api/telegram-bot/settings",
            json={
                "auto_trading_enabled": False,
                "demo_mode": True,
                "trade_amount": 1.0
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'settings' in data
        
        settings = data['settings']
        assert settings['auto_trading_enabled'] == False
        assert settings['demo_mode'] == True
        assert settings['trade_amount'] == 1.0
        print(f"✅ Settings updated: {settings}")
    
    def test_telegram_bot_history(self):
        """GET /api/telegram-bot/history - Returns signal and trade history"""
        response = requests.get(f"{BASE_URL}/api/telegram-bot/history?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'signals' in data
        assert 'trades' in data
        assert isinstance(data['signals'], list)
        assert isinstance(data['trades'], list)
        print(f"✅ History: {len(data['signals'])} signals, {len(data['trades'])} trades")
    
    def test_telegram_bot_stats(self):
        """GET /api/telegram-bot/stats - Returns trading statistics"""
        response = requests.get(f"{BASE_URL}/api/telegram-bot/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'stats' in data
        
        stats = data['stats']
        assert 'total_signals' in stats
        assert 'total_trades' in stats
        assert 'wins' in stats
        assert 'losses' in stats
        assert 'win_rate' in stats
        print(f"✅ Stats: {stats['total_signals']} signals, {stats['win_rate']}% win rate")
    
    def test_telegram_bot_stop(self):
        """POST /api/telegram-bot/stop - Stops bot and SSID service"""
        response = requests.post(f"{BASE_URL}/api/telegram-bot/stop")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'telegram_stopped' in data
        assert data['telegram_stopped'] == True
        print(f"✅ Bot stopped: {data['message']}")


class TestTelegramNotifierEndpoints:
    """Test Telegram Notifier API endpoints"""
    
    def test_telegram_notifier_status(self):
        """GET /api/telegram/status - Returns notifier status"""
        response = requests.get(f"{BASE_URL}/api/telegram/status")
        assert response.status_code == 200
        
        data = response.json()
        assert 'enabled' in data
        assert 'configured' in data
        assert 'chat_id' in data
        assert data['configured'] == True
        print(f"✅ Notifier status: configured={data['configured']}, chat_id={data['chat_id']}")
    
    def test_telegram_notifier_test(self):
        """POST /api/telegram/test - Sends test notification"""
        response = requests.post(f"{BASE_URL}/api/telegram/test")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        print(f"✅ Test notification: {data['message']}")


class TestRegressionEndpoints:
    """Regression tests for existing functionality"""
    
    def test_iq720_ensemble(self):
        """POST /api/signals/iq720-ensemble - IQ-720 signal generation"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-ensemble",
            json={"symbol": "EURUSD", "timeframe": "1m"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # May return insufficient data if no candles available
        assert 'success' in data
        print(f"✅ IQ-720 response: success={data['success']}, message={data.get('message', 'N/A')}")
    
    def test_scan_markets(self):
        """GET /api/signals/scan-markets - Market scanning"""
        response = requests.get(f"{BASE_URL}/api/signals/scan-markets?assets=EURUSD_OTC,GBPUSD_OTC")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'scanned_assets' in data
        assert 'signals_found' in data
        print(f"✅ Scan markets: {data['scanned_assets']} assets scanned, {data['signals_found']} signals found")
    
    def test_health_endpoint(self):
        """GET /api/health - Health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('status') == 'healthy'
        print(f"✅ Health check: {data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
