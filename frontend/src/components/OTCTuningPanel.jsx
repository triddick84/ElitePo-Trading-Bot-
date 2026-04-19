import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { toast } from 'sonner';
import { Database, Zap, RefreshCw, TrendingUp, Brain, Clock, BarChart3, Target } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const OTCTuningPanel = () => {
  const [report, setReport] = useState(null);
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/ml/tuning-report`);
      if (res.data.success) setReport(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  const trainFromOTC = async (model) => {
    setTraining(true);
    setTrainResult(null);
    try {
      const res = await axios.post(`${API}/ml/train-from-otc`, {
        model,
        min_samples: 50
      }, { timeout: 120000 });
      setTrainResult(res.data);
      if (res.data.success) {
        toast.success(`${model} model trained: ${res.data.cv_accuracy}% accuracy`);
        fetchReport();
      } else {
        toast.error(res.data.error || 'Training failed');
      }
    } catch (e) {
      toast.error('Training request failed');
      setTrainResult({ success: false, error: e.message });
    }
    setTraining(false);
  };

  const otcData = report?.otc_data;
  const modelStatus = report?.model_status;
  const config = report?.tuning_config;

  return (
    <Card className="bg-slate-800/50 border-slate-700" data-testid="otc-tuning-panel">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-white flex items-center gap-2">
              <Brain className="w-5 h-5 text-indigo-400" />
              5-Second OTC ML Tuning
            </CardTitle>
            <CardDescription>Train ML models using live 5s OTC candles collected from Tampermonkey</CardDescription>
          </div>
          <Button size="sm" variant="outline" className="border-slate-600" onClick={fetchReport} disabled={loading}>
            <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">

        {/* OTC Data Status */}
        <div data-testid="otc-data-status" className="bg-slate-900/60 rounded-lg p-4 border border-slate-700/50">
          <h3 className="text-white font-medium text-sm mb-3 flex items-center gap-2">
            <Database className="w-4 h-4 text-cyan-400" /> Collected OTC Data
          </h3>
          {otcData ? (
            <>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <div className="text-center">
                  <div className="text-2xl font-bold text-cyan-400">{otcData.total_candles}</div>
                  <div className="text-xs text-slate-400">Total 5s Candles</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-emerald-400">{otcData.by_symbol?.length || 0}</div>
                  <div className="text-xs text-slate-400">Symbols</div>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold ${otcData.ready_for_training ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {otcData.ready_for_training ? 'READY' : 'COLLECTING'}
                  </div>
                  <div className="text-xs text-slate-400">Status</div>
                </div>
              </div>

              <Progress value={Math.min(100, (otcData.total_candles / otcData.min_required) * 100)} className="h-2 mb-2" />
              <div className="text-xs text-slate-500 flex justify-between">
                <span>{otcData.total_candles} / {otcData.min_required} min. required</span>
                <span>{otcData.ready_for_training ? 'Ready to train' : `Need ${otcData.min_required - otcData.total_candles} more candles`}</span>
              </div>

              {otcData.by_symbol?.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {otcData.by_symbol.map(s => (
                    <div key={s.symbol} className="flex items-center justify-between text-xs bg-slate-800 rounded px-3 py-1.5">
                      <span className="text-slate-300 font-medium">{s.symbol}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-slate-400">{s.candles} candles</span>
                        <Badge className={s.trainable ? 'bg-emerald-600' : 'bg-slate-600'}>{s.trainable ? 'Trainable' : 'Needs more'}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="text-center text-slate-500 py-4">Loading OTC data stats...</div>
          )}
        </div>

        {/* Model Status */}
        {modelStatus && (
          <div data-testid="model-status" className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(modelStatus).map(([key, model]) => (
              <div key={key} className="bg-slate-900/60 rounded-lg p-4 border border-slate-700/50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-white capitalize">{key.replace('_', ' ')}</span>
                  <Badge className={model.is_trained ? 'bg-emerald-600' : 'bg-amber-600'}>
                    {model.is_trained ? 'Trained' : 'Not trained'}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-slate-400">Accuracy:</span>
                    <span className={`ml-1 font-bold ${model.accuracy > 55 ? 'text-emerald-400' : model.accuracy > 45 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {model.accuracy}%
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Trained:</span>
                    <span className="ml-1 text-slate-300">{model.last_trained ? new Date(model.last_trained).toLocaleDateString() : 'Never'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Training Controls */}
        <div data-testid="training-controls" className="bg-gradient-to-r from-indigo-900/30 to-purple-900/30 rounded-lg p-4 border border-indigo-500/30">
          <h3 className="text-white font-medium text-sm mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" /> Train from OTC Data
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Trains ML models using 5-second OTC candles with adaptive thresholds, 40 optimized features, 
            SelectKBest feature selection, and TimeSeriesSplit cross-validation.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button
              data-testid="train-maximized-btn"
              onClick={() => trainFromOTC('maximized')}
              disabled={training || !otcData?.ready_for_training}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {training ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Brain className="w-4 h-4 mr-2" />}
              Train Maximized v3 (XGBoost)
            </Button>
            <Button
              data-testid="train-improved-btn"
              onClick={() => trainFromOTC('improved')}
              disabled={training || !otcData?.ready_for_training}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {training ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Brain className="w-4 h-4 mr-2" />}
              Train Improved v2 (RF/GB)
            </Button>
          </div>
          {!otcData?.ready_for_training && (
            <p className="text-xs text-amber-400 mt-2">
              Keep running the Tampermonkey script on Pocket Option to collect more 5s candles. 
              Need at least {otcData?.min_required || 200} candles.
            </p>
          )}
        </div>

        {/* Training Result */}
        {trainResult && (
          <div data-testid="train-result" className={`rounded-lg p-4 border ${trainResult.success ? 'bg-emerald-900/20 border-emerald-500/30' : 'bg-red-900/20 border-red-500/30'}`}>
            {trainResult.success ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <span className="text-emerald-300 font-medium">Training Complete</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="text-center">
                    <div className="text-xl font-bold text-emerald-400">{trainResult.cv_accuracy}%</div>
                    <div className="text-xs text-slate-400">CV Accuracy</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold text-cyan-400">{trainResult.total_samples}</div>
                    <div className="text-xs text-slate-400">Samples</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold text-purple-400">{trainResult.features_used}</div>
                    <div className="text-xs text-slate-400">Features</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold text-amber-400">{trainResult.cv_std}%</div>
                    <div className="text-xs text-slate-400">CV Std</div>
                  </div>
                </div>
                {trainResult.cv_scores && (
                  <div className="text-xs text-slate-400">
                    CV Scores: {trainResult.cv_scores.map(s => `${s}%`).join(', ')}
                  </div>
                )}
                {trainResult.class_distribution && (
                  <div className="text-xs text-slate-400">
                    Classes: CALL={trainResult.class_distribution.CALL}, PUT={trainResult.class_distribution.PUT}
                  </div>
                )}
                {trainResult.selected_features?.length > 0 && (
                  <div>
                    <span className="text-xs text-slate-400">Top Features: </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {trainResult.selected_features.slice(0, 10).map(f => (
                        <Badge key={f} variant="outline" className="text-[10px] border-slate-600 text-slate-300">{f}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-red-300 text-sm">{trainResult.error}</div>
            )}
          </div>
        )}

        {/* Tuning Config */}
        {config && (
          <div className="bg-slate-900/60 rounded-lg p-4 border border-slate-700/50">
            <h3 className="text-white font-medium text-sm mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400" /> Tuning Configuration
            </h3>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-400 block mb-1">Labeling Thresholds (pips):</span>
                <div className="space-y-0.5">
                  {Object.entries(config.timeframe_thresholds || {}).filter(([k]) => !k.startsWith('S')).map(([tf, val]) => (
                    <div key={tf} className="flex justify-between text-slate-300">
                      <span>{tf}</span>
                      <span className="font-mono">{(val * 10000).toFixed(1)} pips</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <span className="text-slate-400 block mb-1">Prediction Horizons:</span>
                <div className="space-y-0.5">
                  {Object.entries(config.prediction_horizons || {}).filter(([k]) => !k.startsWith('S')).map(([tf, val]) => (
                    <div key={tf} className="flex justify-between text-slate-300">
                      <span>{tf}</span>
                      <span className="font-mono">{val} candles ahead</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-3 text-xs text-slate-500">
              Feature Selection: {config.feature_selection} | Cross-Validation: {config.cross_validation}
            </div>
          </div>
        )}

      </CardContent>
    </Card>
  );
};

export default OTCTuningPanel;
