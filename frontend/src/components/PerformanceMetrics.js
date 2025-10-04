import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PerformanceMetrics = () => {
  const [metrics, setMetrics] = useState(null);
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [timeRange, setTimeRange] = useState(30);

  useEffect(() => {
    fetchPerformanceData();
  }, [timeRange]);

  const fetchPerformanceData = async () => {
    setIsLoading(true);
    try {
      const [metricsResponse, historyResponse] = await Promise.all([
        axios.get(`${API}/performance/metrics`),
        axios.get(`${API}/performance/history?days=${timeRange}`)
      ]);

      setMetrics(metricsResponse.data);
      setHistory(historyResponse.data.metrics || []);
    } catch (error) {
      console.error('Error fetching performance data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getMetricColor = (value, isPercentage = false) => {
    if (isPercentage) {
      if (value >= 80) return 'text-green-400';
      if (value >= 60) return 'text-yellow-400';
      return 'text-red-400';
    } else {
      if (value > 0) return 'text-green-400';
      if (value < 0) return 'text-red-400';
      return 'text-slate-400';
    }
  };

  const getRiskAssessment = (winRate, profitFactor) => {
    if (winRate >= 80 && profitFactor >= 2) return { level: 'Excellent', color: 'text-green-400' };
    if (winRate >= 70 && profitFactor >= 1.5) return { level: 'Good', color: 'text-yellow-400' };
    if (winRate >= 60 && profitFactor >= 1) return { level: 'Average', color: 'text-orange-400' };
    return { level: 'Poor', color: 'text-red-400' };
  };

  const MetricCard = ({ title, value, subtitle, icon, trend }) => (
    <Card className="p-6 glass-dark border-slate-700/50 card-hover">
      <div className="flex items-center justify-between mb-4">
        <div className="text-3xl">{icon}</div>
        {trend && (
          <div className={`text-sm font-medium ${trend > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {trend > 0 ? '↗️' : '↘️'} {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div>
        <p className="text-slate-400 text-sm font-medium">{title}</p>
        <p className="text-2xl font-bold text-white mt-1">{value}</p>
        {subtitle && (
          <p className="text-slate-400 text-xs mt-1">{subtitle}</p>
        )}
      </div>
    </Card>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-6 glass-dark border-slate-700/50">
              <div className="skeleton h-24 w-full rounded"></div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const riskAssessment = metrics ? getRiskAssessment(metrics.win_rate, metrics.profit_factor) : { level: 'Unknown', color: 'text-slate-400' };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="performance-metrics">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Performance Analytics</h2>
          <p className="text-slate-400">Comprehensive analysis of trading bot performance</p>
        </div>
        
        <div className="flex items-center space-x-4">
          {/* Time Range Selector */}
          <div className="flex space-x-2">
            {[7, 30, 90].map((days) => (
              <Button
                key={days}
                onClick={() => setTimeRange(days)}
                className={`text-sm ${
                  timeRange === days
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                    : 'bg-slate-700/30 text-slate-400 border-slate-600/30 hover:text-white'
                }`}
                data-testid={`timerange-${days}d`}
              >
                {days}d
              </Button>
            ))}
          </div>
          
          <Button 
            onClick={fetchPerformanceData}
            className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
            data-testid="refresh-performance"
          >
            🔄 Refresh
          </Button>
        </div>
      </div>

      {metrics ? (
        <>
          {/* Key Performance Indicators */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard
              title="Win Rate"
              value={`${metrics.win_rate}%`}
              subtitle={`${metrics.total_wins}/${metrics.total_signals} signals`}
              icon="🎯"
            />
            <MetricCard
              title="Profit & Loss"
              value={`$${metrics.profit_loss}`}
              subtitle={`${metrics.profit_loss >= 0 ? 'Profit' : 'Loss'}`}
              icon="💰"
            />
            <MetricCard
              title="Profit Factor"
              value={metrics.profit_factor}
              subtitle="Risk-adjusted return"
              icon="📊"
            />
            <MetricCard
              title="Total Signals"
              value={metrics.total_signals}
              subtitle="Generated signals"
              icon="📡"
            />
          </div>

          {/* Detailed Analytics */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Risk Assessment */}
            <Card className="p-6 glass-dark border-slate-700/50">
              <h3 className="text-xl font-semibold text-white mb-6">Risk Assessment</h3>
              
              <div className="space-y-4" data-testid="risk-assessment">
                <div className="text-center p-6 bg-slate-800/30 rounded-xl">
                  <div className="text-4xl mb-3">🛡️</div>
                  <p className="text-slate-400 text-sm mb-2">Overall Rating</p>
                  <p className={`text-2xl font-bold ${riskAssessment.color}`}>
                    {riskAssessment.level}
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Consistency</span>
                    <Badge className={`${metrics.win_rate >= 70 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                      {metrics.win_rate >= 70 ? 'High' : 'Low'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Profitability</span>
                    <Badge className={`${metrics.profit_factor >= 1.5 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                      {metrics.profit_factor >= 1.5 ? 'Good' : 'Poor'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Activity Level</span>
                    <Badge className={`${metrics.total_signals >= 10 ? 'bg-blue-500/20 text-blue-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                      {metrics.total_signals >= 10 ? 'Active' : 'Low'}
                    </Badge>
                  </div>
                </div>
              </div>
            </Card>

            {/* Strategy Performance */}
            <Card className="p-6 glass-dark border-slate-700/50">
              <h3 className="text-xl font-semibold text-white mb-6">Strategy Analysis</h3>
              
              <div className="space-y-4" data-testid="strategy-performance">
                <div className="space-y-3">
                  <div>
                    <p className="text-slate-400 text-sm mb-1">Active Strategies</p>
                    <div className="flex flex-wrap gap-2">
                      {metrics.active_strategies?.map((strategy, index) => (
                        <Badge key={index} className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                          {strategy.replace('_', ' ').toUpperCase()}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-slate-400 text-sm mb-1">Trading Mode</p>
                    <Badge className={`${
                      metrics.trading_mode === 'demo' 
                        ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                        : 'bg-red-500/20 text-red-400 border-red-500/30'
                    }`}>
                      {metrics.trading_mode?.toUpperCase()} MODE
                    </Badge>
                  </div>

                  <div>
                    <p className="text-slate-400 text-sm mb-2">Average Signal Confidence</p>
                    <div className="flex items-center space-x-3">
                      <div className="flex-1 bg-slate-700 rounded-full h-2">
                        <div 
                          className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${metrics.average_probability || 0}%` }}
                        ></div>
                      </div>
                      <span className="text-white font-medium">{metrics.average_probability}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            {/* Recent Performance */}
            <Card className="p-6 glass-dark border-slate-700/50">
              <h3 className="text-xl font-semibold text-white mb-6">Recent Trends</h3>
              
              <div className="space-y-4" data-testid="recent-performance">
                {history.length > 0 ? (
                  <div className="space-y-3">
                    {history.slice(0, 5).map((metric, index) => (
                      <div key={index} className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
                        <div>
                          <p className="text-white font-medium">
                            {new Date(metric.date).toLocaleDateString()}
                          </p>
                          <p className="text-slate-400 text-sm">
                            {metric.total_signals} signals
                          </p>
                        </div>
                        <div className="text-right">
                          <p className={`font-bold ${getMetricColor(metric.win_rate, true)}`}>
                            {metric.win_rate}%
                          </p>
                          <p className={`text-sm ${getMetricColor(metric.profit_loss)}`}>
                            ${metric.profit_loss}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <div className="text-4xl mb-2">📈</div>
                    <p className="text-slate-400">No historical data yet</p>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Performance Summary */}
          <Card className="p-6 glass-dark border-slate-700/50">
            <h3 className="text-xl font-semibold text-white mb-6">Performance Summary</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6" data-testid="performance-summary">
              <div className="text-center p-6 bg-slate-800/30 rounded-xl">
                <div className="text-3xl mb-3">🏆</div>
                <p className="text-slate-400 text-sm mb-1">Best Day</p>
                <p className="text-white text-xl font-bold">
                  {history.length > 0 ? `${Math.max(...history.map(h => h.win_rate))}%` : 'N/A'}
                </p>
              </div>
              
              <div className="text-center p-6 bg-slate-800/30 rounded-xl">
                <div className="text-3xl mb-3">📊</div>
                <p className="text-slate-400 text-sm mb-1">Avg Daily Signals</p>
                <p className="text-white text-xl font-bold">
                  {history.length > 0 ? Math.round(history.reduce((sum, h) => sum + h.total_signals, 0) / history.length) : 'N/A'}
                </p>
              </div>
              
              <div className="text-center p-6 bg-slate-800/30 rounded-xl">
                <div className="text-3xl mb-3">💎</div>
                <p className="text-slate-400 text-sm mb-1">Success Rate</p>
                <p className={`text-xl font-bold ${getMetricColor(metrics.win_rate, true)}`}>
                  {metrics.win_rate >= 80 ? 'Excellent' : metrics.win_rate >= 60 ? 'Good' : 'Needs Improvement'}
                </p>
              </div>
            </div>
          </Card>
        </>
      ) : (
        <Card className="p-12 glass-dark border-slate-700/50 text-center">
          <div className="text-6xl mb-4">📊</div>
          <h3 className="text-xl font-semibold text-white mb-2">No Performance Data</h3>
          <p className="text-slate-400">
            Start the trading bot to begin collecting performance metrics and analytics.
          </p>
        </Card>
      )}
    </div>
  );
};

export default PerformanceMetrics;