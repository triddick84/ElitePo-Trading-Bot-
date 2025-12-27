import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const AdaptiveStrategyResults = () => {
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [configRes, statsRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/adaptive-strategy/config`),
        axios.get(`${BACKEND_URL}/api/adaptive-strategy/stats`)
      ]);
      
      if (configRes.data.success) {
        setConfig(configRes.data.config);
      }
      
      if (statsRes.data.success) {
        setStats(statsRes.data.stats);
      }
    } catch (error) {
      console.error('Error loading adaptive strategy data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !config) {
    return (
      <Card className="w-full bg-slate-900 border-slate-700">
        <CardContent className="p-6">
          <div className="text-center text-slate-400">Loading adaptive strategy results...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Strategy Breakdown */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <CardTitle className="text-2xl text-emerald-400">🎯 Adaptive Strategy Breakdown</CardTitle>
          <CardDescription className="text-slate-400">
            How the system adapts to different market conditions
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Trending Market Strategy */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-blue-400">📈 Trending Market Strategy</h3>
              <Badge className="bg-blue-500/20 text-blue-400 border-blue-500">
                ADX > {config.adx_trending_threshold}
              </Badge>
            </div>
            
            <div className="bg-slate-800 rounded-lg p-4 space-y-3">
              <div>
                <p className="text-sm text-slate-400 mb-2">Active Indicators:</p>
                <div className="flex flex-wrap gap-2">
                  {config.trending_indicators.map(indicator => (
                    <Badge key={indicator} className="bg-blue-500/10 text-blue-400 border-blue-500/50">
                      {indicator}
                    </Badge>
                  ))}
                </div>
              </div>
              
              <div>
                <p className="text-sm text-slate-400 mb-2">Strategy Logic:</p>
                <ul className="text-sm text-slate-300 space-y-1">
                  <li>• <span className="text-blue-400">MACD</span> - Identifies trend direction and momentum</li>
                  <li>• <span className="text-blue-400">Parabolic SAR</span> - Provides entry/exit signals</li>
                  <li>• <span className="text-blue-400">EMA</span> - Confirms trend strength</li>
                  <li>• <strong>Execution Delay:</strong> {config.trending_execution_delay}s (avoids whipsaws)</li>
                </ul>
              </div>
              
              {stats?.trending && (
                <div className="border-t border-slate-700 pt-3 mt-3">
                  <p className="text-xs text-slate-400 mb-2">Performance Metrics:</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <p className="text-xs text-slate-500">Signals</p>
                      <p className="text-lg font-bold text-white">{stats.trending.total_signals || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Win Rate</p>
                      <p className="text-lg font-bold text-emerald-400">
                        {stats.trending.win_rate ? `${stats.trending.win_rate.toFixed(1)}%` : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Avg Confidence</p>
                      <p className="text-lg font-bold text-blue-400">
                        {stats.trending.avg_confidence ? `${stats.trending.avg_confidence.toFixed(1)}%` : 'N/A'}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Ranging Market Strategy */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-orange-400">📉 Ranging/Volatile Market Strategy</h3>
              <Badge className="bg-orange-500/20 text-orange-400 border-orange-500">
                ADX < {config.adx_ranging_threshold}
              </Badge>
            </div>
            
            <div className="bg-slate-800 rounded-lg p-4 space-y-3">
              <div>
                <p className="text-sm text-slate-400 mb-2">Active Indicators:</p>
                <div className="flex flex-wrap gap-2">
                  {config.ranging_indicators.map(indicator => (
                    <Badge key={indicator} className="bg-orange-500/10 text-orange-400 border-orange-500/50">
                      {indicator}
                    </Badge>
                  ))}
                </div>
              </div>
              
              <div>
                <p className="text-sm text-slate-400 mb-2">Strategy Logic:</p>
                <ul className="text-sm text-slate-300 space-y-1">
                  <li>• <span className="text-orange-400">RSI</span> - Identifies overbought/oversold conditions</li>
                  <li>• <span className="text-orange-400">Bollinger Bands</span> - Mean reversion signals</li>
                  <li>• <span className="text-orange-400">Volume</span> - Confirms breakout validity</li>
                  <li>• <span className="text-orange-400">EMA</span> - Dynamic support/resistance</li>
                  <li>• <strong>Execution Delay:</strong> {config.ranging_execution_delay}s (quick entries)</li>
                  <li>• <strong>Signal Threshold:</strong> {config.ranging_signal_threshold}% (filters noise)</li>
                </ul>
              </div>
              
              {stats?.ranging && (
                <div className="border-t border-slate-700 pt-3 mt-3">
                  <p className="text-xs text-slate-400 mb-2">Performance Metrics:</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <p className="text-xs text-slate-500">Signals</p>
                      <p className="text-lg font-bold text-white">{stats.ranging.total_signals || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Win Rate</p>
                      <p className="text-lg font-bold text-emerald-400">
                        {stats.ranging.win_rate ? `${stats.ranging.win_rate.toFixed(1)}%` : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Avg Confidence</p>
                      <p className="text-lg font-bold text-orange-400">
                        {stats.ranging.avg_confidence ? `${stats.ranging.avg_confidence.toFixed(1)}%` : 'N/A'}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Neutral Market Strategy */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-purple-400">⚖️ Neutral Market Strategy</h3>
              <Badge className="bg-purple-500/20 text-purple-400 border-purple-500">
                {config.adx_ranging_threshold} ≤ ADX ≤ {config.adx_trending_threshold}
              </Badge>
            </div>
            
            <div className="bg-slate-800 rounded-lg p-4 space-y-3">
              <div>
                <p className="text-sm text-slate-400 mb-2">Strategy Logic:</p>
                <ul className="text-sm text-slate-300 space-y-1">
                  <li>• <span className="text-purple-400">Hybrid Approach</span> - Combines both strategies</li>
                  <li>• <strong>Signal Requirement:</strong> Both trending AND ranging indicators must agree</li>
                  <li>• <strong>Higher Threshold:</strong> Requires ≥ 85% confidence</li>
                  <li>• <strong>Conservative Execution:</strong> Waits for maximum confirmation</li>
                </ul>
              </div>
              
              {stats?.neutral && (
                <div className="border-t border-slate-700 pt-3 mt-3">
                  <p className="text-xs text-slate-400 mb-2">Performance Metrics:</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <p className="text-xs text-slate-500">Signals</p>
                      <p className="text-lg font-bold text-white">{stats.neutral.total_signals || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Win Rate</p>
                      <p className="text-lg font-bold text-emerald-400">
                        {stats.neutral.win_rate ? `${stats.neutral.win_rate.toFixed(1)}%` : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Avg Confidence</p>
                      <p className="text-lg font-bold text-purple-400">
                        {stats.neutral.avg_confidence ? `${stats.neutral.avg_confidence.toFixed(1)}%` : 'N/A'}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Overall Performance */}
      {stats?.overall && (
        <Card className="bg-slate-900 border-slate-700">
          <CardHeader>
            <CardTitle className="text-xl text-white">📊 Overall Adaptive Strategy Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Total Signals</p>
                <p className="text-2xl font-bold text-white">{stats.overall.total_signals || 0}</p>
              </div>
              
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Overall Win Rate</p>
                <p className="text-2xl font-bold text-emerald-400">
                  {stats.overall.win_rate ? `${stats.overall.win_rate.toFixed(1)}%` : 'N/A'}
                </p>
                {stats.overall.win_rate && (
                  <Progress value={stats.overall.win_rate} className="mt-2 h-2" />
                )}
              </div>
              
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Avg Confidence</p>
                <p className="text-2xl font-bold text-blue-400">
                  {stats.overall.avg_confidence ? `${stats.overall.avg_confidence.toFixed(1)}%` : 'N/A'}
                </p>
              </div>
              
              <div className="bg-slate-800 rounded-lg p-4">
                <p className="text-sm text-slate-400 mb-1">Best Strategy</p>
                <p className="text-2xl font-bold text-amber-400">
                  {stats.overall.best_strategy || 'N/A'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default AdaptiveStrategyResults;