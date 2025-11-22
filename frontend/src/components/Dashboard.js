import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import LiveSignalsDisplay from './LiveSignalsDisplay';
import AssetSelectorDropdown from './AssetSelectorDropdown';
import MarketAssetSelector from './MarketAssetSelector';
import ChartConfiguration from './ChartConfiguration';
import LatencyAdjustment from './LatencyAdjustment';
import AccountModeToggle from './AccountModeToggle';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = ({ botStatus, liveSignals, setLiveSignals, notificationSettings, setNotificationSettings }) => {
  const [marketData, setMarketData] = useState(null);
  const [recentSignals, setRecentSignals] = useState([]);
  const [performanceData, setPerformanceData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [config, setConfig] = useState({
    selected_assets: [],
    selected_timeframes: [],
    invert_signals: false,
    chart_type: 'japanese_candles',
    chart_timeframe: '15s',
    signal_timeframe: '5s'
  });
  const [showAssetSelector, setShowAssetSelector] = useState(false);
  
  // Flexible Trading System State
  const [flexibleConfig, setFlexibleConfig] = useState({
    asset_symbol: 'EURUSD',
    market_type: 'regular', // regular or otc
    chart_timeframe: '30s',
    trade_duration_seconds: 82, // 1m 22s
    force_signal: false, // Force signal generation
    sma_fast: 6,
    sma_slow: 12,
    supertrend_atr_period: 2,
    supertrend_multiplier: 2.2,
    ao_short_period: 6,
    ao_long_period: 12
  });
  const [flexibleLoading, setFlexibleLoading] = useState(false);
  const [flexibleResult, setFlexibleResult] = useState(null);

  const handleSignalExecute = (signal) => {
    console.log("Executing signal from dashboard:", signal);
    // Here you could integrate with platform trading APIs
  };
  
  const handleFlexibleGenerate = async () => {
    setFlexibleLoading(true);
    setFlexibleResult(null);
    try {
      const response = await axios.post(`${API}/signals/flexible-generate`, flexibleConfig);
      setFlexibleResult(response.data);
      
      // Add signal to live signals if successful
      if (response.data.success && response.data.signal) {
        setLiveSignals(prev => [response.data.signal, ...prev]);
      }
    } catch (error) {
      console.error('Error generating flexible signal:', error);
      setFlexibleResult({
        success: false,
        message: error.response?.data?.detail || 'Failed to generate signal'
      });
    } finally {
      setFlexibleLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    fetchConfiguration();
    const interval = setInterval(fetchDashboardData, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchConfiguration = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      setConfig({
        selected_assets: response.data.selected_assets || [],
        selected_timeframes: response.data.selected_timeframes || [],
        invert_signals: response.data.invert_signals || false,
        chart_type: response.data.chart_type || 'japanese_candles',
        chart_timeframe: response.data.chart_timeframe || '15s',
        signal_timeframe: response.data.signal_timeframe || '5s'
      });
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const handleAssetsChange = async (assets) => {
    setConfig(prev => ({ ...prev, selected_assets: assets }));
    // Update backend config
    try {
      await axios.put(`${API}/config`, { selected_assets: assets });
    } catch (error) {
      console.error('Error updating assets:', error);
    }
  };

  const handleTimeframesChange = async (timeframes) => {
    setConfig(prev => ({ ...prev, selected_timeframes: timeframes }));
    // Update backend config
    try {
      await axios.put(`${API}/config`, { selected_timeframes: timeframes });
    } catch (error) {
      console.error('Error updating timeframes:', error);
    }
  };

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

      {/* Market Asset & Timeframe Selector */}
      <MarketAssetSelector 
        onSelectionChange={(selection) => {
          setConfig(prev => ({
            ...prev,
            selected_assets: selection.assets,
            selected_timeframes: selection.timeframes
          }));
        }}
      />

      {/* Chart Configuration */}
      <ChartConfiguration 
        onConfigChange={(chartConfig) => {
          setConfig(prev => ({
            ...prev,
            chart_type: chartConfig.chartType,
            chart_timeframe: chartConfig.chartTimeframe,
            signal_timeframe: chartConfig.signalTimeframe
          }));
        }}
      />

      {/* Latency Adjustment - Prominent placement for easy access */}
      <LatencyAdjustment compact={true} />

      {/* Flexible Trading System */}
      <Card className="p-6 glass-dark border-purple-500/30">
        <div className="mb-6">
          <h3 className="text-xl font-bold text-white mb-2 flex items-center">
            <span className="mr-2">🎯</span>
            Flexible Trading System
          </h3>
          <p className="text-slate-400 text-sm">
            Customize chart timeframe, trade duration, and indicator parameters independently
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Asset Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Trading Asset
            </label>
            <select
              value={flexibleConfig.asset_symbol}
              onChange={(e) => setFlexibleConfig({...flexibleConfig, asset_symbol: e.target.value})}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-md text-white focus:outline-none focus:border-purple-500"
            >
              {/* FOREX - Major Pairs */}
              <optgroup label="💱 FOREX - Major Pairs">
                <option value="EURUSD">EUR/USD - Euro vs US Dollar</option>
                <option value="GBPUSD">GBP/USD - British Pound vs US Dollar</option>
                <option value="USDJPY">USD/JPY - US Dollar vs Japanese Yen</option>
                <option value="AUDUSD">AUD/USD - Australian Dollar vs US Dollar</option>
                <option value="USDCHF">USD/CHF - US Dollar vs Swiss Franc</option>
                <option value="USDCAD">USD/CAD - US Dollar vs Canadian Dollar</option>
                <option value="NZDUSD">NZD/USD - New Zealand Dollar vs US Dollar</option>
              </optgroup>

              {/* FOREX - Minor Pairs */}
              <optgroup label="💱 FOREX - Minor Pairs">
                <option value="EURGBP">EUR/GBP - Euro vs British Pound</option>
                <option value="EURJPY">EUR/JPY - Euro vs Japanese Yen</option>
                <option value="EURCHF">EUR/CHF - Euro vs Swiss Franc</option>
                <option value="EURCAD">EUR/CAD - Euro vs Canadian Dollar</option>
                <option value="EURAUD">EUR/AUD - Euro vs Australian Dollar</option>
                <option value="GBPJPY">GBP/JPY - British Pound vs Japanese Yen</option>
                <option value="GBPCHF">GBP/CHF - British Pound vs Swiss Franc</option>
                <option value="GBPCAD">GBP/CAD - British Pound vs Canadian Dollar</option>
                <option value="CHFJPY">CHF/JPY - Swiss Franc vs Japanese Yen</option>
                <option value="CADJPY">CAD/JPY - Canadian Dollar vs Japanese Yen</option>
                <option value="AUDJPY">AUD/JPY - Australian Dollar vs Japanese Yen</option>
                <option value="AUDCHF">AUD/CHF - Australian Dollar vs Swiss Franc</option>
                <option value="NZDJPY">NZD/JPY - New Zealand Dollar vs Japanese Yen</option>
              </optgroup>

              {/* FOREX - Exotic Pairs */}
              <optgroup label="💱 FOREX - Exotic Pairs">
                <option value="USDMXN">USD/MXN - US Dollar vs Mexican Peso</option>
                <option value="USDBRL">USD/BRL - US Dollar vs Brazilian Real</option>
                <option value="USDTRY">USD/TRY - US Dollar vs Turkish Lira</option>
                <option value="USDZAR">USD/ZAR - US Dollar vs South African Rand</option>
                <option value="USDPLN">USD/PLN - US Dollar vs Polish Zloty</option>
                <option value="USDSGD">USD/SGD - US Dollar vs Singapore Dollar</option>
                <option value="USDHKD">USD/HKD - US Dollar vs Hong Kong Dollar</option>
                <option value="USDTHB">USD/THB - US Dollar vs Thai Baht</option>
                <option value="USDSEK">USD/SEK - US Dollar vs Swedish Krona</option>
                <option value="USDNOK">USD/NOK - US Dollar vs Norwegian Krone</option>
              </optgroup>

              {/* CRYPTO - Major */}
              <optgroup label="₿ CRYPTO - Major">
                <option value="BTCUSD">BTC/USD - Bitcoin vs US Dollar</option>
                <option value="ETHUSD">ETH/USD - Ethereum vs US Dollar</option>
                <option value="LTCUSD">LTC/USD - Litecoin vs US Dollar</option>
                <option value="ADAUSD">ADA/USD - Cardano vs US Dollar</option>
                <option value="DOTUSD">DOT/USD - Polkadot vs US Dollar</option>
                <option value="BNBUSD">BNB/USD - Binance Coin vs US Dollar</option>
              </optgroup>

              {/* CRYPTO - Popular Altcoins */}
              <optgroup label="₿ CRYPTO - Popular Altcoins">
                <option value="DOGEUSD">DOGE/USD - Dogecoin vs US Dollar</option>
                <option value="SOLUSD">SOL/USD - Solana vs US Dollar</option>
                <option value="AVAXUSD">AVAX/USD - Avalanche vs US Dollar</option>
                <option value="MATICUSD">MATIC/USD - Polygon vs US Dollar</option>
                <option value="LINKUSD">LINK/USD - Chainlink vs US Dollar</option>
                <option value="TONUSD">TON/USD - Toncoin vs US Dollar</option>
                <option value="ATOMUSD">ATOM/USD - Cosmos vs US Dollar</option>
                <option value="NEARUSD">NEAR/USD - NEAR Protocol vs US Dollar</option>
                <option value="APTOUSD">APTO/USD - Aptos vs US Dollar</option>
                <option value="OPUSD">OP/USD - Optimism vs US Dollar</option>
                <option value="ARBUSD">ARB/USD - Arbitrum vs US Dollar</option>
              </optgroup>

              {/* CRYPTO - DeFi & Meme */}
              <optgroup label="₿ CRYPTO - DeFi & Meme">
                <option value="UNIUSD">UNI/USD - Uniswap vs US Dollar</option>
                <option value="AAVEUSD">AAVE/USD - Aave vs US Dollar</option>
                <option value="SHIBUSDT">SHIB/USD - Shiba Inu vs US Dollar</option>
                <option value="FLOKIUSD">FLOKI/USD - Floki vs US Dollar</option>
              </optgroup>

              {/* STOCKS - Tech Giants */}
              <optgroup label="📈 STOCKS - Tech Giants">
                <option value="AAPL">AAPL - Apple Inc.</option>
                <option value="MSFT">MSFT - Microsoft Corp.</option>
                <option value="GOOGL">GOOGL - Alphabet Inc.</option>
                <option value="AMZN">AMZN - Amazon.com Inc.</option>
                <option value="TSLA">TSLA - Tesla Inc.</option>
                <option value="META">META - Meta Platforms Inc.</option>
                <option value="NFLX">NFLX - Netflix Inc.</option>
                <option value="NVDA">NVDA - NVIDIA Corp.</option>
                <option value="BABA">BABA - Alibaba Group</option>
              </optgroup>

              {/* STOCKS - Financial */}
              <optgroup label="📈 STOCKS - Financial">
                <option value="JPM">JPM - JPMorgan Chase</option>
                <option value="BAC">BAC - Bank of America</option>
                <option value="WFC">WFC - Wells Fargo</option>
                <option value="GS">GS - Goldman Sachs</option>
                <option value="MS">MS - Morgan Stanley</option>
              </optgroup>

              {/* STOCKS - Consumer & Other */}
              <optgroup label="📈 STOCKS - Consumer & Industrial">
                <option value="MCD">MCD - McDonald's Corp.</option>
                <option value="KO">KO - Coca-Cola Co.</option>
                <option value="WMT">WMT - Walmart Inc.</option>
                <option value="BA">BA - Boeing Co.</option>
                <option value="CAT">CAT - Caterpillar Inc.</option>
                <option value="JNJ">JNJ - Johnson & Johnson</option>
                <option value="PFE">PFE - Pfizer Inc.</option>
              </optgroup>

              {/* COMMODITIES */}
              <optgroup label="🥇 COMMODITIES">
                <option value="XAUUSD">XAU/USD - Gold Spot</option>
                <option value="XAGUSD">XAG/USD - Silver Spot</option>
                <option value="BRENTOIL">BRENT - Brent Oil</option>
                <option value="WTIUSD">WTI - Crude Oil</option>
                <option value="NATGAS">NATGAS - Natural Gas</option>
                <option value="XPTUSD">XPT/USD - Platinum</option>
                <option value="XPDUSD">XPD/USD - Palladium</option>
              </optgroup>

              {/* INDICES - US */}
              <optgroup label="📊 INDICES - US">
                <option value="US100">US100 - NASDAQ 100</option>
                <option value="US30">US30 - Dow Jones</option>
                <option value="SPX500">SPX500 - S&P 500</option>
                <option value="US2000">US2000 - Russell 2000</option>
              </optgroup>

              {/* INDICES - European */}
              <optgroup label="📊 INDICES - European">
                <option value="GER40">GER40 - DAX (Germany)</option>
                <option value="UK100">UK100 - FTSE 100 (UK)</option>
                <option value="FRA40">FRA40 - CAC 40 (France)</option>
                <option value="ESP35">ESP35 - IBEX 35 (Spain)</option>
                <option value="ITA40">ITA40 - FTSE MIB (Italy)</option>
                <option value="E35EUR">E35EUR - EuroStoxx 35</option>
              </optgroup>

              {/* INDICES - Asia Pacific */}
              <optgroup label="📊 INDICES - Asia Pacific">
                <option value="JPN225">JPN225 - Nikkei 225 (Japan)</option>
                <option value="HK50">HK50 - Hang Seng (Hong Kong)</option>
                <option value="CHINA50">CHINA50 - China A50</option>
                <option value="AUS200">AUS200 - ASX 200 (Australia)</option>
              </optgroup>
            </select>
          </div>

          {/* Market Type Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Market Type
            </label>
            <select
              value={flexibleConfig.market_type}
              onChange={(e) => setFlexibleConfig({...flexibleConfig, market_type: e.target.value})}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-md text-white focus:outline-none focus:border-purple-500"
            >
              <option value="regular">🔵 Regular Market</option>
              <option value="otc">🟢 OTC Market (24/7)</option>
            </select>
            <p className="text-xs text-slate-500 mt-1">
              {flexibleConfig.market_type === 'otc' ? '24/7 Trading Available' : 'Standard Trading Hours'}
            </p>
          </div>

          {/* Chart Timeframe */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Chart Timeframe (Data Analysis)
            </label>
            <select
              value={flexibleConfig.chart_timeframe}
              onChange={(e) => setFlexibleConfig({...flexibleConfig, chart_timeframe: e.target.value})}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-md text-white focus:outline-none focus:border-purple-500"
            >
              <option value="5s">5 seconds</option>
              <option value="10s">10 seconds</option>
              <option value="15s">15 seconds</option>
              <option value="30s">30 seconds</option>
              <option value="1m">1 minute</option>
              <option value="2m">2 minutes</option>
              <option value="3m">3 minutes</option>
              <option value="5m">5 minutes</option>
            </select>
          </div>

          {/* Trade Duration */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Trade Duration (seconds)
            </label>
            <input
              type="number"
              min="5"
              max="3600"
              value={flexibleConfig.trade_duration_seconds}
              onChange={(e) => setFlexibleConfig({...flexibleConfig, trade_duration_seconds: parseInt(e.target.value)})}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-md text-white focus:outline-none focus:border-purple-500"
              placeholder="e.g., 82 for 1m 22s"
            />
            <p className="text-xs text-slate-500 mt-1">
              {Math.floor(flexibleConfig.trade_duration_seconds / 60)}m {flexibleConfig.trade_duration_seconds % 60}s
            </p>
          </div>
        </div>

        {/* Indicator Parameters */}
        <div className="mt-6 p-4 bg-slate-800/30 rounded-lg border border-slate-700/50">
          <h4 className="text-sm font-semibold text-purple-400 mb-4 flex items-center">
            <span className="mr-2">⚙️</span>
            Customizable Indicator Parameters
          </h4>
          
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Fast SMA</label>
              <input
                type="number"
                min="1"
                max="50"
                value={flexibleConfig.sma_fast}
                onChange={(e) => setFlexibleConfig({...flexibleConfig, sma_fast: parseInt(e.target.value)})}
                className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
            
            <div>
              <label className="block text-xs text-slate-400 mb-1">Slow SMA</label>
              <input
                type="number"
                min="1"
                max="100"
                value={flexibleConfig.sma_slow}
                onChange={(e) => setFlexibleConfig({...flexibleConfig, sma_slow: parseInt(e.target.value)})}
                className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
            
            <div>
              <label className="block text-xs text-slate-400 mb-1">ST ATR Period</label>
              <input
                type="number"
                min="1"
                max="50"
                value={flexibleConfig.supertrend_atr_period}
                onChange={(e) => setFlexibleConfig({...flexibleConfig, supertrend_atr_period: parseInt(e.target.value)})}
                className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
            
            <div>
              <label className="block text-xs text-slate-400 mb-1">ST Multiplier</label>
              <input
                type="number"
                min="0.1"
                max="10"
                step="0.1"
                value={flexibleConfig.supertrend_multiplier}
                onChange={(e) => setFlexibleConfig({...flexibleConfig, supertrend_multiplier: parseFloat(e.target.value)})}
                className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
            
            <div>
              <label className="block text-xs text-slate-400 mb-1">AO Short</label>
              <input
                type="number"
                min="1"
                max="50"
                value={flexibleConfig.ao_short_period}
                onChange={(e) => setFlexibleConfig({...flexibleConfig, ao_short_period: parseInt(e.target.value)})}
                className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
            
            <div>
              <label className="block text-xs text-slate-400 mb-1">AO Long</label>
              <input
                type="number"
                min="1"
                max="100"
                value={flexibleConfig.ao_long_period}
                onChange={(e) => setFlexibleConfig({...flexibleConfig, ao_long_period: parseInt(e.target.value)})}
                className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>
        </div>

        {/* Force Signal Option */}
        <div className="mt-6 p-4 bg-slate-800/30 rounded-lg border border-slate-700/50">
          <label className="flex items-center space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={flexibleConfig.force_signal}
              onChange={(e) => setFlexibleConfig({...flexibleConfig, force_signal: e.target.checked})}
              className="w-5 h-5 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-2 focus:ring-purple-500 focus:ring-offset-0 cursor-pointer"
            />
            <div className="flex-1">
              <span className="text-sm font-medium text-slate-200">⚡ Force Signal Generation</span>
              <p className="text-xs text-slate-500 mt-1">
                Generate signal based on current market state even if strict conditions aren't met. Useful when no signals are generated in strict mode.
              </p>
            </div>
          </label>
        </div>

        {/* Generate Button */}
        <div className="mt-6 flex items-center justify-between">
          <div className="text-sm text-slate-400">
            <p>Strategy: Moving Average Crossover + SuperTrend + Awesome Oscillator</p>
            <p className="text-xs mt-1">
              Chart: <span className="text-purple-400 font-medium">{flexibleConfig.chart_timeframe}</span> | 
              Trade: <span className="text-purple-400 font-medium">{Math.floor(flexibleConfig.trade_duration_seconds / 60)}m {flexibleConfig.trade_duration_seconds % 60}s</span>
            </p>
          </div>
          
          <Button
            onClick={handleFlexibleGenerate}
            disabled={flexibleLoading}
            className="bg-purple-500 hover:bg-purple-600 text-white px-6 py-3 font-semibold"
          >
            {flexibleLoading ? '⏳ Generating...' : '🚀 Generate Signal'}
          </Button>
        </div>

        {/* Result Display */}
        {flexibleResult && (
          <div className={`mt-6 p-4 rounded-lg border ${
            flexibleResult.success 
              ? 'bg-green-500/10 border-green-500/30' 
              : 'bg-red-500/10 border-red-500/30'
          }`}>
            <p className={`font-medium ${flexibleResult.success ? 'text-green-400' : 'text-red-400'}`}>
              {flexibleResult.message}
            </p>
            {flexibleResult.success && flexibleResult.signal && (
              <div className="mt-3 space-y-2">
                <div className="flex items-center space-x-4">
                  <div className={`px-4 py-2 rounded-full font-bold ${
                    flexibleResult.signal.direction === 'CALL' 
                      ? 'bg-green-500/20 text-green-400' 
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {flexibleResult.signal.direction}
                  </div>
                  <div className="text-white">
                    <p className="font-semibold">{flexibleResult.signal.symbol}</p>
                    <p className="text-sm text-slate-400">
                      Confidence: {flexibleResult.signal.probability}% ({flexibleResult.signal.confidence_level})
                    </p>
                  </div>
                </div>
                <div className="text-sm text-slate-300 mt-2 p-3 bg-slate-800/50 rounded">
                  <p className="whitespace-pre-wrap">{flexibleResult.signal.justification}</p>
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Developer Credit */}
      <div className="mb-6 p-4 bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/30 rounded-lg">
        <div className="flex items-center justify-center space-x-2">
          <span className="text-2xl">👨‍💻</span>
          <p className="text-slate-300 text-sm">
            <span className="font-semibold text-purple-400">Created by</span>{' '}
            <span className="text-white font-bold">Thomas Riddick</span>{' '}
            <span className="text-slate-400">- Trader / Developer</span>
          </p>
          <span className="text-2xl">📈</span>
        </div>
      </div>

      {/* Invert Signals Warning Banner */}
      {config.invert_signals && (
        <div className="bg-orange-500/20 border-2 border-orange-500 rounded-lg p-4 mb-6">
          <div className="flex items-start space-x-3">
            <div className="text-2xl">🔄</div>
            <div className="flex-1">
              <h3 className="text-orange-400 font-bold text-lg">⚠️ SIGNAL INVERSION ACTIVE</h3>
              <p className="text-orange-300 text-sm mt-1">
                All signals are being inverted across ALL timeframes (5s, 15s, 1m, 3m, 5m, etc.)
              </p>
              <p className="text-orange-200 text-xs mt-2">
                • BUY signals → converted to SELL signals<br/>
                • SELL signals → converted to BUY signals<br/>
                • Applies to both regular and OTC markets
              </p>
              <p className="text-orange-400 text-xs mt-2 font-medium">
                To disable, go to Bot Controls and turn off "Invert Signals" toggle
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Live Signals Display - New Primary Section */}
      <LiveSignalsDisplay 
        botStatus={botStatus} 
        liveSignals={liveSignals}
        setLiveSignals={setLiveSignals}
        notificationSettings={notificationSettings}
        setNotificationSettings={setNotificationSettings}
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