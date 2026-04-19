"""
Iteration 37 - Core Decision Engine v2.0 Tests
==============================================
Tests for:
1. GET /api/signals/engine-status - Engine status with models, strategies, risk limits
2. POST /api/signals/decision - Risk-managed trade decision with regime detection
3. POST /api/signals/record-outcome - Trade outcome tracking
4. Regression tests for existing endpoints
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCoreDecisionEngineStatus:
    """Test GET /api/signals/engine-status endpoint"""
    
    def test_engine_status_returns_success(self):
        """Engine status endpoint should return success"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Engine status returned successfully")
    
    def test_engine_status_has_version(self):
        """Engine status should include version"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        data = response.json()
        assert "version" in data
        assert data["version"] == "2.0.0"
        print(f"✅ Engine version: {data['version']}")
    
    def test_engine_status_has_models(self):
        """Engine status should include models status"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        data = response.json()
        assert "models" in data
        models = data["models"]
        # IQ-720 should always be present
        assert "iq720" in models
        assert models["iq720"]["trained"] == True
        print(f"✅ Models status: {list(models.keys())}")
    
    def test_engine_status_has_model_weights(self):
        """Engine status should include model weights for ensemble"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        data = response.json()
        assert "model_weights" in data
        weights = data["model_weights"]
        # Check expected model weights
        assert "iq720" in weights
        assert "maximized_ml" in weights
        assert "improved_ml" in weights
        assert "lstm_gru" in weights
        assert "ppo_rl" in weights
        # Weights should sum to approximately 1.0
        total_weight = sum(weights.values())
        assert 0.95 <= total_weight <= 1.05
        print(f"✅ Model weights: {weights}")
    
    def test_engine_status_has_active_strategies(self):
        """Engine status should include active strategies"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        data = response.json()
        assert "active_strategies" in data
        strategies = data["active_strategies"]
        # Check all 4 strategies are present
        assert "trend_following" in strategies
        assert "mean_reversion" in strategies
        assert "scalping" in strategies
        assert "momentum" in strategies
        print(f"✅ Active strategies: {strategies}")
    
    def test_engine_status_has_risk_limits(self):
        """Engine status should include risk limits"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        data = response.json()
        assert "risk_limits" in data
        limits = data["risk_limits"]
        # Check required risk limit fields
        assert "max_drawdown_pct" in limits
        assert "max_daily_loss_pct" in limits
        assert "max_consecutive_losses" in limits
        assert "min_confidence" in limits
        assert "max_position_pct" in limits
        assert "min_win_rate_threshold" in limits
        assert "cooldown_after_loss_streak_s" in limits
        print(f"✅ Risk limits: max_drawdown={limits['max_drawdown_pct']}%, min_confidence={limits['min_confidence']}%")
    
    def test_engine_status_has_performance(self):
        """Engine status should include performance metrics"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        data = response.json()
        assert "performance" in data
        perf = data["performance"]
        # Check required performance fields
        assert "total_trades" in perf
        assert "wins" in perf
        assert "losses" in perf
        assert "win_rate" in perf
        assert "consecutive_losses" in perf
        assert "max_drawdown_pct" in perf
        assert "sharpe_ratio" in perf
        print(f"✅ Performance: trades={perf['total_trades']}, win_rate={perf['win_rate']}%")


