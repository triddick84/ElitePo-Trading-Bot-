/**
 * Data Collection Dashboard Component
 *
 * Provides UI for:
 * - Starting/stopping real market data collection
 * - Viewing collection statistics
 * - Training ML models with collected data
 * - Monitoring model performance
 *
 * v8.71.0 (Feb 27, 2026):
 *   Replaced the hardcoded 7-asset / 4-timeframe pickers with the full
 *   `/api/backtest/assets-universe` master list (366+ symbols across
 *   regular + OTC forex/commodities/crypto/indices/stocks). Adds per-class
 *   Select-All toggles plus a global Select-All across every asset class.
 *   Timeframes now reflect the union of regular + OTC timeframes
 *   (3s/5s/15s/30s/M1/M5/M15/M30/H1/H4/D1).
 */

import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { toast } from 'sonner';
import {
  Database, Play, Pause, Brain, BarChart3,
  Clock, RefreshCw, Activity, Zap, Target, Info,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Fallback when the backend universe endpoint is unreachable. Kept tiny
// so the UI is still usable in degraded mode.
const FALLBACK_CLASSES = [
  {
    id: 'forex_otc',
    label: 'Forex (OTC)',
    timeframes: ['5s', '1m', '5m', '15m'],
    symbols: ['EURUSD_OTC', 'GBPUSD_OTC', 'USDJPY_OTC', 'AUDUSD_OTC'],
  },
];

// Master timeframe order. Items not present in the universe are filtered out.
const TIMEFRAME_ORDER = ['3s', '5s', '15s', '30s', 'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'];

// Convert PO-style timeframe (M1/M5/H1) to collector-style (1m/5m/1h)
const tfToCollector = (tf) => {
  if (!tf) return tf;
  const m = String(tf).match(/^([Mm])(\d+)$/);
  if (m) return `${m[2]}m`;
  const h = String(tf).match(/^([Hh])(\d+)$/);
  if (h) return `${h[2]}h`;
  const d = String(tf).match(/^([Dd])(\d+)$/);
  if (d) return `${d[2]}d`;
  return tf.toLowerCase();
};

const DataCollectionDashboard = () => {
  // Universe loaded from backend
  const [universe, setUniverse] = useState({ classes: FALLBACK_CLASSES, loading: true });

  // Collection State
  const [collectionStats, setCollectionStats] = useState(null);
  const [isCollecting, setIsCollecting] = useState(false);
  const [selectedAssets, setSelectedAssets] = useState(new Set(['EURUSD_OTC']));
  const [selectedTimeframes, setSelectedTimeframes] = useState(new Set(['1m', '5s']));

  // Training State
  const [trainedModels, setTrainedModels] = useState({});
  const [trainingHistory, setTrainingHistory] = useState([]);
  const [isTraining, setIsTraining] = useState(false);
  const [trainingAsset, setTrainingAsset] = useState('EURUSD_OTC');
  const [trainingTimeframe, setTrainingTimeframe] = useState('1m');
  const [confidenceThreshold, setConfidenceThreshold] = useState([0.75]);

  // Iter 110 — fine-tuning state
  const [trainingDays, setTrainingDays] = useState([30]);
  const [lookaheadBars, setLookaheadBars] = useState([1]);
  const [testSize, setTestSize] = useState([0.2]);
  const [rfWeight, setRfWeight] = useState([0.5]);
  const [minSamples, setMinSamples] = useState([500]);
  const [featureGroups, setFeatureGroups] = useState({
    trend: true, momentum: true, volatility: true,
    price_action: true, divergence: true, support_resistance: true,
  });
  const [lastTrainingResult, setLastTrainingResult] = useState(null);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [isComparing, setIsComparing] = useState(false);

  // Loading
  const [isLoading, setIsLoading] = useState(true);

  // Load asset universe once on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/backtest/assets-universe`, { timeout: 10_000 });
        if (cancelled) return;
        if (r?.data?.success && Array.isArray(r.data.classes) && r.data.classes.length) {
          setUniverse({ classes: r.data.classes, loading: false });
        } else {
          setUniverse({ classes: FALLBACK_CLASSES, loading: false });
        }
      } catch (e) {
        if (!cancelled) {
          console.warn('Failed to load asset universe, using fallback:', e?.message);
          setUniverse({ classes: FALLBACK_CLASSES, loading: false });
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Derive all-symbols and all-timeframes
  const allSymbols = useMemo(() => {
    const set = new Set();
    universe.classes.forEach((cls) => (cls.symbols || []).forEach((s) => set.add(s)));
    return Array.from(set).sort();
  }, [universe]);

  const allTimeframes = useMemo(() => {
    const set = new Set();
    universe.classes.forEach((cls) => (cls.timeframes || []).forEach((t) => set.add(tfToCollector(t))));
    const ordered = TIMEFRAME_ORDER.map(tfToCollector).filter((t) => set.has(t));
    // Append any unknown timeframes at the end
    Array.from(set).forEach((t) => { if (!ordered.includes(t)) ordered.push(t); });
    return ordered;
  }, [universe]);

  // Fetch stats on mount and periodically
  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10_000);
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const [statsRes, modelsRes] = await Promise.all([
        axios.get(`${API}/data-collector/stats`).catch(() => null),
        axios.get(`${API}/ml-trainer/models`).catch(() => null),
      ]);

      if (statsRes?.data?.success) {
        setCollectionStats(statsRes.data.stats);
        setIsCollecting(!!statsRes.data.stats.collection_enabled);
      }

      if (modelsRes?.data?.success) {
        setTrainedModels(modelsRes.data.models || {});
        setTrainingHistory(modelsRes.data.training_history || []);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // ---- Selection helpers ---------------------------------------------------
  const toggleAsset = (asset) => {
    setSelectedAssets((prev) => {
      const next = new Set(prev);
      if (next.has(asset)) next.delete(asset); else next.add(asset);
      return next;
    });
  };

  const toggleTimeframe = (tf) => {
    setSelectedTimeframes((prev) => {
      const next = new Set(prev);
      if (next.has(tf)) next.delete(tf); else next.add(tf);
      return next;
    });
  };

  const selectAllAssetsGlobal = () => setSelectedAssets(new Set(allSymbols));
  const clearAllAssetsGlobal = () => setSelectedAssets(new Set());

  const selectClassAssets = (cls) => {
    setSelectedAssets((prev) => {
      const next = new Set(prev);
      (cls.symbols || []).forEach((s) => next.add(s));
      return next;
    });
  };

  const clearClassAssets = (cls) => {
    setSelectedAssets((prev) => {
      const next = new Set(prev);
      (cls.symbols || []).forEach((s) => next.delete(s));
      return next;
    });
  };

  const selectAllTimeframes = () => setSelectedTimeframes(new Set(allTimeframes));
  const clearAllTimeframes = () => setSelectedTimeframes(new Set());

  // ---- Actions -------------------------------------------------------------
  const handleStartCollection = async () => {
    if (selectedAssets.size === 0) {
      toast.error('Pick at least one asset before starting collection');
      return;
    }
    if (selectedTimeframes.size === 0) {
      toast.error('Pick at least one timeframe before starting collection');
      return;
    }
    try {
      const response = await axios.post(`${API}/data-collector/start`, {
        assets: Array.from(selectedAssets),
        timeframes: Array.from(selectedTimeframes),
      });
      if (response.data.success) {
        setIsCollecting(true);
        toast.success(`📊 Collection started — ${selectedAssets.size} assets × ${selectedTimeframes.size} timeframes`);
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
    setLastTrainingResult(null);
    try {
      const payload = {
        asset: trainingAsset,
        timeframe: trainingTimeframe,
        confidence_threshold: confidenceThreshold[0],
        min_samples: minSamples[0],
        // Iter 110 fine-tuning params
        days: trainingDays[0],
        lookahead: lookaheadBars[0],
        test_size: testSize[0],
        rf_weight: rfWeight[0],
        gb_weight: 1 - rfWeight[0],
        feature_groups: featureGroups,
      };
      const response = await axios.post(`${API}/ml-trainer/train`, payload);
      setLastTrainingResult(response.data);
      if (response.data.success) {
        toast.success(`🎯 Model trained! Win rate: ${response.data.performance?.win_rate?.toFixed(1) || 'N/A'}%`);
        await fetchStats();
      } else {
        toast.error(response.data.error || 'Training failed');
      }
    } catch (error) {
      toast.error(`Training error: ${error.message}`);
    } finally {
      setIsTraining(false);
    }
  };

  const handleCompareModels = async () => {
    setIsComparing(true);
    setComparisonResult(null);
    try {
      const payload = {
        asset: trainingAsset,
        timeframe: trainingTimeframe,
        confidence_threshold: confidenceThreshold[0],
        min_samples: minSamples[0],
        days: trainingDays[0],
        lookahead: lookaheadBars[0],
        test_size: testSize[0],
        feature_groups: featureGroups,
      };
      const response = await axios.post(`${API}/ml-trainer/train-comparison`, payload);
      setComparisonResult(response.data);
      if (response.data.success) {
        toast.success(`🏁 Comparison done — winner: ${response.data.best}`);
      } else {
        toast.error(response.data.error || 'Comparison failed');
      }
    } catch (error) {
      toast.error(`Comparison error: ${error.message}`);
    } finally {
      setIsComparing(false);
    }
  };

  const toggleFeatureGroup = (g) => {
    setFeatureGroups((prev) => ({ ...prev, [g]: !prev[g] }));
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
      lastCandle: new Date(data.last_candle).toLocaleString(),
    }));
  };

  if (isLoading || universe.loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="data-collection-loading">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="data-collection-dashboard">
      {/* Alert for Real Data Importance */}
      <Alert className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-blue-500/30">
        <Info className="h-4 w-4" />
        <AlertTitle>Real Data = High Accuracy</AlertTitle>
        <AlertDescription>
          The key to achieving 90%+ win rate is training on REAL market data. Pick the asset classes
          and timeframes you want to collect — the universe below covers every regular and OTC asset
          PO exposes ({allSymbols.length} symbols, {allTimeframes.length} timeframes).
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
              variant={isCollecting ? 'default' : 'secondary'}
              className={isCollecting ? 'bg-green-500' : ''}
              data-testid="collection-status-badge"
            >
              {isCollecting ? '● Collecting' : '○ Stopped'}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Global Select All / Clear */}
          <div className="flex flex-wrap items-center gap-2 pb-2 border-b border-slate-700/50">
            <span className="text-xs text-muted-foreground mr-2">
              Selected: <strong>{selectedAssets.size}</strong> assets · <strong>{selectedTimeframes.size}</strong> TFs
            </span>
            <Button size="sm" variant="secondary" onClick={selectAllAssetsGlobal} data-testid="select-all-assets-btn">
              ✓ Select ALL assets ({allSymbols.length})
            </Button>
            <Button size="sm" variant="outline" onClick={clearAllAssetsGlobal} data-testid="clear-all-assets-btn">
              Clear assets
            </Button>
            <Button size="sm" variant="secondary" onClick={selectAllTimeframes} data-testid="select-all-tfs-btn">
              ✓ Select ALL timeframes ({allTimeframes.length})
            </Button>
            <Button size="sm" variant="outline" onClick={clearAllTimeframes} data-testid="clear-all-tfs-btn">
              Clear timeframes
            </Button>
          </div>

          {/* Asset Selection — grouped by class */}
          <div>
            <Label className="mb-2 block">Assets to Collect</Label>
            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1" data-testid="asset-classes-list">
              {universe.classes.map((cls) => {
                const symbols = cls.symbols || [];
                const selectedInClass = symbols.filter((s) => selectedAssets.has(s)).length;
                return (
                  <div key={cls.id} className="rounded-md border border-slate-700/50 p-3 bg-slate-800/20">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{cls.label}</span>
                        <Badge variant="outline" className="text-[10px]">
                          {selectedInClass}/{symbols.length}
                        </Badge>
                      </div>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 text-[11px] px-2"
                          onClick={() => selectClassAssets(cls)}
                          data-testid={`select-class-${cls.id}-btn`}
                        >
                          + All
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 text-[11px] px-2"
                          onClick={() => clearClassAssets(cls)}
                          data-testid={`clear-class-${cls.id}-btn`}
                        >
                          − Clear
                        </Button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {symbols.map((sym) => (
                        <Button
                          key={sym}
                          size="sm"
                          variant={selectedAssets.has(sym) ? 'default' : 'outline'}
                          onClick={() => toggleAsset(sym)}
                          className="text-[11px] h-6 px-2"
                          data-testid={`asset-pill-${sym}`}
                        >
                          {sym.replace('_OTC', '·OTC').replace('_otc', '·OTC')}
                        </Button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Timeframe Selection */}
          <div>
            <Label className="mb-2 block">Timeframes</Label>
            <div className="flex flex-wrap gap-2" data-testid="timeframe-list">
              {allTimeframes.map((tf) => (
                <Button
                  key={tf}
                  size="sm"
                  variant={selectedTimeframes.has(tf) ? 'default' : 'outline'}
                  onClick={() => toggleTimeframe(tf)}
                  className="text-xs"
                  data-testid={`tf-pill-${tf}`}
                >
                  {tf}
                </Button>
              ))}
            </div>
          </div>

          {/* Control Buttons */}
          <div className="flex gap-3">
            {!isCollecting ? (
              <Button
                onClick={handleStartCollection}
                className="bg-green-600 hover:bg-green-700"
                data-testid="start-collection-btn"
              >
                <Play className="w-4 h-4 mr-2" />
                Start Collection
              </Button>
            ) : (
              <Button onClick={handleStopCollection} variant="destructive" data-testid="stop-collection-btn">
                <Pause className="w-4 h-4 mr-2" />
                Stop Collection
              </Button>
            )}
            <Button variant="outline" onClick={fetchStats} data-testid="refresh-stats-btn">
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
                  {getDatasetInfo().map((item) => (
                    <tr key={item.key} className="border-b hover:bg-muted/50">
                      <td className="py-2 px-3 font-medium">{item.asset}</td>
                      <td className="py-2 px-3">
                        <Badge variant="outline">{item.timeframe}</Badge>
                      </td>
                      <td className="py-2 px-3 text-right font-mono">{formatNumber(item.candles)}</td>
                      <td className="py-2 px-3 text-xs text-muted-foreground">{item.firstCandle}</td>
                      <td className="py-2 px-3 text-xs text-muted-foreground">{item.lastCandle}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No data collected yet</p>
              <p className="text-sm">Pick assets + timeframes above, then click <em>Start Collection</em>.</p>
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
            Train ML models using collected real data for 80–90%+ win rate
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Asset Selection */}
            <div>
              <Label>Asset</Label>
              <Select value={trainingAsset} onValueChange={setTrainingAsset}>
                <SelectTrigger data-testid="training-asset-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-80">
                  {allSymbols.map((asset) => (
                    <SelectItem key={asset} value={asset}>
                      {asset.replace('_OTC', ' · OTC').replace('_otc', ' · OTC')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Timeframe */}
            <div>
              <Label>Timeframe</Label>
              <Select value={trainingTimeframe} onValueChange={setTrainingTimeframe}>
                <SelectTrigger data-testid="training-tf-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {allTimeframes.map((tf) => (
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
              data-testid="conf-slider"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Higher threshold = fewer signals but higher accuracy
            </p>
          </div>

          {/* Iter 110 — Fine-tuning grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3 border-t border-slate-700/50">
            <div>
              <div className="flex justify-between mb-2">
                <Label>Training Window</Label>
                <span className="text-sm font-medium">{trainingDays[0]} days</span>
              </div>
              <Slider value={trainingDays} onValueChange={setTrainingDays}
                      min={3} max={90} step={1} className="w-full"
                      data-testid="days-slider" />
              <p className="text-xs text-muted-foreground mt-1">More days = more samples, but stale regimes may hurt.</p>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <Label>Look-ahead (bars)</Label>
                <span className="text-sm font-medium">{lookaheadBars[0]}</span>
              </div>
              <Slider value={lookaheadBars} onValueChange={setLookaheadBars}
                      min={1} max={10} step={1} className="w-full"
                      data-testid="lookahead-slider" />
              <p className="text-xs text-muted-foreground mt-1">Bars ahead the target label predicts.</p>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <Label>Validation Split</Label>
                <span className="text-sm font-medium">{(testSize[0] * 100).toFixed(0)}%</span>
              </div>
              <Slider value={testSize} onValueChange={setTestSize}
                      min={0.1} max={0.4} step={0.05} className="w-full"
                      data-testid="testsize-slider" />
              <p className="text-xs text-muted-foreground mt-1">Fraction held out for accuracy measurement.</p>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <Label>Min Samples</Label>
                <span className="text-sm font-medium">{minSamples[0]}</span>
              </div>
              <Slider value={minSamples} onValueChange={setMinSamples}
                      min={100} max={5000} step={50} className="w-full"
                      data-testid="min-samples-slider" />
              <p className="text-xs text-muted-foreground mt-1">Abort training below this candle count.</p>
            </div>
          </div>

          {/* Ensemble weights */}
          <div className="pt-3 border-t border-slate-700/50">
            <div className="flex justify-between mb-2">
              <Label>Ensemble Weight — Random Forest vs Gradient Boosting</Label>
              <span className="text-sm font-medium">
                RF <span className="text-emerald-400 font-bold">{(rfWeight[0] * 100).toFixed(0)}%</span> · GB <span className="text-cyan-400 font-bold">{((1 - rfWeight[0]) * 100).toFixed(0)}%</span>
              </span>
            </div>
            <Slider value={rfWeight} onValueChange={setRfWeight}
                    min={0} max={1} step={0.05} className="w-full"
                    data-testid="rf-weight-slider" />
            <p className="text-xs text-muted-foreground mt-1">
              Slide fully left → GB-only model. Fully right → RF-only. Middle → 50/50 blend.
            </p>
          </div>

          {/* Feature groups */}
          <div className="pt-3 border-t border-slate-700/50">
            <Label className="mb-2 block">Feature Groups (indicators fed into the model)</Label>
            <div className="flex flex-wrap gap-2" data-testid="feature-groups">
              {Object.entries(featureGroups).map(([g, on]) => (
                <Button
                  key={g}
                  size="sm"
                  variant={on ? 'default' : 'outline'}
                  onClick={() => toggleFeatureGroup(g)}
                  className="text-[11px] h-7"
                  data-testid={`feature-${g}`}
                >
                  {on ? '✓' : '○'} {g.replace(/_/g, ' ')}
                </Button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Toggle groups OFF to test whether that indicator family is helping or hurting your win rate.
            </p>
          </div>

          {/* Train + Compare buttons */}
          <div className="flex gap-2 pt-3">
            <Button
              onClick={handleTrainModel}
              disabled={isTraining || isComparing}
              className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600"
              data-testid="train-model-btn"
            >
              {isTraining ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Training...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4 mr-2" />
                  Train + Save
                </>
              )}
            </Button>
            <Button
              onClick={handleCompareModels}
              disabled={isTraining || isComparing}
              variant="outline"
              className="flex-1"
              data-testid="compare-btn"
            >
              {isComparing ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Comparing...
                </>
              ) : (
                <>
                  <BarChart3 className="w-4 h-4 mr-2" />
                  Compare RF · GB · Ensemble
                </>
              )}
            </Button>
          </div>

          {/* Last training result + feature importance */}
          {lastTrainingResult?.success && (
            <div className="mt-3 p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5" data-testid="training-result-card">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-semibold text-emerald-400">✓ Trained {lastTrainingResult.asset} {lastTrainingResult.timeframe}</span>
                <span className="text-lg font-bold text-emerald-400">{lastTrainingResult.performance?.win_rate?.toFixed(1) || '?'}%</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div>Samples: <span className="font-mono text-slate-300">{lastTrainingResult.samples_used}</span></div>
                <div>Signals: <span className="font-mono text-slate-300">{lastTrainingResult.performance?.total_signals ?? 0}</span></div>
                <div>Precision: <span className="font-mono text-slate-300">{(lastTrainingResult.performance?.precision * 100 || 0).toFixed(1)}%</span></div>
                <div>Recall: <span className="font-mono text-slate-300">{(lastTrainingResult.performance?.recall * 100 || 0).toFixed(1)}%</span></div>
              </div>
              {lastTrainingResult.feature_importance && Object.keys(lastTrainingResult.feature_importance).length > 0 && (
                <div className="mt-2 pt-2 border-t border-emerald-500/20">
                  <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Top Features</div>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(lastTrainingResult.feature_importance).slice(0, 8).map(([f, v]) => (
                      <Badge key={f} variant="outline" className="text-[10px] font-mono">
                        {f}: {(v * 100).toFixed(1)}%
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Comparison result */}
          {comparisonResult?.success && (
            <div className="mt-3 p-3 rounded-lg border border-cyan-500/30 bg-cyan-500/5" data-testid="comparison-result-card">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-semibold text-cyan-400">🏁 Model Comparison — {comparisonResult.asset} {comparisonResult.timeframe}</span>
                {comparisonResult.best && (
                  <Badge className="bg-emerald-500 text-black">
                    Best: {comparisonResult.best}
                  </Badge>
                )}
              </div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-400 uppercase tracking-wider">
                    <th className="text-left py-1">Model</th>
                    <th className="text-right py-1">Win Rate</th>
                    <th className="text-right py-1">Precision</th>
                    <th className="text-right py-1">Recall</th>
                    <th className="text-right py-1">Signals</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(comparisonResult.results).map(([label, r]) => (
                    <tr key={label} className={`border-t border-cyan-500/10 ${label === comparisonResult.best ? 'bg-emerald-500/10' : ''}`}>
                      <td className="py-1 font-mono text-slate-200">{label}</td>
                      {r.success ? (
                        <>
                          <td className="py-1 text-right font-bold text-emerald-400">{r.win_rate?.toFixed(1)}%</td>
                          <td className="py-1 text-right text-slate-300">{(r.precision * 100).toFixed(1)}%</td>
                          <td className="py-1 text-right text-slate-300">{(r.recall * 100).toFixed(1)}%</td>
                          <td className="py-1 text-right font-mono text-slate-400">{r.total_signals}</td>
                        </>
                      ) : (
                        <td colSpan={4} className="py-1 text-right text-rose-400">{r.error}</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
                      {model.loaded ? '✅ Loaded' : '📁 Saved'}
                    </div>
                  </div>
                  {model.performance && (
                    <div className="text-right">
                      <div className="text-lg font-bold text-green-500">
                        {model.performance.win_rate?.toFixed(1) || 'N/A'}%
                      </div>
                      <div className="text-xs text-muted-foreground">Win Rate</div>
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
