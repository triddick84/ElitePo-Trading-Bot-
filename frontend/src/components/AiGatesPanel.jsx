import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * Iter 115 — AI Enhancement Gates panel.
 * Lets the user toggle:
 *   a) ADX Regime Gate
 *   b) Heikin-Ashi Confluence Gate
 *   c) Feedback Engine confidence multiplier
 *   d) LightGBM Meta-Model override
 * Also surfaces:
 *   - current regime for the primary asset
 *   - LightGBM training status + train button
 *   - per-strategy feedback stats snapshot
 */
export default function AiGatesPanel({ primaryAsset = 'EURUSD_OTC' }) {
  const [config, setConfig] = useState(null);
  const [regime, setRegime] = useState(null);
  const [lgbmStatus, setLgbmStatus] = useState(null);
  const [feedbackStats, setFeedbackStats] = useState([]);
  const [training, setTraining] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [cfg, reg, lgbm, fb] = await Promise.all([
        axios.get(`${API}/ai/gates/config`),
        axios.get(`${API}/regime/current`, { params: { symbol: primaryAsset } }),
        axios.get(`${API}/ml/lightgbm/status`),
        axios.get(`${API}/feedback/weights`),
      ]);
      setConfig(cfg.data.config);
      setRegime(reg.data.regime);
      setLgbmStatus(lgbm.data);
      setFeedbackStats(fb.data.stats || []);
    } catch (e) {
      console.error('AI Gates load failed', e);
    }
  }, [primaryAsset]);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const saveConfig = async (next) => {
    try {
      setSaving(true);
      const { data } = await axios.post(`${API}/ai/gates/config`, next);
      setConfig(data.config);
      toast.success('AI gate settings saved');
    } catch (e) {
      toast.error('Failed to save gate settings');
    } finally {
      setSaving(false);
    }
  };

  const toggle = (key) => {
    if (!config) return;
    saveConfig({ ...config, [key]: !config[key] });
  };

  const trainLightGBM = async () => {
    try {
      setTraining(true);
      toast.info('Training LightGBM meta-model — up to 30 s...');
      const { data } = await axios.post(`${API}/ml/lightgbm/train`, {
        max_samples: 3000,
        lookback: 30,
      });
      if (data.success) {
        toast.success(`Trained. AUC ${data.auc}, Acc ${data.accuracy}`);
        await load();
      } else {
        toast.error(`Training failed: ${data.error || 'unknown'}`);
      }
    } catch (e) {
      toast.error(`Training failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setTraining(false);
    }
  };

  if (!config) {
    return (
      <Card className="p-6 glass-dark border-purple-500/20" data-testid="ai-gates-panel-loading">
        <p className="text-white/70">Loading AI enhancement gates…</p>
      </Card>
    );
  }

  const regimeColor = {
    TREND: 'bg-emerald-500/20 text-emerald-300 border-emerald-400/40',
    CHOPPY: 'bg-orange-500/20 text-orange-300 border-orange-400/40',
    NEUTRAL: 'bg-slate-500/20 text-slate-300 border-slate-400/40',
  }[regime?.regime] || 'bg-slate-500/20 text-slate-300 border-slate-400/40';

  return (
    <Card className="p-6 glass-dark border-purple-500/30 card-hover" data-testid="ai-gates-panel">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-white font-bold text-lg">AI Enhancement Gates</h3>
          <p className="text-white/60 text-sm mt-1">
            Iter 115 — ADX regime, HA confluence, feedback loop, LightGBM meta
          </p>
        </div>
        {regime && (
          <div className="text-right">
            <Badge className={`${regimeColor} font-semibold`} data-testid="regime-badge">
              {regime.regime} · ADX {regime.adx}
            </Badge>
            <p className="text-xs text-white/50 mt-1">
              +DI {regime.plus_di} / -DI {regime.minus_di} on {primaryAsset}
            </p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* (a) ADX Regime Gate */}
        <div className="flex items-start justify-between p-4 rounded-lg bg-slate-900/50 border border-white/5">
          <div>
            <p className="text-white font-medium">ADX Regime Gate</p>
            <p className="text-white/60 text-xs mt-1">
              Blocks trend strategies in choppy markets (ADX &lt; 20) and mean-reversion in trends (ADX &gt; 25)
            </p>
          </div>
          <Switch
            checked={!!config.adx_regime_enabled}
            onCheckedChange={() => toggle('adx_regime_enabled')}
            disabled={saving}
            data-testid="toggle-adx-regime"
          />
        </div>

        {/* (b) Heikin-Ashi confluence */}
        <div className="flex items-start justify-between p-4 rounded-lg bg-slate-900/50 border border-white/5">
          <div>
            <p className="text-white font-medium">Heikin-Ashi Confluence</p>
            <p className="text-white/60 text-xs mt-1">
              Signal must be confirmed by at least {config.ha_min_streak} consecutive HA candles
            </p>
          </div>
          <Switch
            checked={!!config.ha_confluence_enabled}
            onCheckedChange={() => toggle('ha_confluence_enabled')}
            disabled={saving}
            data-testid="toggle-ha-confluence"
          />
        </div>

        {/* (c) Feedback multiplier */}
        <div className="flex items-start justify-between p-4 rounded-lg bg-slate-900/50 border border-white/5">
          <div>
            <p className="text-white font-medium">Feedback Multiplier</p>
            <p className="text-white/60 text-xs mt-1">
              Auto-tunes confidence per strategy based on rolling Bayesian win-rate
            </p>
          </div>
          <Switch
            checked={!!config.feedback_multiplier_enabled}
            onCheckedChange={() => toggle('feedback_multiplier_enabled')}
            disabled={saving}
            data-testid="toggle-feedback-multiplier"
          />
        </div>

        {/* (d) LightGBM meta */}
        <div className="flex items-start justify-between p-4 rounded-lg bg-slate-900/50 border border-white/5">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <p className="text-white font-medium">LightGBM Meta-Model</p>
              {lgbmStatus?.ready ? (
                <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-400/40 text-xs">
                  Ready · AUC {lgbmStatus.metrics?.auc ?? '—'}
                </Badge>
              ) : (
                <Badge className="bg-amber-500/20 text-amber-300 border-amber-400/40 text-xs">
                  Untrained
                </Badge>
              )}
            </div>
            <p className="text-white/60 text-xs mt-1">
              Cross-validates every signal against a tabular meta-classifier
            </p>
            <Button
              size="sm"
              variant="outline"
              className="mt-2 text-xs border-purple-400/40 text-purple-300 hover:bg-purple-500/10"
              onClick={trainLightGBM}
              disabled={training}
              data-testid="btn-train-lightgbm"
            >
              {training ? 'Training…' : (lgbmStatus?.ready ? 'Re-train' : 'Train now')}
            </Button>
          </div>
          <Switch
            checked={!!config.lightgbm_meta_enabled}
            onCheckedChange={() => toggle('lightgbm_meta_enabled')}
            disabled={saving || !lgbmStatus?.ready}
            data-testid="toggle-lightgbm-meta"
          />
        </div>
      </div>

      {feedbackStats?.length > 0 && (
        <div className="mt-6">
          <p className="text-white/80 font-medium text-sm mb-2">
            Recent strategy performance ({feedbackStats.length})
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {feedbackStats.slice(0, 9).map((s) => (
              <div
                key={s.strategy_id}
                className="p-3 rounded bg-slate-900/60 border border-white/5"
                data-testid={`feedback-stat-${s.strategy_id}`}
              >
                <p className="text-white text-xs font-medium truncate">
                  {s.strategy_id}
                </p>
                <p className="text-white/60 text-xs mt-1">
                  WR {(s.posterior_win_rate * 100).toFixed(1)}% · n={s.n_trades}
                </p>
                <p className={`text-xs mt-1 ${s.confidence_multiplier >= 1 ? 'text-emerald-300' : 'text-red-300'}`}>
                  ×{s.confidence_multiplier}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