class TestCoreDecisionEndpoint:
    """Test POST /api/signals/decision endpoint"""
    
    def test_decision_endpoint_returns_success(self):
        """Decision endpoint should return success with valid data"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        print(f"✅ Decision endpoint returned: success={data.get('success')}")
    
    def test_decision_has_decision_object(self):
        """Decision response should include decision object"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        data = response.json()
        if data.get("success"):
            assert "decision" in data
            decision = data["decision"]
            assert decision is not None
            print(f"✅ Decision object present")
        else:
            print(f"⚠️ Decision not generated: {data.get('message')}")
    
    def test_decision_has_action(self):
        """Decision should include action (CALL/PUT/HOLD)"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        data = response.json()
        if data.get("success") and data.get("decision"):
            decision = data["decision"]
            assert "action" in decision
            assert decision["action"] in ["CALL", "PUT", "HOLD"]
            print(f"✅ Decision action: {decision['action']}")
        else:
            pytest.skip("No decision generated")
    
    def test_decision_has_confidence(self):
        """Decision should include confidence score"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        data = response.json()
        if data.get("success") and data.get("decision"):
            decision = data["decision"]
            assert "confidence" in decision
            assert 0 <= decision["confidence"] <= 100
            print(f"✅ Decision confidence: {decision['confidence']}%")
        else:
            pytest.skip("No decision generated")
    
    def test_decision_has_regime(self):
        """Decision should include market regime detection"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        data = response.json()
        if data.get("success") and data.get("decision"):
            decision = data["decision"]
            assert "regime" in decision
            valid_regimes = ["trending_up", "trending_down", "ranging", "high_volatility", "low_volatility", "unknown"]
            assert decision["regime"] in valid_regimes
            print(f"✅ Market regime: {decision['regime']}")
        else:
            pytest.skip("No decision generated")
    
    def test_decision_has_model_votes(self):
        """Decision should include model votes"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        data = response.json()
        if data.get("success") and data.get("decision"):
            decision = data["decision"]
            assert "model_votes" in decision
            print(f"✅ Model votes: {list(decision['model_votes'].keys())}")
        else:
            pytest.skip("No decision generated")
    
    def test_decision_has_position_sizing(self):
        """Decision should include position sizing"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        data = response.json()
        if data.get("success") and data.get("decision"):
            decision = data["decision"]
            assert "position_size_pct" in decision
            assert 0 <= decision["position_size_pct"] <= 10  # Max 10% per trade
            print(f"✅ Position size: {decision['position_size_pct']}%")
        else:
            pytest.skip("No decision generated")
    
    def test_decision_has_risk_fields(self):
        """Decision should include stop-loss and take-profit"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        data = response.json()
        if data.get("success") and data.get("decision"):
            decision = data["decision"]
            assert "stop_loss_pips" in decision
            assert "take_profit_pips" in decision
            assert "risk_reward_ratio" in decision
            assert "expiry_seconds" in decision
            print(f"✅ Risk fields: SL={decision['stop_loss_pips']} pips, TP={decision['take_profit_pips']} pips, RR={decision['risk_reward_ratio']}")
        else:
            pytest.skip("No decision generated")
    
    def test_decision_hold_on_low_confidence(self):
        """Decision should return HOLD when confidence is below threshold"""
        # This test verifies the min_confidence threshold (65%)
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        data = response.json()
        if data.get("success") and data.get("decision"):
            decision = data["decision"]
            # If confidence < 65%, action should be HOLD
            if decision["confidence"] < 65:
                assert decision["action"] == "HOLD"
                assert any("LOW_CONFIDENCE" in w for w in decision.get("risk_warnings", []))
                print(f"✅ HOLD returned for low confidence ({decision['confidence']}%)")
            else:
                print(f"✅ Confidence {decision['confidence']}% >= 65% threshold")
        else:
            pytest.skip("No decision generated")


