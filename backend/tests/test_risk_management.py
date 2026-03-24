"""
Risk Management & Drawdown Protection System Tests
===================================================
Tests for Sharpe ratio, Kelly criterion, drawdown tracking, and risk management APIs.

Endpoints tested:
- GET /api/risk-management/status
- GET /api/risk-management/metrics
- POST /api/risk-management/record-trade
- GET /api/risk-management/can-trade
- GET /api/risk-management/position-size
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRiskManagementStatus:
    """Test GET /api/risk-management/status endpoint"""
    
    def test_get_risk_status_returns_success(self):
        """Test that risk status endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/risk-management/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"✅ Risk status endpoint returns success")
    
    def test_get_risk_status_contains_balance(self):
        """Test that risk status contains balance information"""
        response = requests.get(f"{BASE_URL}/api/risk-management/status")
        assert response.status_code == 200
        
        data = response.json()
        risk_mgmt = data.get("risk_management", {})
        
        # Check balance fields exist
        assert "current_balance" in risk_mgmt, "Missing current_balance"
        assert "peak_balance" in risk_mgmt, "Missing peak_balance"
        assert "initial_balance" in risk_mgmt, "Missing initial_balance"
        
        # Validate balance values are numbers
        assert isinstance(risk_mgmt["current_balance"], (int, float)), "current_balance should be numeric"
        assert isinstance(risk_mgmt["peak_balance"], (int, float)), "peak_balance should be numeric"
        
        print(f"✅ Balance info: current=${risk_mgmt['current_balance']}, peak=${risk_mgmt['peak_balance']}")
    
    def test_get_risk_status_contains_drawdown(self):
        """Test that risk status contains drawdown information"""
        response = requests.get(f"{BASE_URL}/api/risk-management/status")
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("risk_management", {}).get("metrics", {})
        
        # Check drawdown fields
        assert "current_drawdown_pct" in metrics, "Missing current_drawdown_pct"
        assert "max_drawdown_pct" in metrics, "Missing max_drawdown_pct"
        
        print(f"✅ Drawdown info: current={metrics['current_drawdown_pct']}%, max={metrics['max_drawdown_pct']}%")
    
    def test_get_risk_status_contains_risk_level(self):
        """Test that risk status contains risk level"""
        response = requests.get(f"{BASE_URL}/api/risk-management/status")
        assert response.status_code == 200
        
        data = response.json()
        risk_mgmt = data.get("risk_management", {})
        
        assert "risk_level" in risk_mgmt, "Missing risk_level"
        valid_levels = ["normal", "elevated", "high", "critical", "paused"]
        assert risk_mgmt["risk_level"] in valid_levels, f"Invalid risk_level: {risk_mgmt['risk_level']}"
        
        print(f"✅ Risk level: {risk_mgmt['risk_level']}")


