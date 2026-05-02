"""
Test Analytics Dashboard APIs - Iteration 22
Tests for the new Analytics Dashboard feature in Performance Center
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pocket-option-ai-9.preview.emergentagent.com')

class TestAnalyticsDashboardAPIs:
    """Tests for Analytics Dashboard backend APIs"""
    
    # ML Model Stats APIs
    def test_maximized_ml_stats(self):
        """GET /api/maximized-ml/stats - returns ML model stats"""
        response = requests.get(f"{BASE_URL}/api/maximized-ml/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get('success') == True
        stats = data.get('stats', {})
        
        # Verify required fields
        assert 'model_accuracy' in stats or 'accuracy' in stats
        assert 'predictions_made' in stats
        assert 'feature_count' in stats
        assert 'models_in_ensemble' in stats
        assert isinstance(stats.get('models_in_ensemble', []), list)
        
    def test_lstm_gru_stats(self):
        """GET /api/lstm-gru/stats - returns LSTM/GRU stats"""
        response = requests.get(f"{BASE_URL}/api/lstm-gru/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get('success') == True
        assert 'accuracy' in data
        assert 'total_predictions' in data
        assert 'training_history' in data
        
        # Verify training_history structure
        history = data.get('training_history', {})
        assert 'train_accuracy' in history or 'epochs_run' in history
        
    def test_ppo_rl_stats(self):
        """GET /api/ppo-rl/stats - returns PPO RL stats"""
        response = requests.get(f"{BASE_URL}/api/ppo-rl/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get('success') == True
        assert 'accuracy' in data
        assert 'training_stats' in data
        
        # Verify training_stats structure
        stats = data.get('training_stats', {})
        assert 'avg_reward' in stats or 'total_episodes' in stats
        
    # Risk Management API
    def test_risk_management_metrics(self):
        """GET /api/risk-management/metrics - returns risk metrics"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get('success') == True
        metrics = data.get('metrics', {})
        
        # Verify all required risk metrics
        assert 'sharpe_ratio' in metrics
        assert 'sortino_ratio' in metrics
        assert 'max_drawdown_pct' in metrics
        assert 'profit_factor' in metrics
        assert 'win_rate_pct' in metrics
        assert 'kelly_fraction_pct' in metrics
        
        # Verify numeric types
        assert isinstance(metrics.get('sharpe_ratio'), (int, float))
        assert isinstance(metrics.get('sortino_ratio'), (int, float))
        assert isinstance(metrics.get('max_drawdown_pct'), (int, float))
        
    # Historical Data API
    def test_historical_summary(self):
        """GET /api/historical/summary - returns historical data summary"""
        response = requests.get(f"{BASE_URL}/api/historical/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get('success') == True
        summary = data.get('summary', {})
        
        # Verify required fields
        assert 'total_candles' in summary
        assert 'symbols' in summary
        assert 'timeframes' in summary
        assert 'sources' in summary
        
        # Verify types
        assert isinstance(summary.get('total_candles'), int)
        assert isinstance(summary.get('symbols', []), list)
        assert isinstance(summary.get('timeframes', []), list)
        
    # Asset Performance API
    def test_asset_performance(self):
        """GET /api/signals/asset-performance - returns all_assets array"""
        response = requests.get(f"{BASE_URL}/api/signals/asset-performance")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get('success') == True
        assert 'all_assets' in data
        
        all_assets = data.get('all_assets', [])
        assert isinstance(all_assets, list)
        
        # If there are assets, verify structure
        if len(all_assets) > 0:
            asset = all_assets[0]
            assert 'symbol' in asset
            assert 'win_rate' in asset
            assert 'total' in asset
            
    # Hourly Stats API
    def test_hourly_stats(self):
        """GET /api/signals/hourly-stats - returns hourly_stats array"""
        response = requests.get(f"{BASE_URL}/api/signals/hourly-stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get('success') == True
        assert 'hourly_stats' in data
        
        hourly_stats = data.get('hourly_stats', [])
        assert isinstance(hourly_stats, list)
        
        # Should have 24 hours
        assert len(hourly_stats) >= 24
        
        # Verify structure of hourly stat
        if len(hourly_stats) > 0:
            hour = hourly_stats[0]
            assert 'hour_utc' in hour
            assert 'session' in hour
            assert 'win_rate' in hour or hour.get('win_rate') is None
            assert 'is_best_hour' in hour
            assert 'is_bad_hour' in hour


class TestAnalyticsDashboardDataIntegrity:
    """Tests for data integrity and consistency"""
    
    def test_ml_models_have_consistent_accuracy_format(self):
        """Verify all ML models return accuracy in consistent format"""
        ml_response = requests.get(f"{BASE_URL}/api/maximized-ml/stats")
        lstm_response = requests.get(f"{BASE_URL}/api/lstm-gru/stats")
        ppo_response = requests.get(f"{BASE_URL}/api/ppo-rl/stats")
        
        assert ml_response.status_code == 200
        assert lstm_response.status_code == 200
        assert ppo_response.status_code == 200
        
        ml_data = ml_response.json()
        lstm_data = lstm_response.json()
        ppo_data = ppo_response.json()
        
        # All should have accuracy as a number
        ml_accuracy = ml_data.get('stats', {}).get('model_accuracy', 0)
        lstm_accuracy = lstm_data.get('accuracy', 0)
        ppo_accuracy = ppo_data.get('accuracy', 0)
        
        assert isinstance(ml_accuracy, (int, float))
        assert isinstance(lstm_accuracy, (int, float))
        assert isinstance(ppo_accuracy, (int, float))
        
    def test_hourly_stats_covers_24_hours(self):
        """Verify hourly stats covers all 24 hours"""
        response = requests.get(f"{BASE_URL}/api/signals/hourly-stats")
        assert response.status_code == 200
        data = response.json()
        
        hourly_stats = data.get('hourly_stats', [])
        hours = [h.get('hour_utc') for h in hourly_stats]
        
        # Should have hours 0-23
        for hour in range(24):
            assert hour in hours, f"Missing hour {hour} in hourly stats"
            
    def test_risk_metrics_values_in_valid_range(self):
        """Verify risk metrics are in valid ranges"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics")
        assert response.status_code == 200
        data = response.json()
        
        metrics = data.get('metrics', {})
        
        # Win rate should be 0-100
        win_rate = metrics.get('win_rate_pct', 0)
        assert 0 <= win_rate <= 100, f"Win rate {win_rate} out of range"
        
        # Max drawdown should be >= 0
        max_dd = metrics.get('max_drawdown_pct', 0)
        assert max_dd >= 0, f"Max drawdown {max_dd} should be >= 0"
        
        # Kelly fraction should be reasonable
        kelly = metrics.get('kelly_fraction_pct', 0)
        assert -100 <= kelly <= 100, f"Kelly fraction {kelly} out of range"
