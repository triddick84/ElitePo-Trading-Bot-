import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const RealtimeMarketDashboard = () => {
  const [selectedSymbols, setSelectedSymbols] = useState(['BTCUSD', 'ETHUSD', 'EURUSD', 'GBPUSD']);
  const [marketData, setMarketData] = useState({});
  const [analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(true);
  const [qualityReport, setQualityReport] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Popular symbols to choose from
  const availableSymbols = {
    'Crypto': ['BTCUSD', 'ETHUSD', 'BNBUSD', 'XRPUSD', 'ADAUSD', 'SOLUSD', 'DOTUSD', 'LTCUSD'],
    'Forex': ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 'USDCAD', 'NZDUSD'],
    'Stocks': ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'META', 'NVDA'],
  };

  useEffect(() => {
    fetchMarketData();
    const interval = autoRefresh ? setInterval(fetchMarketData, 5000) : null;
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [selectedSymbols, autoRefresh]);

  const fetchMarketData = async () => {
    try {
      const symbolsParam = selectedSymbols.join(',');
      const response = await axios.get(`${BACKEND_URL}/api/market/multi-symbol?symbols=${symbolsParam}`);
      
      if (response.data.success) {
        setMarketData(response.data.data);
      }
      
      // Fetch analytics for first symbol
      if (selectedSymbols.length > 0) {
        const analyticsResponse = await axios.get(`${BACKEND_URL}/api/market/analytics/${selectedSymbols[0]}`);
        if (analyticsResponse.data.success) {
          setAnalytics(analyticsResponse.data.analytics);
        }
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching market data:', error);
      setLoading(false);
    }
  };

  const fetchQualityReport = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/market/quality-report`);
      if (response.data.success) {
        setQualityReport(response.data.report);
        toast.success('Quality report updated');
      }
    } catch (error) {
      console.error('Error fetching quality report:', error);
      toast.error('Failed to fetch quality report');
    }
  };

  const getQualityColor = (quality) => {
    const colors = {
      'excellent': 'bg-green-500',
      'good': 'bg-blue-500',
      'fair': 'bg-yellow-500',
      'poor': 'bg-orange-500',
      'unavailable': 'bg-red-500'
    };
    return colors[quality] || 'bg-gray-500';
  };

  const getSourceBadgeColor = (source) => {
    const colors = {
      'binance': 'bg-yellow-500/20 text-yellow-400 border-yellow-500',
      'finnhub': 'bg-blue-500/20 text-blue-400 border-blue-500',
      'alpha_vantage': 'bg-purple-500/20 text-purple-400 border-purple-500'
    };
    return colors[source] || 'bg-gray-500/20 text-gray-400 border-gray-500';
  };

  const toggleSymbol = (symbol) => {
    if (selectedSymbols.includes(symbol)) {
      setSelectedSymbols(selectedSymbols.filter(s => s !== symbol));
    } else if (selectedSymbols.length < 8) {
      setSelectedSymbols([...selectedSymbols, symbol]);
    } else {
      toast.error('Maximum 8 symbols allowed');
    }
  };

  if (loading) {
    return (
      <Card className="w-full bg-slate-900 border-slate-700">
        <CardContent className="p-6">
          <div className="text-center text-slate-400">Loading real-time market data...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-2xl text-emerald-400">📡 Real-Time Market Data</CardTitle>
              <CardDescription className="text-slate-400 mt-2">
                Live market data from multiple sources - No simulated data
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => setAutoRefresh(!autoRefresh)}
                variant={autoRefresh ? "default" : "outline"}
                className={autoRefresh ? "bg-emerald-600" : ""}
              >
                {autoRefresh ? '⏸️ Pause' : '▶️ Resume'}
              </Button>
              <Button onClick={fetchQualityReport} variant="outline">
                📊 Quality Report
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Symbol Selector */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <CardTitle className="text-xl text-white">Select Symbols to Monitor</CardTitle>
        </CardHeader>
        <CardContent>
          {Object.entries(availableSymbols).map(([category, symbols]) => (
            <div key={category} className="mb-4">
              <h3 className="text-sm font-semibold text-slate-400 mb-2">{category}</h3>
              <div className="flex flex-wrap gap-2">
                {symbols.map(symbol => (
                  <Badge
                    key={symbol}
                    onClick={() => toggleSymbol(symbol)}
                    className={`cursor-pointer transition-all ${
                      selectedSymbols.includes(symbol)
                        ? 'bg-emerald-500 hover:bg-emerald-600'
                        : 'bg-slate-700 hover:bg-slate-600'
                    }`}
                  >
                    {symbol}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Live Price Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {selectedSymbols.map(symbol => {
          const data = marketData[symbol];
          if (!data || data.error) {
            return (
              <Card key={symbol} className="bg-slate-900 border-red-700">
                <CardHeader>
                  <CardTitle className="text-lg text-white">{symbol}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-red-400 text-sm">No data available</p>
                </CardContent>
              </Card>
            );
          }

          const priceChange = data.change || 0;
          const changePercent = data.change_percent || 0;

          return (
            <Card key={symbol} className="bg-slate-900 border-slate-700 hover:border-emerald-500 transition-all">
              <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                  <CardTitle className="text-lg text-white">{symbol}</CardTitle>
                  <div className="flex flex-col items-end gap-1">
                    <Badge variant="outline" className={getSourceBadgeColor(data.source)}>
                      {data.source}
                    </Badge>
                    {data.quality && (
                      <div className={`w-2 h-2 rounded-full ${getQualityColor(data.quality)}`} title={data.quality} />
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div>
                    <div className="text-3xl font-bold text-white">
                      {data.price?.toFixed(data.price < 10 ? 5 : 2) || 'N/A'}
                    </div>
                    {(priceChange !== 0 || changePercent !== 0) && (
                      <div className={`text-sm font-medium ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {priceChange >= 0 ? '↑' : '↓'} {Math.abs(priceChange).toFixed(4)} ({Math.abs(changePercent).toFixed(2)}%)
                      </div>
                    )}
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <div className="text-slate-500">Bid</div>
                      <div className="text-blue-400 font-medium">{data.bid?.toFixed(data.bid < 10 ? 5 : 2) || 'N/A'}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Ask</div>
                      <div className="text-orange-400 font-medium">{data.ask?.toFixed(data.ask < 10 ? 5 : 2) || 'N/A'}</div>
                    </div>
                  </div>
                  
                  {data.spread && (
                    <div className="text-xs text-slate-400">
                      Spread: {data.spread.toFixed(5)}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Market Analytics for Primary Symbol */}
      {analytics && analytics.price && (
        <Card className="bg-slate-900 border-slate-700">
          <CardHeader>
            <CardTitle className="text-xl text-white">
              📊 Market Analytics - {selectedSymbols[0]}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Technical Indicators */}
              <div>
                <h3 className="text-sm font-semibold text-slate-400 mb-3">Technical Indicators</h3>
                <div className="space-y-2">
                  {analytics.indicators?.rsi && (
                    <div className="flex justify-between">
                      <span className="text-slate-300">RSI (14)</span>
                      <span className={`font-medium ${
                        analytics.indicators.rsi > 70 ? 'text-red-400' :
                        analytics.indicators.rsi < 30 ? 'text-green-400' :
                        'text-yellow-400'
                      }`}>
                        {analytics.indicators.rsi.toFixed(2)}
                      </span>
                    </div>
                  )}
                  {analytics.indicators?.ma20 && (
                    <div className="flex justify-between">
                      <span className="text-slate-300">MA (20)</span>
                      <span className="text-blue-400 font-medium">{analytics.indicators.ma20.toFixed(5)}</span>
                    </div>
                  )}
                  {analytics.indicators?.atr && (
                    <div className="flex justify-between">
                      <span className="text-slate-300">ATR (14)</span>
                      <span className="text-purple-400 font-medium">{analytics.indicators.atr.toFixed(5)}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Volume Analysis */}
              <div>
                <h3 className="text-sm font-semibold text-slate-400 mb-3">Volume Analysis</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-slate-300">Current</span>
                    <span className="text-white font-medium">
                      {analytics.volume?.current?.toLocaleString() || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-300">Average</span>
                    <span className="text-slate-400 font-medium">
                      {analytics.volume?.average?.toLocaleString() || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-300">Signal</span>
                    <Badge className={
                      analytics.volume?.signal === 'high' ? 'bg-green-500/20 text-green-400' :
                      analytics.volume?.signal === 'low' ? 'bg-red-500/20 text-red-400' :
                      'bg-blue-500/20 text-blue-400'
                    }>
                      {analytics.volume?.signal || 'N/A'}
                    </Badge>
                  </div>
                </div>
              </div>

              {/* Trend Analysis */}
              <div>
                <h3 className="text-sm font-semibold text-slate-400 mb-3">Trend Analysis</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-slate-300">Direction</span>
                    <Badge className={
                      analytics.trend?.direction === 'bullish'
                        ? 'bg-green-500/20 text-green-400 border-green-500'
                        : 'bg-red-500/20 text-red-400 border-red-500'
                    }>
                      {analytics.trend?.direction === 'bullish' ? '📈 Bullish' : '📉 Bearish'}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-300">Strength</span>
                    <Badge variant="outline">
                      {analytics.trend?.strength || 'N/A'}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-300">Data Source</span>
                    <Badge variant="outline" className={getSourceBadgeColor(analytics.data_source)}>
                      {analytics.data_source}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quality Report Modal */}
      {qualityReport && (
        <Card className="bg-slate-900 border-emerald-700">
          <CardHeader>
            <CardTitle className="text-xl text-emerald-400">Data Quality Report</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-400 mb-2">API Usage</h3>
                <div className="grid grid-cols-3 gap-4">
                  {Object.entries(qualityReport.rate_limits).map(([source, limits]) => (
                    <div key={source} className="bg-slate-800 p-3 rounded-lg">
                      <div className="text-white font-medium capitalize">{source}</div>
                      <div className="text-sm text-slate-400 mt-1">
                        Used: {limits.used} / {limits.limit}
                      </div>
                      <div className="text-xs text-emerald-400 mt-1">
                        Remaining: {limits.remaining}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-slate-300">Cache Size</span>
                <Badge variant="outline">{qualityReport.cache_size} entries</Badge>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-slate-300">Total API Calls</span>
                <Badge className="bg-blue-500/20 text-blue-400">{qualityReport.total_api_calls}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default RealtimeMarketDashboard;