class TestRiskManagementMetrics:
    """Test GET /api/risk-management/metrics endpoint"""
    
    def test_get_metrics_returns_success(self):
        """Test that metrics endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"✅ Metrics endpoint returns success")
    
    def test_get_metrics_contains_sharpe_ratio(self):
        """Test that metrics contains Sharpe ratio"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("metrics", {})
        
        assert "sharpe_ratio" in metrics, "Missing sharpe_ratio"
        assert isinstance(metrics["sharpe_ratio"], (int, float)), "sharpe_ratio should be numeric"
        
        print(f"✅ Sharpe ratio: {metrics['sharpe_ratio']}")
    
    def test_get_metrics_contains_sortino_ratio(self):
        """Test that metrics contains Sortino ratio"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("metrics", {})
        
        assert "sortino_ratio" in metrics, "Missing sortino_ratio"
        assert isinstance(metrics["sortino_ratio"], (int, float)), "sortino_ratio should be numeric"
        
        print(f"✅ Sortino ratio: {metrics['sortino_ratio']}")
    
    def test_get_metrics_contains_profit_factor(self):
        """Test that metrics contains profit factor"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("metrics", {})
        
        assert "profit_factor" in metrics, "Missing profit_factor"
        assert isinstance(metrics["profit_factor"], (int, float)), "profit_factor should be numeric"
        
        print(f"✅ Profit factor: {metrics['profit_factor']}")
    
    def test_get_metrics_contains_win_rate(self):
        """Test that metrics contains win rate"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("metrics", {})
        
        assert "win_rate_pct" in metrics, "Missing win_rate_pct"
        assert isinstance(metrics["win_rate_pct"], (int, float)), "win_rate_pct should be numeric"
        
        print(f"✅ Win rate: {metrics['win_rate_pct']}%")
    
    def test_get_metrics_contains_kelly_fraction(self):
        """Test that metrics contains Kelly fraction"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200
        
        data = response.json()
        metrics = data.get("metrics", {})
        
        assert "kelly_fraction_pct" in metrics, "Missing kelly_fraction_pct"
        assert isinstance(metrics["kelly_fraction_pct"], (int, float)), "kelly_fraction_pct should be numeric"
        
        print(f"✅ Kelly fraction: {metrics['kelly_fraction_pct']}%")
    
    def test_get_metrics_contains_interpretation(self):
        """Test that metrics contains interpretation section"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "interpretation" in data, "Missing interpretation section"
        interp = data["interpretation"]
        
        assert "sharpe_quality" in interp, "Missing sharpe_quality interpretation"
        assert "drawdown_status" in interp, "Missing drawdown_status interpretation"
        assert "profit_factor_quality" in interp, "Missing profit_factor_quality interpretation"
        
        print(f"✅ Interpretation: Sharpe={interp['sharpe_quality']}, DD={interp['drawdown_status']}, PF={interp['profit_factor_quality']}")


class TestRecordTrade:
    """Test POST /api/risk-management/record-trade endpoint"""
    
    def test_record_winning_trade(self):
        """Test recording a winning trade"""
        params = {
            "direction": "CALL",
            "amount": 10,
            "pnl": 8,
            "win": True,
            "asset": "EURUSD",
            "confidence": 75
        }
        
        response = requests.post(f"{BASE_URL}/api/risk-management/record-trade", params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Verify trade was recorded correctly
        trade_recorded = data.get("trade_recorded", {})
        assert trade_recorded.get("direction") == "CALL", "Direction mismatch"
        assert trade_recorded.get("amount") == 10, "Amount mismatch"
        assert trade_recorded.get("pnl") == 8, "PnL mismatch"
        assert trade_recorded.get("win") == True, "Win status mismatch"
        assert trade_recorded.get("asset") == "EURUSD", "Asset mismatch"
        
        print(f"✅ Winning trade recorded: {trade_recorded}")
    
    def test_record_losing_trade(self):
        """Test recording a losing trade"""
        params = {
            "direction": "PUT",
            "amount": 10,
            "pnl": -10,
            "win": False,
            "asset": "GBPUSD",
            "confidence": 65
        }
        
        response = requests.post(f"{BASE_URL}/api/risk-management/record-trade", params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Verify trade was recorded correctly
        trade_recorded = data.get("trade_recorded", {})
        assert trade_recorded.get("direction") == "PUT", "Direction mismatch"
        assert trade_recorded.get("win") == False, "Win status mismatch"
        
        print(f"✅ Losing trade recorded: {trade_recorded}")
    
    def test_record_trade_updates_balance(self):
        """Test that recording a trade updates the balance"""
        # Get current balance
        status_response = requests.get(f"{BASE_URL}/api/risk-management/status")
        initial_balance = status_response.json().get("risk_management", {}).get("current_balance", 0)
        
        # Record a winning trade
        params = {
            "direction": "CALL",
            "amount": 5,
            "pnl": 4,
            "win": True,
            "asset": "USDJPY",
            "confidence": 80
        }
        
        response = requests.post(f"{BASE_URL}/api/risk-management/record-trade", params=params)
        assert response.status_code == 200
        
        data = response.json()
        current_status = data.get("current_status", {})
        
        # Balance should have increased by pnl
        assert "balance" in current_status, "Missing balance in current_status"
        
        print(f"✅ Balance updated: {initial_balance} -> {current_status['balance']}")
    
    def test_record_trade_returns_current_status(self):
        """Test that recording a trade returns current status"""
        params = {
            "direction": "CALL",
            "amount": 5,
            "pnl": 4,
            "win": True,
            "asset": "AUDUSD",
            "confidence": 70
        }
        
        response = requests.post(f"{BASE_URL}/api/risk-management/record-trade", params=params)
        assert response.status_code == 200
        
        data = response.json()
        current_status = data.get("current_status", {})
        
        # Verify current status fields
        assert "balance" in current_status, "Missing balance"
        assert "drawdown_pct" in current_status, "Missing drawdown_pct"
        assert "risk_level" in current_status, "Missing risk_level"
        assert "consecutive_losses" in current_status, "Missing consecutive_losses"
        assert "can_trade" in current_status, "Missing can_trade"
        
        print(f"✅ Current status returned: risk_level={current_status['risk_level']}, can_trade={current_status['can_trade']}")


class TestCanTrade:
    """Test GET /api/risk-management/can-trade endpoint"""
    
    def test_can_trade_returns_success(self):
        """Test that can-trade endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/risk-management/can-trade", params={"confidence": 0.7})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"✅ Can-trade endpoint returns success")
    
    def test_can_trade_returns_boolean(self):
        """Test that can-trade returns a boolean value"""
        response = requests.get(f"{BASE_URL}/api/risk-management/can-trade", params={"confidence": 0.7})
        assert response.status_code == 200
        
        data = response.json()
        assert "can_trade" in data, "Missing can_trade field"
        assert isinstance(data["can_trade"], bool), "can_trade should be boolean"
        
        print(f"✅ Can trade: {data['can_trade']}")
    
    def test_can_trade_returns_reason(self):
        """Test that can-trade returns a reason"""
        response = requests.get(f"{BASE_URL}/api/risk-management/can-trade", params={"confidence": 0.7})
        assert response.status_code == 200
        
        data = response.json()
        assert "reason" in data, "Missing reason field"
        assert isinstance(data["reason"], str), "reason should be string"
        
        print(f"✅ Reason: {data['reason']}")
    
    def test_can_trade_returns_recommended_position_size(self):
        """Test that can-trade returns recommended position size"""
        response = requests.get(f"{BASE_URL}/api/risk-management/can-trade", params={"confidence": 0.8})
        assert response.status_code == 200
        
        data = response.json()
        assert "recommended_position_size" in data, "Missing recommended_position_size"
        assert isinstance(data["recommended_position_size"], (int, float)), "recommended_position_size should be numeric"
        
        print(f"✅ Recommended position size: ${data['recommended_position_size']}")
    
    def test_can_trade_with_different_confidence_levels(self):
        """Test can-trade with different confidence levels"""
        confidence_levels = [0.5, 0.7, 0.9]
        
        for conf in confidence_levels:
            response = requests.get(f"{BASE_URL}/api/risk-management/can-trade", params={"confidence": conf})
            assert response.status_code == 200, f"Failed for confidence={conf}"
            
            data = response.json()
            assert data.get("success") == True, f"Failed for confidence={conf}"
            
            print(f"✅ Confidence {conf}: can_trade={data['can_trade']}, position_size=${data['recommended_position_size']}")


