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
  // Iter 119 — EV gate + shadow-mode
  const [evConfig, setEvConfig] = useState(null);
  const [shadow, setShadow] = useState(null);
  const [savingEv, setSavingEv] = useState(false);
  const [backfilling, setBackfilling] = useState(false);

  const load = useCallback(async () => {
    try {
      const [cfg, reg, lgbm, fb, ev, sh] = await Promise.all([
        axios.get(`${API}/ai/gates/config`),
        axios.get(`${API}/regime/current`, { params: { symbol: primaryAsset } }),
        axios.get(`${API}/ml/lightgbm/status`),
        axios.get(`${API}/feedback/weights`),
        axios.get(`${API}/ai/ev-gate/config`),
        axios.get(`${API}/ai/shadow-mode/report`, { params: { hours: 24 } }),
      ]);
      setConfig(cfg.data.config);
      setRegime(reg.data.regime);
      setLgbmStatus(lgbm.data);
      setFeedbackStats(fb.data.stats || []);
      setEvConfig(ev.data.config);
      setShadow(sh.data);
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

  const applyPreset = async (preset) => {
    try {
      setSaving(true);
      const { data } = await axios.post(`${API}/ai/gates/apply-preset`, { preset });
      setConfig(data.config);
      toast.success(`Applied "${preset.charAt(0).toUpperCase() + preset.slice(1)}" preset`);
    } catch (e) {
      toast.error(`Preset failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setSaving(false);
    }
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

  // Iter 119 — EV gate + backfill handlers
  const saveEv = async (next) => {
    try {
      setSavingEv(true);
      const { data } = await axios.post(`${API}/ai/ev-gate/config`, next);
      setEvConfig(data.config);
      toast.success('EV gate settings saved');
    } catch (e) {
      toast.error(`EV save failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setSavingEv(false);
    }
  };

  const runBackfill = async () => {
    try {
      setBackfilling(true);
      toast.info('Backfilling from tm_trade_reports — up to 60 s...');
      const { data } = await axios.post(`${API}/ml/lightgbm/backfill`, {
        max_samples: 6000,
        candle_lookback: 60,
      });
      if (data.success) {
        toast.success(
          `Backfill OK · +${data.backfill_stored || 0} samples · AUC ${data.auc}`
        );
        await load();
      } else {
        toast.warning(`Backfill: ${data.error || 'no new samples'}`);
      }
    } catch (e) {
      toast.error(`Backfill failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setBackfilling(false);
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

      {/* Iter 118 — One-tap presets */}
      <div className="mt-1 mb-4 pt-4 border-t border-white/5 flex flex-wrap items-center gap-2" data-testid="ai-gate-presets-row">
        <span className="text-xs text-white/50 mr-1">Presets:</span>
        <Button
          size="sm" variant="outline"
          className="text-xs border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10"
          onClick={() => applyPreset('conservative')} disabled={saving}
          data-testid="ai-gate-preset-conservative"
        >🛡 Conservative</Button>
        <Button
          size="sm" variant="outline"
          className="text-xs border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10"
          onClick={() => applyPreset('balanced')} disabled={saving}
          data-testid="ai-gate-preset-balanced"
        >⚖️ Balanced</Button>
        <Button
          size="sm" variant="outline"
          className="text-xs border-orange-500/30 text-orange-300 hover:bg-orange-500/10"
          onClick={() => applyPreset('aggressive')} disabled={saving}
          data-testid="ai-gate-preset-aggressive"
        >🔥 Aggressive</Button>
        <span className="text-[10px] text-white/40 ml-auto hidden sm:inline">
          Presets flip all 4 gates + thresholds in one tap
        </span>
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

      {/* Iter 119 — EV Gate + Shadow Mode */}
      <div
        className="mt-6 pt-4 border-t border-white/5"
        data-testid="ev-shadow-section"
      >
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div>
            <p className="text-white font-medium text-sm">
              Iter 119 · Expected-Value Gate + Shadow Mode
            </p>
            <p className="text-white/50 text-xs mt-0.5">
              Only fires when p·payout − (1−p) ≥ min-EV. Every decision logged for A/B.
            </p>
          </div>
          <Button
            size="sm" variant="outline"
            className="text-xs border-purple-400/40 text-purple-300 hover:bg-purple-500/10"
            onClick={runBackfill} disabled={backfilling}
            data-testid="btn-lgbm-backfill"
          >
            {backfilling ? 'Backfilling…' : '↻ Backfill LightGBM'}
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* EV controls */}
          <div className="p-3 rounded-lg bg-slate-900/50 border border-white/5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-white/80 text-xs font-medium">EV Gate</span>
              <Switch
                checked={!!evConfig?.enabled}
                onCheckedChange={() => saveEv({ ...evConfig, enabled: !evConfig?.enabled })}
                disabled={savingEv || !evConfig}
                data-testid="toggle-ev-gate"
              />
            </div>
            {evConfig && (
              <div className="space-y-2">
                <label className="block text-[11px] text-white/60">
                  Min EV per $1 stake
                  <span className="ml-2 text-emerald-300 font-mono" data-testid="ev-min-value">
                    {Number(evConfig.min_ev).toFixed(3)}
                  </span>
                </label>
                <input
                  type="range" min="-0.1" max="0.3" step="0.005"
                  value={evConfig.min_ev}
                  onChange={(e) => setEvConfig({ ...evConfig, min_ev: Number(e.target.value) })}
                  onMouseUp={() => saveEv(evConfig)}
                  onTouchEnd={() => saveEv(evConfig)}
                  className="w-full accent-purple-500"
                  data-testid="ev-min-slider"
                />
                <label className="block text-[11px] text-white/60">
                  Default payout
                  <span className="ml-2 text-cyan-300 font-mono">
                    {(Number(evConfig.default_payout) * 100).toFixed(0)}%
                  </span>
                </label>
                <input
                  type="range" min="0.5" max="0.95" step="0.01"
                  value={evConfig.default_payout}
                  onChange={(e) => setEvConfig({ ...evConfig, default_payout: Number(e.target.value) })}
                  onMouseUp={() => saveEv(evConfig)}
                  onTouchEnd={() => saveEv(evConfig)}
                  className="w-full accent-cyan-500"
                  data-testid="ev-payout-slider"
                />
              </div>
            )}
          </div>

          {/* Shadow-mode stats */}
          <div
            className="p-3 rounded-lg bg-slate-900/50 border border-white/5"
            data-testid="shadow-mode-card"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-white/80 text-xs font-medium">Shadow Mode · 24h</span>
              {shadow?.sim_win_rate != null ? (
                <Badge
                  className="bg-emerald-500/20 text-emerald-300 border-emerald-400/40 text-[10px]"
                  data-testid="shadow-winrate-badge"
                >
                  WR {(shadow.sim_win_rate * 100).toFixed(1)}%
                </Badge>
              ) : (
                <Badge className="bg-slate-500/20 text-slate-300 border-slate-400/40 text-[10px]">
                  no resolved yet
                </Badge>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-white/50 text-[10px] uppercase">Picks</p>
                <p className="text-white text-lg font-mono" data-testid="shadow-total">
                  {shadow?.total_shadow_picks ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-white/50 text-[10px] uppercase">Would fire</p>
                <p className="text-emerald-300 text-lg font-mono" data-testid="shadow-would-fire">
                  {shadow?.would_fire ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-white/50 text-[10px] uppercase">Sim P&L</p>
                <p
                  className={`text-lg font-mono ${
                    (shadow?.sim_pnl ?? 0) >= 0 ? 'text-emerald-300' : 'text-red-300'
                  }`}
                  data-testid="shadow-sim-pnl"
                >
                  {shadow?.sim_pnl != null ? `${shadow.sim_pnl >= 0 ? '+' : ''}${shadow.sim_pnl}` : '—'}
                </p>
              </div>
            </div>
            {lgbmStatus?.metrics && (
              <p className="text-[10px] text-white/40 mt-2 text-center">
                LightGBM AUC {lgbmStatus.metrics.auc} · {lgbmStatus.metrics.validation}
                {lgbmStatus.metrics.calibrated ? ' · calibrated' : ''}
              </p>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