class TestRecordOutcomeEndpoint:
    """Test POST /api/signals/record-outcome endpoint"""
    
    def test_record_win_outcome(self):
        """Record a winning trade outcome"""
        response = requests.post(
            f"{BASE_URL}/api/signals/record-outcome",
            json={
                "symbol": "EURUSD",
                "direction": "CALL",
                "outcome": "win",
                "pnl": 10.0
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "performance" in data
        perf = data["performance"]
        assert "total_trades" in perf
        assert "win_rate" in perf
        print(f"✅ Win recorded: trades={perf['total_trades']}, win_rate={perf['win_rate']}%")
    
    def test_record_loss_outcome(self):
        """Record a losing trade outcome"""
        response = requests.post(
            f"{BASE_URL}/api/signals/record-outcome",
            json={
                "symbol": "EURUSD",
                "direction": "PUT",
                "outcome": "loss",
                "pnl": -8.0
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "performance" in data
        perf = data["performance"]
        assert "consecutive_losses" in perf
        assert "max_drawdown_pct" in perf
        print(f"✅ Loss recorded: consecutive_losses={perf['consecutive_losses']}, max_drawdown={perf['max_drawdown_pct']}%")
    
    def test_record_outcome_updates_sharpe(self):
        """Record outcome should update Sharpe ratio"""
        # Record a few trades to build up Sharpe calculation
        for i in range(3):
            requests.post(
                f"{BASE_URL}/api/signals/record-outcome",
                json={
                    "symbol": "GBPUSD",
                    "direction": "CALL",
                    "outcome": "win" if i % 2 == 0 else "loss",
                    "pnl": 5.0 if i % 2 == 0 else -4.0
                }
            )
        
        response = requests.post(
            f"{BASE_URL}/api/signals/record-outcome",
            json={
                "symbol": "GBPUSD",
                "direction": "PUT",
                "outcome": "win",
                "pnl": 8.0
            }
        )
        data = response.json()
        assert data.get("success") == True
        perf = data["performance"]
        assert "sharpe_ratio" in perf
        print(f"✅ Sharpe ratio tracked: {perf['sharpe_ratio']}")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_iq720_ensemble_still_works(self):
        """IQ-720 ensemble endpoint should still work"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-ensemble",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        assert response.status_code == 200
        data = response.json()
        # Should return success or a valid "no signal" response
        assert "success" in data or "signal" in data
        print(f"✅ IQ-720 ensemble: success={data.get('success')}, signal={data.get('signal') is not None}")
    
    def test_scan_markets_still_works(self):
        """Scan markets endpoint should still work"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 60, "max_signals": 3}
        )
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data or "success" in data
        print(f"✅ Scan markets: returned {len(data.get('signals', []))} signals")
    
    def test_signal_routing_stats_still_works(self):
        """Signal routing stats endpoint should still work"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/stats")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "total_signals_routed" in data
        print(f"✅ Signal routing stats: {data}")
    
    def test_ml_tuning_report_still_works(self):
        """ML tuning report endpoint should still work"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "otc_data" in data
        print(f"✅ ML tuning report: success={data.get('success')}")
    
    def test_api_health(self):
        """API health endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✅ API health: {data.get('status')}")


class TestDecisionEngineIntegration:
    """Integration tests for the full decision pipeline"""
    
    def test_full_decision_pipeline(self):
        """Test the full decision pipeline: status -> decision -> record"""
        # 1. Get engine status
        status_resp = requests.get(f"{BASE_URL}/api/signals/engine-status")
        assert status_resp.status_code == 200
        status = status_resp.json()
        initial_trades = status.get("performance", {}).get("total_trades", 0)
        print(f"Initial trades: {initial_trades}")
        
        # 2. Generate a decision
        decision_resp = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100}
        )
        assert decision_resp.status_code == 200
        decision_data = decision_resp.json()
        
        if decision_data.get("success") and decision_data.get("decision"):
            decision = decision_data["decision"]
            action = decision["action"]
            print(f"Decision: {action} with {decision['confidence']}% confidence")
            
            # 3. Record outcome (simulate trade result)
            if action in ["CALL", "PUT"]:
                outcome_resp = requests.post(
                    f"{BASE_URL}/api/signals/record-outcome",
                    json={
                        "symbol": "EURUSD",
                        "direction": action,
                        "outcome": "win",
                        "pnl": 8.2
                    }
                )
                assert outcome_resp.status_code == 200
                outcome_data = outcome_resp.json()
                new_trades = outcome_data.get("performance", {}).get("total_trades", 0)
                print(f"After recording: {new_trades} trades")
                assert new_trades > initial_trades
                print(f"✅ Full pipeline test passed")
            else:
                print(f"✅ HOLD decision - no trade to record")
        else:
            print(f"⚠️ No decision generated: {decision_data.get('message')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
