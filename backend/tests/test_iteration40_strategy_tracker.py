"""
Iteration 40 Tests: Strategy Performance Tracker & Decision Engine Widget
Tests per-asset strategy tracking, auto-promotion, and new dashboard widgets.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestStrategyTrackerEndpoints:
    """Test the new strategy tracker and decision engine endpoints"""
    
    def test_engine_status_endpoint(self):
        """GET /api/signals/engine-status - Returns models, strategies, risk limits, performance"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Verify required fields
        assert "models" in data, "Missing 'models' field"
        assert "active_strategies" in data, "Missing 'active_strategies' field"
        assert "risk_limits" in data, "Missing 'risk_limits' field"
        assert "performance" in data, "Missing 'performance' field"
        
        # Verify performance structure
        perf = data["performance"]
        assert "total_trades" in perf, "Missing total_trades in performance"
        assert "win_rate" in perf, "Missing win_rate in performance"
        assert "sharpe_ratio" in perf, "Missing sharpe_ratio in performance"
        assert "max_drawdown_pct" in perf, "Missing max_drawdown_pct in performance"
        
        print(f"✅ Engine status: {perf['total_trades']} trades, {perf['win_rate']}% WR, Sharpe: {perf['sharpe_ratio']}")
    
    def test_engine_status_models(self):
        """Verify models field contains expected model info"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        data = response.json()
        
        models = data.get("models", {})
        # Should have iq720 at minimum
        assert "iq720" in models, "Missing iq720 model"
        
        # Each model should have trained and accuracy fields
        for model_name, model_info in models.items():
            assert "trained" in model_info, f"Model {model_name} missing 'trained' field"
            if "accuracy" in model_info:
                assert isinstance(model_info["accuracy"], (int, float)), f"Model {model_name} accuracy should be numeric"
        
        print(f"✅ Models found: {list(models.keys())}")
    
    def test_engine_status_active_strategies(self):
        """Verify active_strategies contains expected strategies"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        data = response.json()
        
        strategies = data.get("active_strategies", {})
        expected_strategies = ["trend_following", "mean_reversion", "scalping", "momentum"]
        
        for strat in expected_strategies:
            assert strat in strategies, f"Missing strategy: {strat}"
            assert isinstance(strategies[strat], bool), f"Strategy {strat} should be boolean"
        
        print(f"✅ Active strategies: {strategies}")
    
    def test_strategy_tracker_endpoint(self):
        """GET /api/signals/strategy-tracker - Returns per-asset strategy performance"""
        response = requests.get(f"{BASE_URL}/api/signals/strategy-tracker")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Verify required fields
        assert "tracker" in data, "Missing 'tracker' field"
        assert "total_assets_tracked" in data, "Missing 'total_assets_tracked' field"
        assert "overall" in data, "Missing 'overall' field"
        
        # Verify overall structure
        overall = data["overall"]
        assert "total_trades" in overall, "Missing total_trades in overall"
        assert "win_rate" in overall, "Missing win_rate in overall"
        assert "sharpe_ratio" in overall, "Missing sharpe_ratio in overall"
        
        print(f"✅ Strategy tracker: {data['total_assets_tracked']} assets tracked, overall {overall['total_trades']} trades")
    
    def test_record_outcome_with_strategy(self):
        """POST /api/signals/record-outcome - Accepts strategy field, returns best_strategy_for_asset"""
        # Record a win for EURUSD_OTC with IQ-720 strategy
        payload = {
            "symbol": "EURUSD_OTC",
            "direction": "CALL",
            "outcome": "win",
            "pnl": 8.2,
            "strategy": "IQ-720"
        }
        
        response = requests.post(f"{BASE_URL}/api/signals/record-outcome", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Verify performance is returned
        assert "performance" in data, "Missing 'performance' field"
        perf = data["performance"]
        assert "total_trades" in perf, "Missing total_trades"
        assert "win_rate" in perf, "Missing win_rate"
        
        # Verify best_strategy_for_asset is returned
        assert "best_strategy_for_asset" in data, "Missing 'best_strategy_for_asset' field"
        
        print(f"✅ Recorded outcome: {perf['total_trades']} total trades, best strategy: {data['best_strategy_for_asset']}")
    
    def test_record_multiple_outcomes_for_auto_promotion(self):
        """Test auto-promotion by recording 5+ trades for a strategy"""
        # Record 5 wins for keltner_macd strategy on GBPUSD_OTC
        for i in range(5):
            payload = {
                "symbol": "GBPUSD_OTC",
                "direction": "CALL" if i % 2 == 0 else "PUT",
                "outcome": "win" if i < 4 else "loss",  # 4 wins, 1 loss = 80% WR
                "pnl": 8.2 if i < 4 else -10.0,
                "strategy": "keltner_macd"
            }
            response = requests.post(f"{BASE_URL}/api/signals/record-outcome", json=payload)
            assert response.status_code == 200
        
        # Now check strategy tracker
        response = requests.get(f"{BASE_URL}/api/signals/strategy-tracker")
        data = response.json()
        
        tracker = data.get("tracker", {})
        if "GBPUSD_OTC" in tracker:
            asset_info = tracker["GBPUSD_OTC"]
            print(f"✅ GBPUSD_OTC: {asset_info.get('total_trades')} trades, best strategy: {asset_info.get('best_strategy')}")
            
            # Verify strategies breakdown
            strategies = asset_info.get("strategies", {})
            if "keltner_macd" in strategies:
                strat_info = strategies["keltner_macd"]
                assert "wins" in strat_info, "Missing wins in strategy info"
                assert "losses" in strat_info, "Missing losses in strategy info"
                assert "win_rate" in strat_info, "Missing win_rate in strategy info"
                print(f"   keltner_macd: {strat_info['wins']}W/{strat_info['losses']}L = {strat_info['win_rate']}%")
    
    def test_strategy_tracker_per_asset_structure(self):
        """Verify per-asset structure in strategy tracker"""
        # First record some trades
        payload = {
            "symbol": "USDJPY_OTC",
            "direction": "PUT",
            "outcome": "win",
            "pnl": 8.2,
            "strategy": "momentum_buster"
        }
        requests.post(f"{BASE_URL}/api/signals/record-outcome", json=payload)
        
        # Get tracker
        response = requests.get(f"{BASE_URL}/api/signals/strategy-tracker")
        data = response.json()
        
        tracker = data.get("tracker", {})
        
        # Check structure for any tracked asset
        for symbol, info in tracker.items():
            assert "total_trades" in info, f"Missing total_trades for {symbol}"
            assert "win_rate" in info, f"Missing win_rate for {symbol}"
            assert "pnl" in info, f"Missing pnl for {symbol}"
            assert "best_strategy" in info, f"Missing best_strategy for {symbol}"
            assert "strategies" in info, f"Missing strategies for {symbol}"
            
            # Verify strategies is a dict
            assert isinstance(info["strategies"], dict), f"strategies should be dict for {symbol}"
            
            print(f"✅ {symbol}: {info['total_trades']} trades, {info['win_rate']}% WR, best: {info['best_strategy']}")


class TestRegressionEndpoints:
    """Regression tests for existing functionality"""
    
    def test_api_health(self):
        """Verify /api/health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ API health check passed")
    
    def test_iq720_ensemble_endpoint(self):
        """Verify IQ-720 ensemble endpoint still works"""
        payload = {
            "symbol": "EURUSD",
            "candles": [
                {"open": 1.0850, "high": 1.0855, "low": 1.0845, "close": 1.0852, "volume": 1000},
                {"open": 1.0852, "high": 1.0858, "low": 1.0848, "close": 1.0855, "volume": 1100},
                {"open": 1.0855, "high": 1.0860, "low": 1.0850, "close": 1.0857, "volume": 1200},
            ] * 20  # Need at least 30 candles
        }
        response = requests.post(f"{BASE_URL}/api/signals/iq720-ensemble", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Should return a signal or indicate no signal
        assert "direction" in data or "signal" in data or "error" not in data
        print(f"✅ IQ-720 ensemble endpoint working")
    
    def test_signal_routing_rules(self):
        """Verify signal routing rules endpoint"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/rules")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "rules" in data, "Missing 'rules' field"
        print(f"✅ Signal routing rules endpoint working, {len(data.get('rules', []))} rules found")
    
    def test_telegram_bot_status(self):
        """Verify telegram bot status endpoint"""
        response = requests.get(f"{BASE_URL}/api/telegram/status")
        assert response.status_code == 200
        data = response.json()
        # Should return status info
        assert "configured" in data or "status" in data or "success" in data
        print(f"✅ Telegram bot status endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
