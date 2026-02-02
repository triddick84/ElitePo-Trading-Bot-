import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const BacktestPanel = () => {
  const [backtestConfig, setBacktestConfig] = useState({
    strategy: 'hybrid',
    symbol: 'EUR_USD',
    days: 30
  });
  
  const [backtestResults, setBacktestResults] = useState([]);
  const [currentResult, setCurrentResult] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchBacktestHistory();
  }, []);

  const fetchBacktestHistory = async () => {
    try {
      const response = await axios.get(`${API}/backtest/history`);
      setBacktestResults(response.data.results || []);
    } catch (error) {
      console.error('Error fetching backtest history:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const runBacktest = async () => {
    if (!backtestConfig.strategy || !backtestConfig.symbol) {
      toast.error('Please select strategy and symbol');
      return;
    }

    setIsRunning(true);
    try {
      const response = await axios.post(`${API}/backtest/run`, backtestConfig);
      setCurrentResult(response.data);
      toast.success('Backtest completed successfully!');
      fetchBacktestHistory(); // Refresh history
    } catch (error) {
      console.error('Error running backtest:', error);
      toast.error('Failed to run backtest');
    } finally {
      setIsRunning(false);
    }
  };

  const getPerformanceColor = (value, isPercentage = false) => {
    if (isPercentage) {
      if (value >= 70) return 'text-green-400';
      if (value >= 50) return 'text-yellow-400';
      return 'text-red-400';
    } else {
      if (value > 0) return 'text-green-400';
      if (value < 0) return 'text-red-400';
      return 'text-slate-400';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  const strategies = [
    { id: 'hybrid', name: 'Hybrid Strategy' },
    { id: 'cci_20', name: 'CCI 20' },
    { id: 'ema_crossover', name: 'EMA Crossover' },
    { id: 'rsi_5', name: 'RSI 5' },
    { id: 'macd_momentum', name: 'MACD Momentum' }
  ];

  const symbols = [
    'EUR_USD', 'GBP_USD', 'USD_JPY', 'USD_CHF', 'AUD_USD',
    'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT',
    'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN'
  ];

  const BacktestResultCard = ({ result, isMain = false }) => (
    <Card className={`p-6 glass-dark border-slate-700/50 ${isMain ? 'border-emerald-500/30' : ''}`}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="text-white font-semibold text-lg">
            {result.strategy.replace('_', ' ').toUpperCase()}
          </h4>
          <p className="text-slate-400">{result.symbol}</p>
        </div>
        <Badge className={`${
          result.win_rate >= 70 ? 'bg-green-500/20 text-green-400' : 
          result.win_rate >= 50 ? 'bg-yellow-500/20 text-yellow-400' : 
          'bg-red-500/20 text-red-400'
        }`}>
          {result.win_rate.toFixed(1)}% Win Rate
        </Badge>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="text-center">
          <p className="text-slate-400 text-sm">Total Signals</p>
          <p className="text-white font-bold text-xl">{result.total_signals}</p>
        </div>
        <div className="text-center">
          <p className="text-slate-400 text-sm">Wins</p>
          <p className="text-green-400 font-bold text-xl">{result.winning_signals}</p>
        </div>
        <div className="text-center">
          <p className="text-slate-400 text-sm">Losses</p>
          <p className="text-red-400 font-bold text-xl">{result.losing_signals}</p>
        </div>
        <div className="text-center">
          <p className="text-slate-400 text-sm">Profit Factor</p>
          <p className={`font-bold text-xl ${getPerformanceColor(result.profit_factor)}`}>
            {result.profit_factor.toFixed(2)}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm border-t border-slate-700/50 pt-4">
        <span className="text-slate-400">
          Period: {formatDate(result.start_date)} - {formatDate(result.end_date)}
        </span>
        <span className={`font-medium ${getPerformanceColor(result.total_return)}`}>
          Return: ${result.total_return.toFixed(2)}
        </span>
      </div>
    </Card>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card className="p-6 glass-dark border-slate-700/50">
          <div className="skeleton h-32 w-full rounded"></div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="backtest-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Strategy Backtesting</h2>
          <p className="text-slate-400">Test trading strategies against historical market data</p>
        </div>
        <Button 
          onClick={fetchBacktestHistory}
          className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
          data-testid="refresh-backtests"
        >
          🔄 Refresh
        </Button>
      </div>

      {/* Backtest Configuration */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <h3 className="text-xl font-semibold text-white mb-6">Run New Backtest</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6" data-testid="backtest-config">
          <div>
            <Label className="text-slate-300 font-medium mb-2 block">Strategy</Label>
            <Select 
              value={backtestConfig.strategy} 
              onValueChange={(value) => setBacktestConfig(prev => ({ ...prev, strategy: value }))}
            >
              <SelectTrigger className="bg-slate-800/50 border-slate-600 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-600">
                {strategies.map((strategy) => (
                  <SelectItem key={strategy.id} value={strategy.id}>
                    {strategy.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-slate-300 font-medium mb-2 block">Symbol</Label>
            <Select 
              value={backtestConfig.symbol} 
              onValueChange={(value) => setBacktestConfig(prev => ({ ...prev, symbol: value }))}
            >
              <SelectTrigger className="bg-slate-800/50 border-slate-600 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-600">
                {symbols.map((symbol) => (
                  <SelectItem key={symbol} value={symbol}>
                    {symbol}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-slate-300 font-medium mb-2 block">Days</Label>
            <Input
              type="number"
              value={backtestConfig.days}
              onChange={(e) => setBacktestConfig(prev => ({ ...prev, days: parseInt(e.target.value) }))}
              className="bg-slate-800/50 border-slate-600 text-white"
              min="7"
              max="365"
            />
          </div>

          <div className="flex items-end">
            <Button 
              onClick={runBacktest}
              disabled={isRunning}
              className="w-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 btn-glow"
              data-testid="run-backtest-btn"
            >
              {isRunning ? '⏳ Running...' : '🧪 Run Backtest'}
            </Button>
          </div>
        </div>
      </Card>

      {/* Current Backtest Result */}
      {currentResult && (
        <div className="space-y-4">
          <h3 className="text-xl font-semibold text-white">Latest Backtest Result</h3>
          <BacktestResultCard result={currentResult} isMain={true} />
        </div>
      )}

      {/* Backtest History */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold text-white">Backtest History</h3>
          <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
            {backtestResults.length} results
          </Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="backtest-history">
          {backtestResults.length === 0 ? (
            <Card className="lg:col-span-2 p-12 glass-dark border-slate-700/50 text-center">
              <div className="text-6xl mb-4">🧪</div>
              <h3 className="text-xl font-semibold text-white mb-2">No Backtest Results</h3>
              <p className="text-slate-400">
                Run your first backtest to see how strategies perform on historical data
              </p>
            </Card>
          ) : (
            backtestResults.map((result, index) => (
              <BacktestResultCard key={index} result={result} />
            ))
          )}
        </div>
      </div>

      {/* Performance Insights */}
      {backtestResults.length > 0 && (
        <Card className="p-6 glass-dark border-slate-700/50">
          <h3 className="text-xl font-semibold text-white mb-6">Performance Insights</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6" data-testid="performance-insights">
            <div className="text-center p-4 bg-slate-800/30 rounded-xl">
              <div className="text-3xl mb-2">🏆</div>
              <p className="text-slate-400 text-sm mb-1">Best Strategy</p>
              <p className="text-white font-bold">
                {backtestResults.reduce((best, current) => 
                  current.win_rate > best.win_rate ? current : best
                ).strategy.replace('_', ' ').toUpperCase()}
              </p>
            </div>
            
            <div className="text-center p-4 bg-slate-800/30 rounded-xl">
              <div className="text-3xl mb-2">📊</div>
              <p className="text-slate-400 text-sm mb-1">Avg Win Rate</p>
              <p className="text-white font-bold">
                {(backtestResults.reduce((sum, result) => sum + result.win_rate, 0) / backtestResults.length).toFixed(1)}%
              </p>
            </div>
            
            <div className="text-center p-4 bg-slate-800/30 rounded-xl">
              <div className="text-3xl mb-2">💰</div>
              <p className="text-slate-400 text-sm mb-1">Total Tested</p>
              <p className="text-white font-bold">
                {backtestResults.reduce((sum, result) => sum + result.total_signals, 0)} signals
              </p>
            </div>
          </div>

          <div className="mt-6 p-4 bg-slate-800/30 rounded-xl">
            <h4 className="text-white font-medium mb-3">💡 Recommendations</h4>
            <ul className="space-y-2 text-sm text-slate-300">
              <li>• Strategies with 70%+ win rates show consistent performance</li>
              <li>• Consider combining multiple high-performing strategies</li>
              <li>• Test strategies across different market conditions and timeframes</li>
              <li>• Monitor real-time performance vs. backtested results</li>
            </ul>
          </div>
        </Card>
      )}
    </div>
  );
};

export default BacktestPanel;