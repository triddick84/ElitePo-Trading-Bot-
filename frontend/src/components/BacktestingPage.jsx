/**
 * Comprehensive Backtesting Page
 * 
 * Features:
 * - Historical backtesting with real data (Yahoo Finance, CryptoCompare)
 * - Multi-strategy, multi-asset, multi-timeframe testing
 * - Up to 90 days of historical data
 * - Performance analytics and comparison
 * - Live data testing mode (coming soon)
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Checkbox } from './ui/checkbox';
import { Slider } from './ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Alert, AlertDescription } from './ui/alert';
import { Progress } from './ui/progress';
import { toast } from 'sonner';
import { 
  Play, History, TrendingUp, TrendingDown, BarChart3, Target, 
  RefreshCw, Download, Trash2, Clock, DollarSign, Award,
  Activity, AlertTriangle, CheckCircle, XCircle, Zap, Filter
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Timeframes available
const TIMEFRAMES = [
  { id: '1m', name: '1 Minute', icon: '⚡' },
  { id: '5m', name: '5 Minutes', icon: '🔥' },
  { id: '15m', name: '15 Minutes', icon: '⏱️' },
  { id: '30m', name: '30 Minutes', icon: '🕐' },
  { id: '1h', name: '1 Hour', icon: '🕑' },
  { id: '4h', name: '4 Hours', icon: '🕓' },
  { id: '1d', name: '1 Day', icon: '📅' }
];

// Date range presets
const DATE_PRESETS = [
  { days: 7, label: 'Last 7 days' },
  { days: 14, label: 'Last 14 days' },
  { days: 30, label: 'Last 30 days' },
  { days: 60, label: 'Last 60 days' },
  { days: 90, label: 'Last 90 days' }
];

const BacktestingPage = () => {
  // Available options (fetched from backend)
  const [availableAssets, setAvailableAssets] = useState({ forex: [], crypto: [], stocks: [] });
  const [availableStrategies, setAvailableStrategies] = useState([]);
  
  // Configuration state
  const [config, setConfig] = useState({
    strategies: ['hybrid'],
    assets: ['EURUSD'],
    timeframes: ['1h'],
    days: 30,
    initial_balance: 1000,
    trade_amount: 10,
    payout_rate: 85
  });
  
  // Results state
  const [results, setResults] = useState([]);
  const [summary, setSummary] = useState(null);
  const [backtestHistory, setBacktestHistory] = useState([]);
  
  // UI state
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('configure');
  const [expandedCategories, setExpandedCategories] = useState({ forex: true, crypto: false, stocks: false });
  
  // Fetch available options on mount
  useEffect(() => {
    fetchAvailableOptions();
    fetchBacktestHistory();
  }, []);
  
  const fetchAvailableOptions = async () => {
    try {
      const [assetsRes, strategiesRes] = await Promise.all([
        axios.get(`${API}/backtest/assets`),
        axios.get(`${API}/backtest/strategies`)
      ]);
      
      if (assetsRes.data.success) {
        setAvailableAssets(assetsRes.data.assets);
      }
      if (strategiesRes.data.success) {
        setAvailableStrategies(strategiesRes.data.strategies);
      }
    } catch (error) {
      console.error('Error fetching options:', error);
    } finally {
      setIsLoading(false);
    }
  };
  
  const fetchBacktestHistory = async () => {
    try {
      const response = await axios.get(`${API}/backtest/history`);
      setBacktestHistory(response.data.results || []);
    } catch (error) {
      console.error('Error fetching history:', error);
    }
  };
  
  // Toggle strategy selection
  const toggleStrategy = (strategyId) => {
    setConfig(prev => ({
      ...prev,
      strategies: prev.strategies.includes(strategyId)
        ? prev.strategies.filter(s => s !== strategyId)
        : [...prev.strategies, strategyId]
    }));
  };
  
  // Toggle asset selection
  const toggleAsset = (asset) => {
    setConfig(prev => ({
      ...prev,
      assets: prev.assets.includes(asset)
        ? prev.assets.filter(a => a !== asset)
        : [...prev.assets, asset]
    }));
  };
  
  // Toggle timeframe selection
  const toggleTimeframe = (tf) => {
    setConfig(prev => ({
      ...prev,
      timeframes: prev.timeframes.includes(tf)
        ? prev.timeframes.filter(t => t !== tf)
        : [...prev.timeframes, tf]
    }));
  };
  
  // Select all assets in category
  const selectAllInCategory = (category) => {
    const assets = availableAssets[category] || [];
    setConfig(prev => ({
      ...prev,
      assets: [...new Set([...prev.assets, ...assets])]
    }));
  };
  
  // Clear assets in category
  const clearCategory = (category) => {
    const assets = availableAssets[category] || [];
    setConfig(prev => ({
      ...prev,
      assets: prev.assets.filter(a => !assets.includes(a))
    }));
  };
  
  // Run backtest
  const runBacktest = async () => {
    if (config.strategies.length === 0) {
      toast.error('Please select at least one strategy');
      return;
    }
    if (config.assets.length === 0) {
      toast.error('Please select at least one asset');
      return;
    }
    if (config.timeframes.length === 0) {
      toast.error('Please select at least one timeframe');
      return;
    }
    
    setIsRunning(true);
    setProgress(0);
    setResults([]);
    setSummary(null);
    
    // Estimate total tests
    const totalTests = config.strategies.length * config.assets.length * config.timeframes.length;
    toast.info(`Running ${totalTests} backtests... This may take a moment.`);
    
    // Simulate progress
    const progressInterval = setInterval(() => {
      setProgress(prev => Math.min(prev + 5, 90));
    }, 500);
    
    try {
      const response = await axios.post(`${API}/backtest/comprehensive`, {
        strategies: config.strategies,
        assets: config.assets,
        timeframes: config.timeframes,
        days: config.days,
        initial_balance: config.initial_balance,
        trade_amount: config.trade_amount,
        payout_rate: config.payout_rate / 100
      });
      
      clearInterval(progressInterval);
      setProgress(100);
      
      if (response.data.success) {
        setResults(response.data.results);
        setSummary(response.data.summary);
        toast.success(`✅ Backtest complete! ${response.data.summary.total_backtests} results generated.`);
        setActiveTab('results');
        fetchBacktestHistory();
      } else {
        toast.error(response.data.error || 'Backtest failed');
      }
    } catch (error) {
      clearInterval(progressInterval);
      console.error('Error running backtest:', error);
      toast.error('Failed to run backtest');
    } finally {
      setIsRunning(false);
    }
  };
  
  // Clear history
  const clearHistory = async () => {
    if (!window.confirm('Are you sure you want to clear all backtest history?')) return;
    
    try {
      await axios.delete(`${API}/backtest/clear`);
      setBacktestHistory([]);
      toast.success('History cleared');
    } catch (error) {
      toast.error('Failed to clear history');
    }
  };
  
  // Export results as JSON
  const exportResults = () => {
    const data = JSON.stringify({ results, summary, config }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_results_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    toast.success('Results exported');
  };
  
  // Get color based on win rate
  const getWinRateColor = (winRate) => {
    if (winRate >= 70) return 'text-green-400';
    if (winRate >= 55) return 'text-yellow-400';
    return 'text-red-400';
  };
  
  const getWinRateBg = (winRate) => {
    if (winRate >= 70) return 'bg-green-500/20 border-green-500/30';
    if (winRate >= 55) return 'bg-yellow-500/20 border-yellow-500/30';
    return 'bg-red-500/20 border-red-500/30';
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <History className="w-8 h-8 text-purple-400" />
            Strategy Backtesting
          </h1>
          <p className="text-slate-400 mt-1">Test strategies against historical market data (up to 90 days)</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className="bg-green-500/20 text-green-400">
            <Activity className="w-3 h-3 mr-1" />
            Yahoo Finance + CryptoCompare
          </Badge>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="bg-slate-800/50">
          <TabsTrigger value="configure">⚙️ Configure</TabsTrigger>
          <TabsTrigger value="results" disabled={results.length === 0}>
            📊 Results ({results.length})
          </TabsTrigger>
          <TabsTrigger value="history">📜 History ({backtestHistory.length})</TabsTrigger>
        </TabsList>

        {/* Configure Tab */}
        <TabsContent value="configure" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Strategy Selection */}
            <Card className="glass-dark border-slate-700/50">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Target className="w-5 h-5" />
                  Strategies
                </CardTitle>
                <CardDescription>Select strategies to backtest ({config.strategies.length} selected)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 max-h-80 overflow-y-auto">
                {availableStrategies.map(strategy => (
                  <label
                    key={strategy.id}
                    className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                      config.strategies.includes(strategy.id)
                        ? 'bg-purple-500/20 border border-purple-500/30'
                        : 'bg-slate-800/30 border border-transparent hover:bg-slate-800/50'
                    }`}
                  >
                    <Checkbox
                      checked={config.strategies.includes(strategy.id)}
                      onCheckedChange={() => toggleStrategy(strategy.id)}
                    />
                    <div>
                      <p className="text-white font-medium">{strategy.name}</p>
                      <p className="text-xs text-slate-400">{strategy.description}</p>
                    </div>
                  </label>
                ))}
              </CardContent>
            </Card>

            {/* Asset Selection */}
            <Card className="glass-dark border-slate-700/50">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Assets
                </CardTitle>
                <CardDescription>Select assets to test ({config.assets.length} selected)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 max-h-80 overflow-y-auto">
                {Object.entries(availableAssets).map(([category, assets]) => (
                  <div key={category} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <button
                        onClick={() => setExpandedCategories(prev => ({ ...prev, [category]: !prev[category] }))}
                        className="flex items-center gap-2 text-white font-medium"
                      >
                        <span>{category === 'forex' ? '💱' : category === 'crypto' ? '₿' : '📈'}</span>
                        <span className="capitalize">{category}</span>
                        <Badge className="bg-slate-700 text-xs">{assets.length}</Badge>
                        <span className="text-slate-400">{expandedCategories[category] ? '▼' : '▶'}</span>
                      </button>
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" className="text-xs h-6 px-2" onClick={() => selectAllInCategory(category)}>
                          All
                        </Button>
                        <Button size="sm" variant="ghost" className="text-xs h-6 px-2" onClick={() => clearCategory(category)}>
                          Clear
                        </Button>
                      </div>
                    </div>
                    {expandedCategories[category] && (
                      <div className="grid grid-cols-2 gap-1 pl-6">
                        {assets.map(asset => (
                          <label
                            key={asset}
                            className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm ${
                              config.assets.includes(asset)
                                ? 'bg-purple-500/20 text-purple-300'
                                : 'text-slate-400 hover:bg-slate-800/50'
                            }`}
                          >
                            <Checkbox
                              checked={config.assets.includes(asset)}
                              onCheckedChange={() => toggleAsset(asset)}
                            />
                            <span>{asset}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Timeframe & Settings */}
            <Card className="glass-dark border-slate-700/50">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  Timeframes & Settings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Timeframes */}
                <div>
                  <Label className="text-slate-300 mb-2 block">Timeframes</Label>
                  <div className="grid grid-cols-4 gap-2">
                    {TIMEFRAMES.map(tf => (
                      <button
                        key={tf.id}
                        onClick={() => toggleTimeframe(tf.id)}
                        className={`p-2 rounded text-center text-sm transition-all ${
                          config.timeframes.includes(tf.id)
                            ? 'bg-purple-500/20 border border-purple-500/30 text-purple-300'
                            : 'bg-slate-800/30 border border-slate-700 text-slate-400 hover:border-slate-600'
                        }`}
                      >
                        <span className="text-lg">{tf.icon}</span>
                        <p className="text-xs mt-1">{tf.id}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Date Range */}
                <div>
                  <Label className="text-slate-300 mb-2 block">Historical Period: {config.days} days</Label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {DATE_PRESETS.map(preset => (
                      <Button
                        key={preset.days}
                        size="sm"
                        variant={config.days === preset.days ? "default" : "outline"}
                        className={config.days === preset.days ? 'bg-purple-500' : 'border-slate-600'}
                        onClick={() => setConfig(prev => ({ ...prev, days: preset.days }))}
                      >
                        {preset.label}
                      </Button>
                    ))}
                  </div>
                  <Slider
                    value={[config.days]}
                    onValueChange={([v]) => setConfig(prev => ({ ...prev, days: v }))}
                    min={7}
                    max={90}
                    className="mt-2"
                  />
                </div>

                {/* Trading Parameters */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-300 text-sm">Initial Balance ($)</Label>
                    <Input
                      type="number"
                      value={config.initial_balance}
                      onChange={(e) => setConfig(prev => ({ ...prev, initial_balance: parseFloat(e.target.value) || 1000 }))}
                      className="bg-slate-800/50 border-slate-600 mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-slate-300 text-sm">Trade Amount ($)</Label>
                    <Input
                      type="number"
                      value={config.trade_amount}
                      onChange={(e) => setConfig(prev => ({ ...prev, trade_amount: parseFloat(e.target.value) || 10 }))}
                      className="bg-slate-800/50 border-slate-600 mt-1"
                    />
                  </div>
                </div>

                <div>
                  <Label className="text-slate-300 text-sm">Payout Rate: {config.payout_rate}%</Label>
                  <Slider
                    value={[config.payout_rate]}
                    onValueChange={([v]) => setConfig(prev => ({ ...prev, payout_rate: v }))}
                    min={70}
                    max={95}
                    className="mt-2"
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Run Button */}
          <Card className="glass-dark border-purple-500/30">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white font-medium">
                    Ready to backtest {config.strategies.length} strategies × {config.assets.length} assets × {config.timeframes.length} timeframes
                  </p>
                  <p className="text-slate-400 text-sm">
                    = {config.strategies.length * config.assets.length * config.timeframes.length} total backtests over {config.days} days
                  </p>
                </div>
                <Button
                  onClick={runBacktest}
                  disabled={isRunning}
                  className="bg-purple-500 hover:bg-purple-600 px-8"
                >
                  {isRunning ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Running...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      Run Backtest
                    </>
                  )}
                </Button>
              </div>
              
              {isRunning && (
                <div className="mt-4">
                  <Progress value={progress} className="h-2" />
                  <p className="text-slate-400 text-sm mt-2">Fetching historical data and simulating trades...</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Results Tab */}
        <TabsContent value="results" className="space-y-6">
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Card className="glass-dark border-slate-700/50">
                <CardContent className="p-4 text-center">
                  <p className="text-slate-400 text-sm">Total Backtests</p>
                  <p className="text-2xl font-bold text-white">{summary.total_backtests}</p>
                </CardContent>
              </Card>
              <Card className="glass-dark border-slate-700/50">
                <CardContent className="p-4 text-center">
                  <p className="text-slate-400 text-sm">Trades Simulated</p>
                  <p className="text-2xl font-bold text-white">{summary.total_trades_simulated}</p>
                </CardContent>
              </Card>
              <Card className="glass-dark border-slate-700/50">
                <CardContent className="p-4 text-center">
                  <p className="text-slate-400 text-sm">Avg Win Rate</p>
                  <p className={`text-2xl font-bold ${getWinRateColor(summary.average_win_rate)}`}>
                    {summary.average_win_rate}%
                  </p>
                </CardContent>
              </Card>
              <Card className="glass-dark border-slate-700/50">
                <CardContent className="p-4 text-center">
                  <p className="text-slate-400 text-sm">Best Strategy</p>
                  <p className="text-lg font-bold text-purple-400">{summary.best_performer?.replace(/_/g, ' ')}</p>
                </CardContent>
              </Card>
              <Card className="glass-dark border-slate-700/50">
                <CardContent className="p-4 text-center">
                  <p className="text-slate-400 text-sm">Best Win Rate</p>
                  <p className={`text-2xl font-bold ${getWinRateColor(summary.best_win_rate)}`}>
                    {summary.best_win_rate}%
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline" className="border-slate-600" onClick={exportResults}>
              <Download className="w-4 h-4 mr-2" />
              Export Results
            </Button>
          </div>

          {/* Results Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.sort((a, b) => b.win_rate - a.win_rate).map((result, idx) => (
              <Card key={idx} className={`glass-dark border ${getWinRateBg(result.win_rate)}`}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-white font-medium">{result.strategy?.replace(/_/g, ' ')}</p>
                      <p className="text-slate-400 text-sm">{result.asset} • {result.timeframe}</p>
                    </div>
                    <Badge className={getWinRateBg(result.win_rate)}>
                      {result.win_rate?.toFixed(1)}%
                    </Badge>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-2 text-center mb-3">
                    <div>
                      <p className="text-slate-400 text-xs">Trades</p>
                      <p className="text-white font-bold">{result.total_trades}</p>
                    </div>
                    <div>
                      <p className="text-slate-400 text-xs">Wins</p>
                      <p className="text-green-400 font-bold">{result.winning_trades}</p>
                    </div>
                    <div>
                      <p className="text-slate-400 text-xs">Losses</p>
                      <p className="text-red-400 font-bold">{result.losing_trades}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between text-sm border-t border-slate-700/50 pt-3">
                    <span className="text-slate-400">ROI</span>
                    <span className={result.roi >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {result.roi >= 0 ? '+' : ''}{result.roi?.toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Profit</span>
                    <span className={result.total_profit >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {result.total_profit >= 0 ? '+' : ''}${result.total_profit?.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Max Drawdown</span>
                    <span className="text-red-400">-{result.max_drawdown?.toFixed(2)}%</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-slate-400">Previous backtest results</p>
            <div className="flex gap-2">
              <Button variant="outline" className="border-slate-600" onClick={fetchBacktestHistory}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <Button variant="outline" className="border-red-500/30 text-red-400" onClick={clearHistory}>
                <Trash2 className="w-4 h-4 mr-2" />
                Clear All
              </Button>
            </div>
          </div>

          {backtestHistory.length === 0 ? (
            <Card className="glass-dark border-slate-700/50">
              <CardContent className="p-12 text-center">
                <History className="w-12 h-12 mx-auto mb-3 text-slate-500" />
                <p className="text-white font-medium">No backtest history</p>
                <p className="text-slate-400 text-sm">Run a backtest to see results here</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {backtestHistory.map((result, idx) => (
                <Card key={idx} className="glass-dark border-slate-700/50">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <Badge className={getWinRateBg(result.win_rate)}>
                          {result.win_rate?.toFixed(1)}% Win
                        </Badge>
                        <div>
                          <p className="text-white font-medium">
                            {result.strategy?.replace(/_/g, ' ')} • {result.asset} • {result.timeframe}
                          </p>
                          <p className="text-slate-400 text-sm">
                            {result.total_trades} trades • {new Date(result.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold ${result.total_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {result.total_profit >= 0 ? '+' : ''}${result.total_profit?.toFixed(2)}
                        </p>
                        <p className="text-slate-400 text-sm">ROI: {result.roi?.toFixed(2)}%</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default BacktestingPage;
