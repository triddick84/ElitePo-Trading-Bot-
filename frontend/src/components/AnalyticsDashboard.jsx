import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { toast } from 'sonner';
import {
  Brain, Database, TrendingUp, TrendingDown, Activity, RefreshCw,
  BarChart3, Target, Shield, Zap, Layers, Award, Clock
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MetricCard = ({ label, value, sub, icon: Icon, color = 'purple' }) => {
  const colors = {
    purple: 'text-purple-400',
    green: 'text-emerald-400',
    red: 'text-red-400',
    yellow: 'text-amber-400',
    blue: 'text-sky-400',
    cyan: 'text-cyan-400',
  };
  return (
    <Card className="bg-slate-900/60 border-slate-700/40" data-testid={`metric-${label.toLowerCase().replace(/\s+/g,'-')}`}>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-1">
          {Icon && <Icon className={`w-4 h-4 ${colors[color]}`} />}
          <span className="text-slate-400 text-xs uppercase tracking-wide">{label}</span>
        </div>
        <p className={`text-xl font-bold ${colors[color]}`}>{value}</p>
        {sub && <p className="text-slate-500 text-xs mt-0.5">{sub}</p>}
      </CardContent>
    </Card>
  );
};

const ModelCard = ({ title, data, color }) => {
  const accent = {
    purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', bar: 'bg-purple-500' },
    blue: { bg: 'bg-sky-500/10', border: 'border-sky-500/30', text: 'text-sky-400', bar: 'bg-sky-500' },
    green: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', bar: 'bg-emerald-500' },
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', bar: 'bg-amber-500' },
  }[color] || accent;

  return (
    <Card className={`${accent.bg} ${accent.border} border`} data-testid={`model-card-${title.toLowerCase().replace(/\s+/g,'-')}`}>
      <CardHeader className="pb-2">
        <CardTitle className={`text-sm font-semibold ${accent.text} flex items-center gap-2`}>
          <Brain className="w-4 h-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.map((item, i) => (
          <div key={i}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">{item.label}</span>
              <span className="text-white font-medium">{item.value}</span>
            </div>
            {item.progress !== undefined && (
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full ${accent.bar} rounded-full transition-all`} style={{ width: `${Math.min(item.progress, 100)}%` }} />
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

const AnalyticsDashboard = () => {
  const [mlStats, setMlStats] = useState(null);
  const [lstmStats, setLstmStats] = useState(null);
  const [ppoStats, setPpoStats] = useState(null);
  const [riskMetrics, setRiskMetrics] = useState(null);
  const [historicalSummary, setHistoricalSummary] = useState(null);
  const [assetPerformance, setAssetPerformance] = useState([]);
  const [hourlyStats, setHourlyStats] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ml, lstm, ppo, risk, hist, assets, hourly] = await Promise.all([
        axios.get(`${API}/maximized-ml/stats`).catch(() => ({ data: {} })),
        axios.get(`${API}/lstm-gru/stats`).catch(() => ({ data: {} })),
        axios.get(`${API}/ppo-rl/stats`).catch(() => ({ data: {} })),
        axios.get(`${API}/risk-management/metrics`).catch(() => ({ data: {} })),
        axios.get(`${API}/historical/summary`).catch(() => ({ data: {} })),
        axios.get(`${API}/signals/asset-performance`).catch(() => ({ data: {} })),
        axios.get(`${API}/signals/hourly-stats`).catch(() => ({ data: {} })),
      ]);
      setMlStats(ml.data.stats || ml.data);
      setLstmStats(lstm.data);
      setPpoStats(ppo.data);
      setRiskMetrics(risk.data.metrics || {});
      setHistoricalSummary(hist.data.summary || {});
      setAssetPerformance((assets.data.all_assets || []).sort((a, b) => b.win_rate - a.win_rate));
      setHourlyStats(hourly.data.hourly_stats || []);
    } catch (e) {
      console.error('Analytics fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <RefreshCw className="w-6 h-6 text-purple-400 animate-spin" />
      </div>
    );
  }

  const sharpe = riskMetrics?.sharpe_ratio ?? 0;
  const sortino = riskMetrics?.sortino_ratio ?? 0;
  const maxDD = riskMetrics?.max_drawdown_pct ?? 0;
  const profitFactor = riskMetrics?.profit_factor ?? 0;
  const winRate = riskMetrics?.win_rate_pct ?? 0;
  const kelly = riskMetrics?.kelly_fraction_pct ?? 0;
  const riskLevel = riskMetrics?.risk_level ?? 'normal';

  const topAssets = assetPerformance.slice(0, 8);
  const bestHours = hourlyStats.filter(h => h.is_best_hour);
  const badHours = hourlyStats.filter(h => h.is_bad_hour);

  return (
    <div className="space-y-6" data-testid="analytics-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-purple-400" />
            Analytics Dashboard
          </h2>
          <p className="text-slate-400 text-sm mt-0.5">ML models, risk metrics, historical data, and asset performance</p>
        </div>
        <Button variant="outline" className="border-slate-600" onClick={() => { fetchAll(); toast.success('Refreshed'); }}>
          <RefreshCw className="w-4 h-4 mr-1" /> Refresh
        </Button>
      </div>

      {/* Risk Overview */}
      <div>
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
          <Shield className="w-4 h-4 text-emerald-400" /> Risk Management
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          <MetricCard label="Sharpe" value={sharpe.toFixed(2)} icon={TrendingUp} color={sharpe >= 1 ? 'green' : sharpe >= 0 ? 'yellow' : 'red'} />
          <MetricCard label="Sortino" value={sortino.toFixed(2)} icon={TrendingUp} color={sortino >= 1 ? 'green' : sortino >= 0 ? 'yellow' : 'red'} />
          <MetricCard label="Max Drawdown" value={`${maxDD.toFixed(1)}%`} icon={TrendingDown} color={maxDD < 5 ? 'green' : maxDD < 15 ? 'yellow' : 'red'} />
          <MetricCard label="Profit Factor" value={profitFactor.toFixed(2)} icon={Target} color={profitFactor >= 1.5 ? 'green' : profitFactor >= 1 ? 'yellow' : 'red'} />
          <MetricCard label="Win Rate" value={`${winRate.toFixed(1)}%`} icon={Award} color={winRate >= 60 ? 'green' : winRate >= 50 ? 'yellow' : 'red'} />
          <MetricCard label="Kelly %" value={`${kelly.toFixed(1)}%`} icon={Zap} color="blue" />
          <MetricCard label="Risk Level" value={riskLevel.toUpperCase()} icon={Shield} color={riskLevel === 'normal' ? 'green' : riskLevel === 'caution' ? 'yellow' : 'red'} />
        </div>
      </div>

      {/* ML Model Performance */}
      <div>
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-400" /> ML Model Performance
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Stacking Ensemble */}
          <ModelCard
            title="Stacking Ensemble"
            color="purple"
            data={[
              { label: 'Accuracy', value: `${mlStats?.model_accuracy ?? 0}%`, progress: mlStats?.model_accuracy ?? 0 },
              { label: 'Predictions', value: mlStats?.predictions_made ?? 0 },
              { label: 'Features', value: mlStats?.feature_count ?? 0 },
              { label: 'Regime', value: mlStats?.current_regime ?? 'N/A' },
              { label: 'Models', value: (mlStats?.models_in_ensemble || []).join(', ') || 'N/A' },
              { label: 'Trained', value: mlStats?.is_trained ? 'Yes' : 'No' },
            ]}
          />
          {/* LSTM/GRU */}
          <ModelCard
            title={lstmStats?.model_type || 'BiLSTM + GRU'}
            color="blue"
            data={[
              { label: 'Accuracy', value: `${lstmStats?.accuracy ?? 0}%`, progress: lstmStats?.accuracy ?? 0 },
              { label: 'Total Predictions', value: lstmStats?.total_predictions ?? 0 },
              { label: 'Seq Length', value: lstmStats?.sequence_length ?? 0 },
              { label: 'Train Accuracy', value: `${lstmStats?.training_history?.train_accuracy ?? 0}%` },
              { label: 'Epochs', value: lstmStats?.training_history?.epochs_run ?? 0 },
              { label: 'Samples', value: lstmStats?.training_history?.samples ?? 0 },
            ]}
          />
          {/* PPO RL */}
          <ModelCard
            title={ppoStats?.model_type || 'PPO Actor-Critic'}
            color="green"
            data={[
              { label: 'Win Rate', value: `${ppoStats?.accuracy ?? 0}%`, progress: ppoStats?.accuracy ?? 0 },
              { label: 'Total Predictions', value: ppoStats?.total_predictions ?? 0 },
              { label: 'Avg Reward', value: ppoStats?.training_stats?.avg_reward?.toFixed(2) ?? 0 },
              { label: 'Episodes', value: ppoStats?.training_stats?.total_episodes ?? 0 },
              { label: 'Final Trades', value: ppoStats?.training_stats?.final_trades ?? 0 },
              { label: 'Trained', value: ppoStats?.is_trained ? 'Yes' : 'No' },
            ]}
          />
        </div>
      </div>

      {/* Historical Data Summary */}
      <div>
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
          <Database className="w-4 h-4 text-cyan-400" /> Historical Data
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Total Candles" value={(historicalSummary?.total_candles ?? 0).toLocaleString()} icon={Database} color="cyan" />
          <MetricCard label="Symbols" value={(historicalSummary?.symbols || []).length} sub={(historicalSummary?.symbols || []).join(', ') || 'None'} icon={Layers} color="blue" />
          <MetricCard label="Timeframes" value={(historicalSummary?.timeframes || []).length} sub={(historicalSummary?.timeframes || []).join(', ') || 'None'} icon={Clock} color="purple" />
          <MetricCard label="Sources" value={(historicalSummary?.sources || []).filter(Boolean).length || 0} sub={(historicalSummary?.sources || []).filter(Boolean).join(', ') || 'None'} icon={Activity} color="green" />
        </div>
        {/* Symbol breakdown */}
        {historicalSummary?.by_symbol && Object.keys(historicalSummary.by_symbol).length > 0 && (
          <Card className="bg-slate-900/60 border-slate-700/40 mt-3">
            <CardContent className="p-4">
              <p className="text-slate-400 text-xs uppercase tracking-wide mb-3">Candles by Symbol</p>
              <div className="space-y-2">
                {Object.entries(historicalSummary.by_symbol).map(([sym, count]) => {
                  const pct = historicalSummary.total_candles > 0 ? (count / historicalSummary.total_candles) * 100 : 0;
                  return (
                    <div key={sym} className="flex items-center gap-3">
                      <span className="text-white text-sm w-24 truncate">{sym || 'Unknown'}</span>
                      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-slate-400 text-xs w-20 text-right">{count.toLocaleString()} ({pct.toFixed(0)}%)</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Asset Performance Leaderboard */}
      {topAssets.length > 0 && (
        <div>
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
            <Award className="w-4 h-4 text-amber-400" /> Asset Performance (Top {topAssets.length})
          </h3>
          <Card className="bg-slate-900/60 border-slate-700/40">
            <CardContent className="p-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {topAssets.map((asset, i) => {
                  const wr = asset.win_rate ?? 0;
                  const color = wr >= 60 ? 'emerald' : wr >= 50 ? 'amber' : 'red';
                  return (
                    <div key={asset.symbol} className="flex items-center gap-3 p-2 rounded-lg bg-slate-800/40">
                      <span className={`text-xs font-bold w-6 text-center ${i < 3 ? 'text-amber-400' : 'text-slate-500'}`}>#{i + 1}</span>
                      <span className="text-white text-sm flex-1 truncate">{asset.symbol}</span>
                      <div className="w-24 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${color === 'emerald' ? 'bg-emerald-500' : color === 'amber' ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${wr}%` }} />
                      </div>
                      <Badge className={`text-xs ${color === 'emerald' ? 'bg-emerald-500/20 text-emerald-400' : color === 'amber' ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400'}`}>
                        {wr.toFixed(1)}%
                      </Badge>
                      <span className="text-slate-500 text-xs w-12 text-right">{asset.total}t</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Trading Hours Analysis */}
      {(bestHours.length > 0 || badHours.length > 0) && (
        <div>
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4 text-sky-400" /> Trading Hours Analysis
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {bestHours.length > 0 && (
              <Card className="bg-emerald-500/5 border-emerald-500/20">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-emerald-400">Best Trading Hours (UTC)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  {bestHours.map(h => (
                    <div key={h.hour_utc} className="flex items-center justify-between text-sm">
                      <span className="text-white">{String(h.hour_utc).padStart(2, '0')}:00 <span className="text-slate-500">({h.session})</span></span>
                      <span className="text-emerald-400 font-medium">{h.win_rate?.toFixed(1)}% ({h.total_trades}t)</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
            {badHours.length > 0 && (
              <Card className="bg-red-500/5 border-red-500/20">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-red-400">Avoid These Hours (UTC)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  {badHours.map(h => (
                    <div key={h.hour_utc} className="flex items-center justify-between text-sm">
                      <span className="text-white">{String(h.hour_utc).padStart(2, '0')}:00 <span className="text-slate-500">({h.session})</span></span>
                      <span className="text-red-400 font-medium">{h.win_rate?.toFixed(1)}% ({h.total_trades}t)</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Hourly Heatmap */}
      <div>
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-purple-400" /> 24h Win Rate Heatmap (UTC)
        </h3>
        <Card className="bg-slate-900/60 border-slate-700/40">
          <CardContent className="p-4">
            <div className="grid grid-cols-12 gap-1">
              {hourlyStats.slice(0, 24).map(h => {
                const wr = h.win_rate ?? null;
                const trades = h.total_trades ?? 0;
                let bg = 'bg-slate-800';
                if (trades > 0) {
                  if (wr >= 65) bg = 'bg-emerald-500/60';
                  else if (wr >= 55) bg = 'bg-emerald-500/30';
                  else if (wr >= 45) bg = 'bg-amber-500/30';
                  else bg = 'bg-red-500/40';
                }
                return (
                  <div key={h.hour_utc} className={`${bg} rounded p-1.5 text-center`} title={`${h.hour_utc}:00 UTC - ${h.session} - WR: ${wr ?? 'N/A'}% (${trades} trades)`}>
                    <p className="text-[9px] text-slate-400">{h.hour_utc}h</p>
                    <p className="text-[10px] text-white font-bold">{trades > 0 ? `${wr?.toFixed(0)}%` : '-'}</p>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/60" /> 65%+</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/30" /> 55-65%</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500/30" /> 45-55%</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/40" /> &lt;45%</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-slate-800" /> No data</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
