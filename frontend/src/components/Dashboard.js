import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import LiveSignalsDisplay from './LiveSignalsDisplay';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = ({ botStatus }) => {
  const [marketData, setMarketData] = useState(null);
  const [recentSignals, setRecentSignals] = useState([]);
  const [performanceData, setPerformanceData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const handleSignalExecute = (signal) => {
    console.log("Executing signal from dashboard:", signal);
    // Here you could integrate with platform trading APIs
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [marketResponse, signalsResponse, performanceResponse] = await Promise.all([
        axios.get(`${API}/market/data`),
        axios.get(`${API}/signals/active`),
        axios.get(`${API}/performance/metrics`)
      ]);

      setMarketData(marketResponse.data);
      setRecentSignals(signalsResponse.data.slice(0, 5)); // Show last 5 signals
      setPerformanceData(performanceResponse.data);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-6 bg-slate-800/30 border-slate-700/50">
              <div className="skeleton h-20 w-full rounded"></div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const getSignalStatusColor = (signal) => {
    if (signal.actual_outcome === 'WIN') return 'text-green-400';
    if (signal.actual_outcome === 'LOSS') return 'text-red-400';
    return 'text-yellow-400';
  };

  const getSignalStatusIcon = (signal) => {
    if (signal.actual_outcome === 'WIN') return '✅';
    if (signal.actual_outcome === 'LOSS') return '❌';
    return '⏳';
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Trading Dashboard</h2>
          <p className="text-slate-400">Real-time overview with live signals and platform integrations</p>
        </div>
        <Button 
          onClick={fetchDashboardData}
          className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
          data-testid="refresh-dashboard"
        >
          🔄 Refresh
        </Button>
      </div>

      {/* Live Signals Display - New Primary Section */}
      <LiveSignalsDisplay 
        botStatus={botStatus} 
        onSignalExecute={handleSignalExecute}
      />

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="p-6 glass-dark border-emerald-500/20 card-hover">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm font-medium">Bot Status</p>
              <div className="flex items-center space-x-2 mt-2">
                <div className={`w-3 h-3 rounded-full ${
                  botStatus?.is_running ? 'status-online' : 'status-offline'
                }`}></div>
                <span className="text-xl font-bold text-white">
                  {botStatus?.is_running ? 'ACTIVE' : 'STOPPED'}
                </span>
              </div>
            </div>
            <div className="text-3xl">🤖</div>
          </div>
        </Card>

        <Card className="p-6 glass-dark border-green-500/20 card-hover">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm font-medium">Win Rate</p>
              <p className="text-2xl font-bold text-green-400 mt-1">
                {performanceData?.win_rate || 0}%
              </p>
            </div>
            <div className="text-3xl">📈</div>
          </div>
        </Card>

        <Card className="p-6 glass-dark border-blue-500/20 card-hover">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm font-medium">Total Signals</p>
              <p className="text-2xl font-bold text-blue-400 mt-1">
                {performanceData?.total_signals || 0}
              </p>
            </div>
            <div className="text-3xl">📊</div>
          </div>
        </Card>

        <Card className="p-6 glass-dark border-purple-500/20 card-hover">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm font-medium">P&L</p>
              <p className={`text-2xl font-bold mt-1 ${
                (performanceData?.profit_loss || 0) >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                ${performanceData?.profit_loss || 0}
              </p>
            </div>
            <div className="text-3xl">💰</div>
          </div>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Signals */}
        <Card className="p-6 glass-dark border-slate-700/50">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-white">Recent Signals</h3>
            <span className="text-sm text-slate-400">Last 5 signals</span>
          </div>
          
          <div className="space-y-3" data-testid="recent-signals">
            {recentSignals.length === 0 ? (
              <div className="text-center text-slate-400 py-8">
                <div className="text-4xl mb-2">📭</div>
                <p>No signals generated yet</p>
              </div>
            ) : (
              recentSignals.map((signal, index) => (
                <div 
                  key={signal.id || index} 
                  className="flex items-center justify-between p-4 bg-slate-800/50 rounded-lg border border-slate-700/30 signal-item"
                >
                  <div className="flex items-center space-x-4">
                    <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                      signal.direction === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {signal.direction}
                    </div>
                    <div>
                      <p className="text-white font-medium">{signal.symbol}</p>
                      <p className="text-slate-400 text-sm">
                        ${signal.entry_price} • {signal.probability}%
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`text-sm font-medium ${getSignalStatusColor(signal)}`}>
                      {signal.actual_outcome || 'Pending'}
                    </span>
                    <span className="text-lg">
                      {getSignalStatusIcon(signal)}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Market Overview */}
        <Card className="p-6 glass-dark border-slate-700/50">
          <h3 className="text-xl font-semibold text-white mb-6">Market Overview</h3>
          
          <div className="space-y-4" data-testid="market-overview">
            {marketData ? (
              Object.entries(marketData).map(([assetType, assets]) => (
                <div key={assetType} className="space-y-2">
                  <h4 className="text-emerald-400 font-medium capitalize">{assetType}</h4>
                  {assets.slice(0, 3).map((asset, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
                      <div>
                        <p className="text-white font-medium">{asset.symbol}</p>
                        <p className="text-slate-400 text-sm">{asset.asset_type}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-white font-medium">${asset.price}</p>
                        <p className={`text-sm ${
                          asset.change >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {asset.change >= 0 ? '+' : ''}{asset.change_percent}%
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ))
            ) : (
              <div className="text-center text-slate-400 py-8">
                <div className="text-4xl mb-2">📊</div>
                <p>Loading market data...</p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Performance Summary */}
      {performanceData && (
        <Card className="p-6 glass-dark border-slate-700/50">
          <h3 className="text-xl font-semibold text-white mb-6">Performance Summary</h3>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="performance-summary">
            <div className="text-center">
              <p className="text-slate-400 text-sm">Total Wins</p>
              <p className="text-2xl font-bold text-green-400">{performanceData.total_wins}</p>
            </div>
            <div className="text-center">
              <p className="text-slate-400 text-sm">Total Losses</p>
              <p className="text-2xl font-bold text-red-400">{performanceData.total_losses}</p>
            </div>
            <div className="text-center">
              <p className="text-slate-400 text-sm">Profit Factor</p>
              <p className="text-2xl font-bold text-blue-400">{performanceData.profit_factor}</p>
            </div>
            <div className="text-center">
              <p className="text-slate-400 text-sm">Avg Probability</p>
              <p className="text-2xl font-bold text-purple-400">{performanceData.average_probability}%</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};

export default Dashboard;