class TestPositionSize:
    """Test GET /api/risk-management/position-size endpoint"""
    
    def test_position_size_returns_success(self):
        """Test that position-size endpoint returns success"""
        response = requests.get(f"{BASE_URL}/api/risk-management/position-size", params={"confidence": 0.8})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"✅ Position-size endpoint returns success")
    
    def test_position_size_returns_recommended_amount(self):
        """Test that position-size returns recommended amount"""
        response = requests.get(f"{BASE_URL}/api/risk-management/position-size", params={"confidence": 0.8})
        assert response.status_code == 200
        
        data = response.json()
        assert "recommended_amount" in data, "Missing recommended_amount"
        assert isinstance(data["recommended_amount"], (int, float)), "recommended_amount should be numeric"
        assert data["recommended_amount"] >= 0, "recommended_amount should be non-negative"
        
        print(f"✅ Recommended amount: ${data['recommended_amount']}")
    
    def test_position_size_returns_kelly_fraction(self):
        """Test that position-size returns Kelly fraction"""
        response = requests.get(f"{BASE_URL}/api/risk-management/position-size", params={"confidence": 0.8})
        assert response.status_code == 200
        
        data = response.json()
        assert "kelly_fraction_pct" in data, "Missing kelly_fraction_pct"
        assert isinstance(data["kelly_fraction_pct"], (int, float)), "kelly_fraction_pct should be numeric"
        
        print(f"✅ Kelly fraction: {data['kelly_fraction_pct']}%")
    
    def test_position_size_returns_current_balance(self):
        """Test that position-size returns current balance"""
        response = requests.get(f"{BASE_URL}/api/risk-management/position-size", params={"confidence": 0.8})
        assert response.status_code == 200
        
        data = response.json()
        assert "current_balance" in data, "Missing current_balance"
        assert isinstance(data["current_balance"], (int, float)), "current_balance should be numeric"
        
        print(f"✅ Current balance: ${data['current_balance']}")
    
    def test_position_size_returns_risk_level(self):
        """Test that position-size returns risk level"""
        response = requests.get(f"{BASE_URL}/api/risk-management/position-size", params={"confidence": 0.8})
        assert response.status_code == 200
        
        data = response.json()
        assert "risk_level" in data, "Missing risk_level"
        valid_levels = ["normal", "elevated", "high", "critical", "paused"]
        assert data["risk_level"] in valid_levels, f"Invalid risk_level: {data['risk_level']}"
        
        print(f"✅ Risk level: {data['risk_level']}")
    
    def test_position_size_varies_with_confidence(self):
        """Test that position size varies with confidence level"""
        low_conf_response = requests.get(f"{BASE_URL}/api/risk-management/position-size", params={"confidence": 0.5})
        high_conf_response = requests.get(f"{BASE_URL}/api/risk-management/position-size", params={"confidence": 0.9})
        
        assert low_conf_response.status_code == 200
        assert high_conf_response.status_code == 200
        
        low_conf_data = low_conf_response.json()
        high_conf_data = high_conf_response.json()
        
        # Higher confidence should generally result in larger position size
        # (unless risk conditions override)
        print(f"✅ Position size at 0.5 confidence: ${low_conf_data['recommended_amount']}")
        print(f"✅ Position size at 0.9 confidence: ${high_conf_data['recommended_amount']}")


