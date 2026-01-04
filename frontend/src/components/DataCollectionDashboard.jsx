/**
 * Data Collection Dashboard Component
 * 
 * Provides UI for:
 * - Starting/stopping real market data collection
 * - Viewing collection statistics
 * - Training ML models with collected data
 * - Monitoring model performance
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { Progress } from './ui/progress';
import { toast } from 'sonner';
import {
  Database, Play, Pause, Brain, BarChart3, TrendingUp,
  Clock, CheckCircle, AlertTriangle, RefreshCw, Download,
  Activity, Zap, Target, Info, Settings
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Available assets for collection
const AVAILABLE_ASSETS = [
  'EURUSD_otc',
  'GBPUSD_otc',
  'USDJPY_otc',
  'AUDUSD_otc',
  'EURGBP_otc',
  'BTCUSD_otc',
  'ETHUSD_otc'
];

// Available timeframes
const AVAILABLE_TIMEFRAMES = ['5s', '1m', '5m', '15m'];

const DataCollectionDashboard = () => {
  // Collection State
  const [collectionStats, setCollectionStats] = useState(null);
  const [isCollecting, setIsCollecting] = useState(false);
  const [selectedAssets, setSelectedAssets] = useState(['EURUSD_otc']);
  const [selectedTimeframes, setSelectedTimeframes] = useState(['1m', '5s']);
  
  // Training State
  const [trainedModels, setTrainedModels] = useState({});
  const [trainingHistory, setTrainingHistory] = useState([]);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingAsset, setTrainingAsset] = useState('EURUSD_otc');
  const [trainingTimeframe, setTrainingTimeframe] = useState('1m');
  const [confidenceThreshold, setConfidenceThreshold] = useState([0.75]);
  
  // Loading
  const [isLoading, setIsLoading] = useState(true);

  // Fetch stats on mount and periodically
  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000); // Every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const [statsRes, modelsRes] = await Promise.all([
        axios.get(`${API}/data-collector/stats`),
        axios.get(`${API}/ml-trainer/models`)
      ]);
      
      if (statsRes.data.success) {
        setCollectionStats(statsRes.data.stats);
        setIsCollecting(statsRes.data.stats.collection_enabled);
      }
      
      if (modelsRes.data.success) {
        setTrainedModels(modelsRes.data.models || {});
        setTrainingHistory(modelsRes.data.training_history || []);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartCollection = async () => {
    try {
      const response = await axios.post(`${API}/data-collector/start`, {
        assets: selectedAssets,
        timeframes: selectedTimeframes
      });
      
      if (response.data.success) {
        setIsCollecting(true);
        toast.success('📊 Data collection started!');
      }
    } catch (error) {
      toast.error('Failed to start collection');
    }
  };

  const handleStopCollection = async () => {
    try {
      const response = await axios.post(`${API}/data-collector/stop`);
      
      if (response.data.success) {
        setIsCollecting(false);
        toast.success('Data collection stopped');
      }
    } catch (error) {
      toast.error('Failed to stop collection');
    }
  };

  const handleTrainModel = async () => {
    setIsTraining(true);
    
    try {
      const response = await axios.post(`${API}/ml-trainer/train`, {
        asset: trainingAsset,
        timeframe: trainingTimeframe,
        confidence_threshold: confidenceThreshold[0],
        min_samples: 500
      });
      
      if (response.data.success) {
        toast.success(`🎯 Model trained! Win rate: ${response.data.performance?.win_rate?.toFixed(1) || 'N/A'}%`);
        await fetchStats(); // Refresh stats
      } else {
        toast.error(response.data.error || 'Training failed');
      }
    } catch (error) {
      toast.error('Failed to train model');
    } finally {
      setIsTraining(false);
    }
  };

  const toggleAsset = (asset) => {
    setSelectedAssets(prev => 
      prev.includes(asset) 
        ? prev.filter(a => a !== asset)
        : [...prev, asset]
    );
  };

  const toggleTimeframe = (tf) => {
    setSelectedTimeframes(prev =>
      prev.includes(tf)
        ? prev.filter(t => t !== tf)
        : [...prev, tf]
    );
  };

  const formatNumber = (num) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num?.toString() || '0';
  };

  const getDatasetInfo = () => {
    if (!collectionStats?.database_stats) return [];
    
    return Object.entries(collectionStats.database_stats).map(([key, data]) => ({
      key,
      asset: data.asset,
      timeframe: data.timeframe,
      candles: data.total_candles,
      firstCandle: new Date(data.first_candle).toLocaleString(),
      lastCandle: new Date(data.last_candle).toLocaleString()
    }));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Alert for Real Data Importance */}
      <Alert className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-blue-500/30">
        <Info className="h-4 w-4" />
        <AlertTitle>Real Data = High Accuracy</AlertTitle>
        <AlertDescription>
          The key to achieving 90%+ win rate is training on REAL market data from Pocket Option. 
          Start the desktop client to collect data, or use the API to import historical data.
        </AlertDescription>
      </Alert>

      {/* Collection Status */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5" />
                Data Collection
              </CardTitle>
              <CardDescription>
                Collect real market data from Pocket Option for ML training
              </CardDescription>
            </div>
            <Badge 
              variant={isCollecting ? "default" : "secondary"}
              className={isCollecting ? "bg-green-500" : ""}
            >
              {isCollecting ? "● Collecting" : "○ Stopped"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Asset Selection */}
          <div>
            <Label className="mb-2 block">Assets to Collect</Label>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_ASSETS.map(asset => (
                <Button
                  key={asset}
                  size="sm"
                  variant={selectedAssets.includes(asset) ? "default" : "outline"}
                  onClick={() => toggleAsset(asset)}
                  className="text-xs"
                >
                  {asset.replace('_otc', '')}
                </Button>
              ))}
            </div>
          </div>

          {/* Timeframe Selection */}
          <div>
            <Label className="mb-2 block">Timeframes</Label>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_TIMEFRAMES.map(tf => (
                <Button
                  key={tf}
                  size="sm"
                  variant={selectedTimeframes.includes(tf) ? "default" : "outline"}
                  onClick={() => toggleTimeframe(tf)}
                  className="text-xs"
                >
                  {tf}
                </Button>
              ))}
            </div>
          </div>

          {/* Control Buttons */}
          <div className="flex gap-3">
            {!isCollecting ? (
              <Button onClick={handleStartCollection} className="bg-green-600 hover:bg-green-700">
                <Play className="w-4 h-4 mr-2" />
                Start Collection
              </Button>
            ) : (
              <Button onClick={handleStopCollection} variant="destructive">
                <Pause className="w-4 h-4 mr-2" />
                Stop Collection
              </Button>
            )}
            <Button variant="outline" onClick={fetchStats}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh Stats
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Collected Data Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Collected Data
          </CardTitle>
        </CardHeader>
        <CardContent>
          {getDatasetInfo().length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-3">Asset</th>
                    <th className="text-left py-2 px-3">Timeframe</th>
                    <th className="text-right py-2 px-3">Candles</th>
                    <th className="text-left py-2 px-3">First</th>
                    <th className="text-left py-2 px-3">Last</th>
                  </tr>
                </thead>
                <tbody>
                  {getDatasetInfo().map(item => (
                    <tr key={item.key} className="border-b hover:bg-muted/50">
                      <td className="py-2 px-3 font-medium">{item.asset}</td>
                      <td className="py-2 px-3">
                        <Badge variant="outline">{item.timeframe}</Badge>
                      </td>
                      <td className="py-2 px-3 text-right font-mono">
                        {formatNumber(item.candles)}
                      </td>
                      <td className="py-2 px-3 text-xs text-muted-foreground">
                        {item.firstCandle}
                      </td>
                      <td className="py-2 px-3 text-xs text-muted-foreground">
                        {item.lastCandle}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No data collected yet</p>
              <p className="text-sm">Start the desktop client or import historical data</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ML Training */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="w-5 h-5" />
            Train High-Accuracy Model
          </CardTitle>
          <CardDescription>
            Train ML models using collected real data for 80-90%+ win rate
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Asset Selection */}
            <div>
              <Label>Asset</Label>
              <Select value={trainingAsset} onValueChange={setTrainingAsset}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AVAILABLE_ASSETS.map(asset => (
                    <SelectItem key={asset} value={asset}>
                      {asset.replace('_otc', '')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Timeframe */}
            <div>
              <Label>Timeframe</Label>
              <Select value={trainingTimeframe} onValueChange={setTrainingTimeframe}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AVAILABLE_TIMEFRAMES.map(tf => (
                    <SelectItem key={tf} value={tf}>{tf}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Confidence Threshold */}
          <div>
            <div className="flex justify-between mb-2">
              <Label>Confidence Threshold</Label>
              <span className="text-sm font-medium">{(confidenceThreshold[0] * 100).toFixed(0)}%</span>
            </div>
            <Slider
              value={confidenceThreshold}
              onValueChange={setConfidenceThreshold}
              min={0.5}
              max={0.95}
              step={0.05}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Higher threshold = fewer signals but higher accuracy
            </p>
          </div>

          {/* Train Button */}
          <Button 
            onClick={handleTrainModel} 
            disabled={isTraining}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600"
          >
            {isTraining ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Training...
              </>
            ) : (
              <>
                <Zap className="w-4 h-4 mr-2" />
                Train Model
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Trained Models */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="w-5 h-5" />
            Trained Models
          </CardTitle>
        </CardHeader>
        <CardContent>
          {Object.keys(trainedModels).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(trainedModels).map(([key, model]) => (
                <div 
                  key={key}
                  className="p-3 rounded-lg border bg-muted/30 flex justify-between items-center"
                >
                  <div>
                    <div className="font-medium">{key}</div>
                    <div className="text-xs text-muted-foreground">
                      {model.loaded ? "✅ Loaded" : "📁 Saved"}
                    </div>
                  </div>
                  {model.performance && (
                    <div className="text-right">
                      <div className="text-lg font-bold text-green-500">
                        {model.performance.win_rate?.toFixed(1) || 'N/A'}%
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Win Rate
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-muted-foreground">
              <Brain className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p>No models trained yet</p>
              <p className="text-sm">Collect data first, then train a model</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Training History */}
      {trainingHistory.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" />
              Training History
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {trainingHistory.slice(-5).reverse().map((entry, idx) => (
                <div 
                  key={idx}
                  className="p-2 rounded border text-sm flex justify-between"
                >
                  <div>
                    <span className="font-medium">{entry.asset} {entry.timeframe}</span>
                    <span className="text-muted-foreground ml-2">
                      {entry.samples_used} samples
                    </span>
                  </div>
                  <div className="text-green-500 font-medium">
                    {entry.performance?.win_rate?.toFixed(1) || '?'}% win rate
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default DataCollectionDashboard;
