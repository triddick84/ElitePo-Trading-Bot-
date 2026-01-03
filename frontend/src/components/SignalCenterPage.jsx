/**
 * Signal Center Page
 * 
 * Centralized page for all signal generation and history:
 * - Manual Signal Generation
 * - Auto Signal Generation Settings
 * - Recent Signal History
 * - Signal Filters and Quick Actions
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Alert, AlertDescription } from './ui/alert';
import { toast } from 'sonner';
import { 
  Zap, Play, Square, RefreshCw, Filter, Clock, TrendingUp, TrendingDown,
  CheckCircle, XCircle, AlertTriangle, BarChart3, Target, Search,
  Trash2, Download, ArrowUp, ArrowDown, Activity
} from 'lucide-react';
import MarketAssetSelector from './MarketAssetSelector';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Available Timeframes
const TIMEFRAMES = ['1m', '2m', '3m', '5m', '15m', '30m', '1h'];

// Available Strategies for Signal Generation
const SIGNAL_STRATEGIES = [
  { id: 'enhanced_rsi_bb_volume', name: 'Enhanced RSI + BB + Volume' },
  { id: 'macd_crossover', name: 'MACD Crossover' },
  { id: 'ema_crossover', name: 'EMA Crossover' },
  { id: 'rsi_reversal', name: 'RSI Reversal' },
  { id: 'bollinger_squeeze', name: 'Bollinger Squeeze' },
  { id: 'support_resistance', name: 'Support/Resistance' },
  { id: 'auto_select', name: 'Auto Select Best' }
];

const SignalCenterPage = () => {
  // Generation Settings
  const [genSettings, setGenSettings] = useState({
    selected_assets: [],
    timeframe: '1m',
    strategy: 'enhanced_rsi_bb_volume',
    min_confidence: 75,
    expiration: '1m'
  });
  
  // Auto Generation Settings
  const [autoSettings, setAutoSettings] = useState({
    enabled: false,
    interval_seconds: 60,
    scan_all_assets: false,
    min_payout: 80,
    max_signals_per_scan: 5
  });
  
  // Signal State
  const [signals, setSignals] = useState([]);
  const [filteredSignals, setFilteredSignals] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanCount, setScanCount] = useState(0);
  
  // Filter State
  const [filters, setFilters] = useState({
    direction: 'all', // 'all', 'call', 'put'
    minConfidence: 0,
    asset: '',
    timeRange: 'all' // 'all', '1h', '24h'
  });
  
  // Statistics
  const [stats, setStats] = useState({
    total: 0,
    calls: 0,
    puts: 0,
    avg_confidence: 0,
    win_rate: 0
  });
  
  // Loading
  const [isLoading, setIsLoading] = useState(true);
  
  // Fetch data on mount
  useEffect(() => {
    fetchSignals();
    fetchStats();
    const interval = setInterval(fetchSignals, 10000);
    return () => clearInterval(interval);
  }, []);
  
  // Apply filters when signals or filters change
  useEffect(() => {
    applyFilters();
  }, [signals, filters]);
  
  const fetchSignals = async () => {
    try {
      const response = await axios.get(`${API}/signals/recent?limit=100`);
      setSignals(response.data.signals || response.data || []);
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching signals:', error);
      setIsLoading(false);
    }
  };
  
  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/signals/statistics`);
      setStats(response.data || {});
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };
  
  const applyFilters = () => {
    let filtered = [...signals];
    
    // Direction filter
    if (filters.direction !== 'all') {
      filtered = filtered.filter(s => s.direction?.toLowerCase() === filters.direction);
    }
    
    // Confidence filter
    if (filters.minConfidence > 0) {
      filtered = filtered.filter(s => (s.confidence || s.probability || 0) >= filters.minConfidence);
    }
    
    // Asset filter
    if (filters.asset) {
      filtered = filtered.filter(s => 
        s.asset?.toLowerCase().includes(filters.asset.toLowerCase()) ||
        s.symbol?.toLowerCase().includes(filters.asset.toLowerCase())
      );
    }
    
    // Time range filter
    if (filters.timeRange !== 'all') {
      const now = new Date();
      const hours = filters.timeRange === '1h' ? 1 : 24;
      const cutoff = new Date(now.getTime() - hours * 60 * 60 * 1000);
      filtered = filtered.filter(s => new Date(s.timestamp || s.created_at) >= cutoff);
    }
    
    setFilteredSignals(filtered);
  };
  
  // Generate single signal
  const handleGenerateSignal = async () => {
    if (genSettings.selected_assets.length === 0) {
      toast.error('Please select at least one asset');
      return;
    }
    
    setIsGenerating(true);
    try {
      const asset = genSettings.selected_assets[0];
      const [symbol, market] = asset.includes('_') ? asset.split('_') : [asset, 'regular'];
      
      const response = await axios.post(`${API}/signals/force-generate`, {
        asset_symbol: symbol,
        market_type: market,
        selected_timeframe: genSettings.timeframe,
        selected_strategy: genSettings.strategy
      });
      
      if (response.data.success && response.data.signal) {
        setSignals(prev => [response.data.signal, ...prev]);
        toast.success(`✅ ${response.data.signal.direction?.toUpperCase()} signal generated for ${symbol}`);
      } else {
        toast.warning(response.data.message || 'No signal generated - conditions not met');
      }
    } catch (error) {
      console.error('Error generating signal:', error);
      toast.error('Failed to generate signal');
    } finally {
      setIsGenerating(false);
    }
  };
  
  // Generate for multiple assets
  const handleBulkGenerate = async () => {
    if (genSettings.selected_assets.length === 0) {
      toast.error('Please select assets');
      return;
    }
    
    setIsGenerating(true);
    let generated = 0;
    
    for (const asset of genSettings.selected_assets.slice(0, 5)) {
      try {
        const [symbol, market] = asset.includes('_') ? asset.split('_') : [asset, 'regular'];
        
        const response = await axios.post(`${API}/signals/force-generate`, {
          asset_symbol: symbol,
          market_type: market,
          selected_timeframe: genSettings.timeframe,
          selected_strategy: genSettings.strategy
        });
        
        if (response.data.success && response.data.signal) {
          setSignals(prev => [response.data.signal, ...prev]);
          generated++;
        }
      } catch (error) {
        console.error(`Error generating for ${asset}:`, error);
      }
    }
    
    setIsGenerating(false);
    toast.success(`Generated ${generated} signals`);
  };
  
  // Auto scan toggle
  const handleToggleAutoScan = async () => {
    if (isScanning) {
      setIsScanning(false);
      toast.info('Auto-scanning stopped');
      return;
    }
    
    setIsScanning(true);
    setScanCount(0);
    toast.info('Starting auto-scan...');
    
    const scan = async () => {
      if (!isScanning) return;
      
      try {
        const params = new URLSearchParams({
          scan_all_assets: autoSettings.scan_all_assets,
          min_payout: autoSettings.min_payout,
          max_signals: autoSettings.max_signals_per_scan
        });
        
        const response = await axios.post(`${API}/signals/auto-generate/enhanced?${params.toString()}`);
        
        if (response.data.success && response.data.signals?.length > 0) {
          setSignals(prev => [...response.data.signals, ...prev]);
          toast.success(`Found ${response.data.signals.length} signals`);
        }
        
        setScanCount(prev => prev + 1);
      } catch (error) {
        console.error('Scan error:', error);
      }
    };
    
    // Initial scan
    await scan();
    
    // Set up interval
    const intervalId = setInterval(scan, autoSettings.interval_seconds * 1000);
    
    // Store interval ID for cleanup
    return () => clearInterval(intervalId);
  };
  
  // Clear all signals
  const handleClearSignals = async () => {
    try {
      await axios.delete(`${API}/signals/clear-all`);
      setSignals([]);
      toast.success('All signals cleared');
    } catch (error) {
      toast.error('Failed to clear signals');
    }
  };
  
  // Export signals
  const handleExportSignals = () => {
    const data = JSON.stringify(filteredSignals, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `signals_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    toast.success('Signals exported');
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
            <Zap className="w-8 h-8 text-yellow-400" />
            Signal Center
          </h1>
          <p className="text-slate-400 mt-1">Generate and manage trading signals</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className="bg-slate-700 text-white">
            {filteredSignals.length} signals
          </Badge>
          {isScanning && (
            <Badge className="bg-green-500/20 text-green-400 animate-pulse">
              <Activity className="w-3 h-3 mr-1" />
              Scanning ({scanCount})
            </Badge>
          )}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-slate-400 text-sm">Total Signals</p>
            <p className="text-2xl font-bold text-white">{filteredSignals.length}</p>
          </CardContent>
        </Card>
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-slate-400 text-sm">CALL Signals</p>
            <p className="text-2xl font-bold text-green-400">
              {filteredSignals.filter(s => s.direction?.toLowerCase() === 'call').length}
            </p>
          </CardContent>
        </Card>
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-slate-400 text-sm">PUT Signals</p>
            <p className="text-2xl font-bold text-red-400">
              {filteredSignals.filter(s => s.direction?.toLowerCase() === 'put').length}
            </p>
          </CardContent>
        </Card>
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-slate-400 text-sm">Avg Confidence</p>
            <p className="text-2xl font-bold text-purple-400">
              {filteredSignals.length > 0 
                ? (filteredSignals.reduce((acc, s) => acc + (s.confidence || s.probability || 0), 0) / filteredSignals.length).toFixed(1)
                : 0}%
            </p>
          </CardContent>
        </Card>
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-slate-400 text-sm">Win Rate</p>
            <p className="text-2xl font-bold text-white">{stats.win_rate?.toFixed(1) || 0}%</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signal Generation Panel */}
        <div className="lg:col-span-1 space-y-4">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-white flex items-center gap-2">
                <Play className="w-5 h-5" />
                Generate Signals
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Asset Selection */}
              <div>
                <Label className="text-slate-300 mb-2 block">Select Assets</Label>
                <MarketAssetSelector
                  selectedAssets={genSettings.selected_assets}
                  onSelectionChange={(assets) => setGenSettings(prev => ({ ...prev, selected_assets: assets }))}
                  maxSelection={10}
                />
              </div>
              
              {/* Timeframe */}
              <div>
                <Label>Timeframe</Label>
                <Select 
                  value={genSettings.timeframe}
                  onValueChange={(v) => setGenSettings(prev => ({ ...prev, timeframe: v }))}
                >
                  <SelectTrigger className="bg-slate-800/50 border-slate-600 mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-600">
                    {TIMEFRAMES.map(tf => (
                      <SelectItem key={tf} value={tf}>{tf}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Strategy */}
              <div>
                <Label>Strategy</Label>
                <Select 
                  value={genSettings.strategy}
                  onValueChange={(v) => setGenSettings(prev => ({ ...prev, strategy: v }))}
                >
                  <SelectTrigger className="bg-slate-800/50 border-slate-600 mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-600">
                    {SIGNAL_STRATEGIES.map(s => (
                      <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Generate Buttons */}
              <div className="flex gap-2 pt-2">
                <Button
                  onClick={handleGenerateSignal}
                  disabled={isGenerating || genSettings.selected_assets.length === 0}
                  className="flex-1 bg-purple-500 hover:bg-purple-600"
                >
                  {isGenerating ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Zap className="w-4 h-4 mr-2" />
                  )}
                  Generate
                </Button>
                <Button
                  onClick={handleBulkGenerate}
                  disabled={isGenerating || genSettings.selected_assets.length === 0}
                  variant="outline"
                  className="border-slate-600"
                >
                  Bulk ({genSettings.selected_assets.length})
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Auto Scan Settings */}
          <Card className="glass-dark border-slate-700/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-white flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Auto Scan
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>Scan All Assets</Label>
                <Switch
                  checked={autoSettings.scan_all_assets}
                  onCheckedChange={(v) => setAutoSettings(prev => ({ ...prev, scan_all_assets: v }))}
                />
              </div>
              
              <div>
                <Label>Scan Interval: {autoSettings.interval_seconds}s</Label>
                <Slider
                  value={[autoSettings.interval_seconds]}
                  onValueChange={([v]) => setAutoSettings(prev => ({ ...prev, interval_seconds: v }))}
                  min={30}
                  max={300}
                  step={10}
                  className="mt-2"
                />
              </div>
              
              <div>
                <Label>Min Payout: {autoSettings.min_payout}%</Label>
                <Slider
                  value={[autoSettings.min_payout]}
                  onValueChange={([v]) => setAutoSettings(prev => ({ ...prev, min_payout: v }))}
                  min={60}
                  max={95}
                  className="mt-2"
                />
              </div>
              
              <Button
                onClick={handleToggleAutoScan}
                className={isScanning ? 'bg-red-500 hover:bg-red-600 w-full' : 'bg-green-500 hover:bg-green-600 w-full'}
              >
                {isScanning ? (
                  <>
                    <Square className="w-4 h-4 mr-2" />
                    Stop Scanning
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Start Auto Scan
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Signal List */}
        <div className="lg:col-span-2">
          <Card className="glass-dark border-slate-700/50 h-full">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-white">Recent Signals</CardTitle>
                <div className="flex items-center gap-2">
                  <Button onClick={fetchSignals} variant="ghost" size="sm">
                    <RefreshCw className="w-4 h-4" />
                  </Button>
                  <Button onClick={handleExportSignals} variant="ghost" size="sm">
                    <Download className="w-4 h-4" />
                  </Button>
                  <Button onClick={handleClearSignals} variant="ghost" size="sm" className="text-red-400">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              
              {/* Filters */}
              <div className="flex flex-wrap gap-3 mt-3">
                <Select 
                  value={filters.direction}
                  onValueChange={(v) => setFilters(prev => ({ ...prev, direction: v }))}
                >
                  <SelectTrigger className="w-28 bg-slate-800/50 border-slate-600 h-8 text-sm">
                    <SelectValue placeholder="Direction" />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-600">
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="call">CALL</SelectItem>
                    <SelectItem value="put">PUT</SelectItem>
                  </SelectContent>
                </Select>
                
                <Select 
                  value={filters.timeRange}
                  onValueChange={(v) => setFilters(prev => ({ ...prev, timeRange: v }))}
                >
                  <SelectTrigger className="w-28 bg-slate-800/50 border-slate-600 h-8 text-sm">
                    <SelectValue placeholder="Time" />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-600">
                    <SelectItem value="all">All Time</SelectItem>
                    <SelectItem value="1h">Last Hour</SelectItem>
                    <SelectItem value="24h">Last 24h</SelectItem>
                  </SelectContent>
                </Select>
                
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-2 top-2 text-slate-400" />
                  <Input
                    placeholder="Filter asset..."
                    value={filters.asset}
                    onChange={(e) => setFilters(prev => ({ ...prev, asset: e.target.value }))}
                    className="pl-8 h-8 w-36 bg-slate-800/50 border-slate-600 text-sm"
                  />
                </div>
                
                <div className="flex items-center gap-2">
                  <Label className="text-xs text-slate-400">Min:</Label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={filters.minConfidence || ''}
                    onChange={(e) => setFilters(prev => ({ ...prev, minConfidence: parseInt(e.target.value) || 0 }))}
                    className="h-8 w-16 bg-slate-800/50 border-slate-600 text-sm"
                  />
                  <Label className="text-xs text-slate-400">%</Label>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {filteredSignals.length === 0 ? (
                  <div className="text-center py-12 text-slate-400">
                    <Zap className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No signals yet</p>
                    <p className="text-sm">Generate some signals to get started</p>
                  </div>
                ) : (
                  filteredSignals.map((signal, idx) => (
                    <div 
                      key={signal.id || idx}
                      className={`p-4 rounded-lg border-l-4 bg-slate-800/30 ${
                        signal.direction?.toLowerCase() === 'call' 
                          ? 'border-l-green-500' 
                          : 'border-l-red-500'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Badge className={
                            signal.direction?.toLowerCase() === 'call'
                              ? 'bg-green-500/20 text-green-400'
                              : 'bg-red-500/20 text-red-400'
                          }>
                            {signal.direction?.toLowerCase() === 'call' ? (
                              <ArrowUp className="w-3 h-3 mr-1" />
                            ) : (
                              <ArrowDown className="w-3 h-3 mr-1" />
                            )}
                            {signal.direction?.toUpperCase()}
                          </Badge>
                          <div>
                            <p className="font-medium text-white">{signal.asset || signal.symbol}</p>
                            <p className="text-xs text-slate-400">
                              {signal.strategy?.replace(/_/g, ' ')} • {signal.timeframe || '1m'}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="font-bold text-purple-400">
                            {(signal.confidence || signal.probability || 0).toFixed(1)}%
                          </p>
                          <p className="text-xs text-slate-500">
                            {new Date(signal.timestamp || signal.created_at).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                      {signal.entry_price && (
                        <div className="mt-2 flex gap-4 text-xs text-slate-400">
                          <span>Entry: ${signal.entry_price?.toFixed(5)}</span>
                          {signal.expiration && <span>Exp: {signal.expiration}</span>}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default SignalCenterPage;