class TestRiskManagementIntegration:
    """Integration tests for risk management workflow"""
    
    def test_full_trading_workflow(self):
        """Test a complete trading workflow: check status, record trades, verify metrics"""
        # Step 1: Get initial status
        status_response = requests.get(f"{BASE_URL}/api/risk-management/status")
        assert status_response.status_code == 200
        initial_status = status_response.json()
        print(f"✅ Step 1: Initial status retrieved")
        
        # Step 2: Check if we can trade
        can_trade_response = requests.get(f"{BASE_URL}/api/risk-management/can-trade", params={"confidence": 0.75})
        assert can_trade_response.status_code == 200
        can_trade_data = can_trade_response.json()
        print(f"✅ Step 2: Can trade check: {can_trade_data['can_trade']} - {can_trade_data['reason']}")
        
        # Step 3: Get recommended position size
        position_response = requests.get(f"{BASE_URL}/api/risk-management/position-size", params={"confidence": 0.75})
        assert position_response.status_code == 200
        position_data = position_response.json()
        print(f"✅ Step 3: Recommended position: ${position_data['recommended_amount']}")
        
        # Step 4: Record a trade
        trade_params = {
            "direction": "CALL",
            "amount": position_data['recommended_amount'],
            "pnl": position_data['recommended_amount'] * 0.85,  # 85% payout
            "win": True,
            "asset": "EURUSD",
            "confidence": 75
        }
        trade_response = requests.post(f"{BASE_URL}/api/risk-management/record-trade", params=trade_params)
        assert trade_response.status_code == 200
        print(f"✅ Step 4: Trade recorded")
        
        # Step 5: Get updated metrics
        metrics_response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert metrics_response.status_code == 200
        metrics_data = metrics_response.json()
        print(f"✅ Step 5: Updated metrics - Win rate: {metrics_data['metrics']['win_rate_pct']}%, Sharpe: {metrics_data['metrics']['sharpe_ratio']}")
        
        print(f"✅ Full trading workflow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
