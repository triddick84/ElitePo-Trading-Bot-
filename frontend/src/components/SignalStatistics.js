import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { TrendingUp, TrendingDown, Target, BarChart3, RefreshCw } from 'lucide-react';
import axios from 'axios';

const SignalStatistics = () => {
  const [stats, setStats] = useState(null);
  const [recentValidations, setRecentValidations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTimeframe, setSelectedTimeframe] = useState('all');
  const [selectedPeriod, setSelectedPeriod] = useState(24);

  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    fetchStatistics();
    fetchRecentValidations();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchStatistics();
      fetchRecentValidations();
    }, 30000);
    
    return () => clearInterval(interval);
  }, [selectedTimeframe, selectedPeriod]);

  const fetchStatistics = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ hours: selectedPeriod });
      if (selectedTimeframe !== 'all') {
        params.append('timeframe', selectedTimeframe);
      }
      
      const response = await axios.get(`${BACKEND_URL}/api/signals/statistics?${params}`);
      if (response.data.success) {
        setStats(response.data.statistics);
      }
    } catch (error) {
      console.error('Error fetching statistics:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchRecentValidations = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/signals/validations/recent?limit=10`);
      if (response.data.success) {
        setRecentValidations(response.data.validations);
      }
    } catch (error) {
      console.error('Error fetching recent validations:', error);
    }
  };

  const triggerAILearning = async () => {
    try {
      setLoading(true);
      const response = await axios.post(`${BACKEND_URL}/api/ai/learn`);
      if (response.data.success) {
        alert('✅ AI Learning completed! Strategies have been adjusted based on recent performance.');
        fetchStatistics();
      }
    } catch (error) {
      console.error('Error triggering AI learning:', error);
      alert('❌ Error triggering AI learning');
    } finally {
      setLoading(false);
    }
  };

  const getWinRateColor = (rate) => {
    if (rate >= 70) return 'text-green-400';
    if (rate >= 60) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getWinRateBg = (rate) => {
    if (rate >= 70) return 'bg-green-500/20 border-green-500/30';
    if (rate >= 60) return 'bg-yellow-500/20 border-yellow-500/30';
    return 'bg-red-500/20 border-red-500/30';
  };

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin w-8 h-8 border-4 border-emerald-400 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-7 h-7 text-emerald-400" />
            Signal Performance
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Track win/loss rates and accuracy of generated signals
          </p>
        </div>
        <Button
          onClick={() => {
            fetchStatistics();
            fetchRecentValidations();
          }}
          className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <Card className="p-4 bg-slate-800/50 border-slate-700">
        <div className="flex flex-wrap gap-4">
          <div>
            <label className="text-slate-300 text-sm mb-2 block">Timeframe</label>
            <select
              value={selectedTimeframe}
              onChange={(e) => setSelectedTimeframe(e.target.value)}
              className="bg-slate-700 border border-slate-600 text-white rounded px-3 py-2 text-sm"
            >
              <option value="all">All Timeframes</option>
              <option value="5s">5 Seconds</option>
              <option value="15s">15 Seconds</option>
              <option value="30s">30 Seconds</option>
              <option value="1m">1 Minute</option>
              <option value="2m">2 Minutes</option>
              <option value="3m">3 Minutes</option>
              <option value="5m">5 Minutes</option>
            </select>
          </div>
          <div>
            <label className="text-slate-300 text-sm mb-2 block">Period</label>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(parseInt(e.target.value))}
              className="bg-slate-700 border border-slate-600 text-white rounded px-3 py-2 text-sm"
            >
              <option value={1}>Last Hour</option>
              <option value={6}>Last 6 Hours</option>
              <option value={24}>Last 24 Hours</option>
              <option value={72}>Last 3 Days</option>
              <option value={168}>Last Week</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Statistics Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Signals */}
          <Card className={`p-4 bg-slate-800/60 border-slate-700`}>
            <div className="text-slate-400 text-sm mb-1">Total Signals</div>
            <div className="text-3xl font-bold text-white">{stats.total_signals}</div>
            <div className="text-slate-500 text-xs mt-1">Validated</div>
          </Card>

          {/* Win Rate */}
          <Card className={`p-4 ${getWinRateBg(stats.win_rate)} border`}>
            <div className="text-slate-300 text-sm mb-1">Win Rate</div>
            <div className={`text-3xl font-bold ${getWinRateColor(stats.win_rate)}`}>
              {stats.win_rate}%
            </div>
            <div className="text-slate-400 text-xs mt-1">
              {stats.wins}W / {stats.losses}L
            </div>
          </Card>

          {/* BUY Signals */}
          <Card className="p-4 bg-green-500/10 border border-green-500/30">
            <div className="text-green-300 text-sm mb-1 flex items-center gap-1">
              <TrendingUp className="w-4 h-4" />
              BUY Signals
            </div>
            <div className="text-2xl font-bold text-green-400">
              {stats.buy_signals?.win_rate || 0}%
            </div>
            <div className="text-green-600 text-xs mt-1">
              {stats.buy_signals?.wins || 0}W / {(stats.buy_signals?.total || 0) - (stats.buy_signals?.wins || 0)}L
            </div>
          </Card>

          {/* SELL Signals */}
          <Card className="p-4 bg-red-500/10 border border-red-500/30">
            <div className="text-red-300 text-sm mb-1 flex items-center gap-1">
              <TrendingDown className="w-4 h-4" />
              SELL Signals
            </div>
            <div className="text-2xl font-bold text-red-400">
              {stats.sell_signals?.win_rate || 0}%
            </div>
            <div className="text-red-600 text-xs mt-1">
              {stats.sell_signals?.wins || 0}W / {(stats.sell_signals?.total || 0) - (stats.sell_signals?.wins || 0)}L
            </div>
          </Card>
        </div>
      )}

      {/* Recent Validations */}
      <Card className="p-6 bg-slate-800/60 border-slate-700">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <Target className="w-5 h-5 text-emerald-400" />
          Recent Signal Results
        </h3>
        
        <div className="space-y-2">
          {recentValidations.length === 0 ? (
            <div className="text-center text-slate-400 py-8">
              <Target className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No validated signals yet</p>
              <p className="text-sm mt-1">Signals are validated automatically after expiration</p>
            </div>
          ) : (
            recentValidations.map((validation, index) => (
              <div
                key={index}
                className={`p-3 rounded-lg border flex items-center justify-between ${
                  validation.result === 'WIN'
                    ? 'bg-green-500/10 border-green-500/30'
                    : 'bg-red-500/10 border-red-500/30'
                }`}
              >
                <div className="flex items-center gap-3">
                  {/* Result Badge */}
                  <Badge
                    className={`font-bold ${
                      validation.result === 'WIN'
                        ? 'bg-green-500 text-white'
                        : 'bg-red-500 text-white'
                    }`}
                  >
                    {validation.result}
                  </Badge>

                  {/* Direction */}
                  <div className={`flex items-center gap-1 ${
                    validation.direction === 'BUY' || validation.direction === 'CALL'
                      ? 'text-green-400'
                      : 'text-red-400'
                  }`}>
                    {validation.direction === 'BUY' || validation.direction === 'CALL' ? (
                      <TrendingUp className="w-4 h-4" />
                    ) : (
                      <TrendingDown className="w-4 h-4" />
                    )}
                    <span className="font-semibold">{validation.direction}</span>
                  </div>

                  {/* Symbol */}
                  <span className="text-white font-medium">
                    {validation.symbol.replace('_OTC', '').replace('_regular', '')}
                  </span>

                  {/* Price Change */}
                  <span className={`text-sm ${
                    validation.price_change_percent > 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {validation.price_change_percent > 0 ? '+' : ''}
                    {validation.price_change_percent.toFixed(3)}%
                  </span>
                </div>

                <div className="text-right text-slate-400 text-xs">
                  <div>{new Date(validation.validated_at).toLocaleTimeString()}</div>
                  <div className="text-slate-500">
                    {validation.expiration_minutes < 1
                      ? `${(validation.expiration_minutes * 60).toFixed(0)}s`
                      : `${validation.expiration_minutes}m`}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
};

export default SignalStatistics;
