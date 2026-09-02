import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PRESETS = {
  conservative: {
    label: 'Conservative',
    tiers: [
      { min_conf: 85, max_conf: 92, amount: 1, label: 'Good' },
      { min_conf: 93, max_conf: 100, amount: 2, label: 'Great' },
    ],
    fallback: 0.5,
  },
  balanced: {
    label: 'Balanced',
    tiers: [
      { min_conf: 80, max_conf: 89, amount: 1, label: 'Good' },
      { min_conf: 90, max_conf: 95, amount: 2, label: 'Great' },
      { min_conf: 96, max_conf: 100, amount: 5, label: 'Elite' },
    ],
    fallback: 1,
  },
  aggressive: {
    label: 'Aggressive',
    tiers: [
      { min_conf: 75, max_conf: 84, amount: 2, label: 'Good' },
      { min_conf: 85, max_conf: 92, amount: 5, label: 'Great' },
      { min_conf: 93, max_conf: 100, amount: 10, label: 'Elite' },
    ],
    fallback: 2,
  },
};

/**
 * Iter 118 — Confidence-Tiered Stakes panel.
 *
 * Lets the user set trade amount per confidence bucket. The TM script
 * pulls this config every 30s and, when enabled, writes the tier-matched
 * amount into Pocket Option's trade-amount input before firing.
 */
export default function StakeTiersPanel() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/tampermonkey/stake-tiers`);
      setCfg({
        enabled: !!data.enabled,
        auto_set: data.auto_set !== false,
        fallback: Number(data.fallback) || 1,
        tiers: Array.isArray(data.tiers) && data.tiers.length > 0
          ? data.tiers
          : PRESETS.balanced.tiers,
      });
    } catch (e) {
      console.error('Failed to fetch stake-tiers', e);
      setCfg({ enabled: false, auto_set: true, fallback: 1, tiers: PRESETS.balanced.tiers });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (next) => {
    try {
      setSaving(true);
      const payload = {
        enabled: !!next.enabled,
        auto_set: !!next.auto_set,
        fallback: Number(next.fallback) || 1,
        tiers: (next.tiers || []).slice(0, 5),
      };
      const { data } = await axios.post(`${API}/tampermonkey/stake-tiers`, payload);
      setCfg({
        enabled: !!data.enabled,
        auto_set: data.auto_set !== false,
        fallback: Number(data.fallback) || 1,
        tiers: Array.isArray(data.tiers) ? data.tiers : payload.tiers,
      });
      toast.success('Stake tiers saved — TM will pick up within 30s');
    } catch (e) {
      toast.error(`Save failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const applyPreset = (key) => {
    const p = PRESETS[key];
    if (!p) return;
    const next = { ...cfg, tiers: p.tiers, fallback: p.fallback };
    setCfg(next);
    save(next);
  };

  const updateTier = (i, patch) => {
    const next = { ...cfg, tiers: cfg.tiers.map((t, idx) => idx === i ? { ...t, ...patch } : t) };
    setCfg(next);
  };

  const addTier = () => {
    if (!cfg || cfg.tiers.length >= 5) return;
    const last = cfg.tiers[cfg.tiers.length - 1];
    const nextMin = last ? Math.min(99, (last.max_conf || 0) + 1) : 80;
    const nextTier = {
      min_conf: nextMin,
      max_conf: Math.min(100, nextMin + 5),
      amount: (last?.amount || 1) * 2,
      label: '',
    };
    setCfg({ ...cfg, tiers: [...cfg.tiers, nextTier] });
  };

  const removeTier = (i) => {
    setCfg({ ...cfg, tiers: cfg.tiers.filter((_, idx) => idx !== i) });
  };

  if (!cfg) {
    return (
      <Card className="bg-slate-800/50 border-slate-700" data-testid="stake-tiers-panel-loading">
        <CardContent className="p-6"><p className="text-slate-400">Loading stake tiers…</p></CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-slate-800/50 border-slate-700" data-testid="stake-tiers-panel">
      <CardHeader>
        <CardTitle className="text-white flex items-center justify-between flex-wrap gap-2">
          <span>💰 Confidence-Tiered Stakes</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Enable</span>
            <Switch
              checked={cfg.enabled}
              onCheckedChange={(v) => save({ ...cfg, enabled: v })}
              disabled={saving}
              data-testid="stake-tiers-enabled-switch"
            />
          </div>
        </CardTitle>
        <CardDescription>
          Set a trade amount per confidence bucket. When enabled, TM auto-writes the tier-matched amount into Pocket Option before firing.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Presets */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400 mr-1">Presets:</span>
          {Object.entries(PRESETS).map(([k, p]) => (
            <Button
              key={k}
              size="sm"
              variant="outline"
              className="text-xs border-slate-600 h-7"
              onClick={() => applyPreset(k)}
              disabled={saving}
              data-testid={`stake-tiers-preset-${k}`}
            >
              {p.label}
            </Button>
          ))}
        </div>

        {/* Tiers editor */}
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-2 text-xs text-slate-400 font-semibold px-1">
            <div className="col-span-2">Min %</div>
            <div className="col-span-2">Max %</div>
            <div className="col-span-3">Amount $</div>
            <div className="col-span-4">Label</div>
            <div className="col-span-1"></div>
          </div>
          {cfg.tiers.map((t, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-center bg-slate-900/40 border border-slate-700 rounded-md p-2" data-testid={`stake-tier-row-${i}`}>
              <Input
                type="number" min={0} max={100}
                value={t.min_conf}
                onChange={(e) => updateTier(i, { min_conf: parseInt(e.target.value, 10) || 0 })}
                onBlur={() => save(cfg)}
                className="col-span-2 h-8 text-sm bg-slate-800 border-slate-700"
                data-testid={`stake-tier-min-${i}`}
              />
              <Input
                type="number" min={0} max={100}
                value={t.max_conf}
                onChange={(e) => updateTier(i, { max_conf: parseInt(e.target.value, 10) || 0 })}
                onBlur={() => save(cfg)}
                className="col-span-2 h-8 text-sm bg-slate-800 border-slate-700"
                data-testid={`stake-tier-max-${i}`}
              />
              <Input
                type="number" min={0} step={0.1}
                value={t.amount}
                onChange={(e) => updateTier(i, { amount: parseFloat(e.target.value) || 0 })}
                onBlur={() => save(cfg)}
                className="col-span-3 h-8 text-sm bg-slate-800 border-slate-700"
                data-testid={`stake-tier-amount-${i}`}
              />
              <Input
                type="text"
                placeholder="Good / Great / Elite"
                value={t.label || ''}
                onChange={(e) => updateTier(i, { label: e.target.value })}
                onBlur={() => save(cfg)}
                className="col-span-4 h-8 text-sm bg-slate-800 border-slate-700"
                data-testid={`stake-tier-label-${i}`}
              />
              <Button
                size="sm" variant="ghost"
                className="col-span-1 h-8 text-red-400 hover:bg-red-500/10"
                onClick={() => { removeTier(i); save({ ...cfg, tiers: cfg.tiers.filter((_, x) => x !== i) }); }}
                data-testid={`stake-tier-remove-${i}`}
              >✕</Button>
            </div>
          ))}
          <Button
            size="sm"
            variant="outline"
            className="text-xs border-slate-600 mt-2"
            onClick={addTier}
            disabled={cfg.tiers.length >= 5 || saving}
            data-testid="stake-tier-add-btn"
          >+ Add tier (max 5)</Button>
        </div>

        {/* Fallback + auto-set */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 border-t border-slate-700">
          <div>
            <label className="text-xs text-slate-400 block mb-1">Fallback amount (when no tier matches)</label>
            <Input
              type="number" min={0} step={0.1}
              value={cfg.fallback}
              onChange={(e) => setCfg({ ...cfg, fallback: parseFloat(e.target.value) || 0 })}
              onBlur={() => save(cfg)}
              className="h-8 bg-slate-800 border-slate-700"
              data-testid="stake-tiers-fallback"
            />
          </div>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className="text-xs text-slate-400 block mb-1">Auto-set in Pocket Option</label>
              <div className="flex items-center gap-2 h-8">
                <Switch
                  checked={cfg.auto_set}
                  onCheckedChange={(v) => save({ ...cfg, auto_set: v })}
                  disabled={saving}
                  data-testid="stake-tiers-auto-set-switch"
                />
                <span className="text-xs text-slate-400">
                  {cfg.auto_set ? 'Bot writes amount into PO' : 'Advisory only (logs only)'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Preview strip */}
        <div className="pt-3 border-t border-slate-700">
          <p className="text-xs text-slate-400 mb-2">Preview:</p>
          <div className="flex flex-wrap gap-2">
            {cfg.tiers.length === 0 ? (
              <Badge className="bg-slate-700 text-slate-300 text-xs">No tiers configured — fallback ${cfg.fallback}</Badge>
            ) : (
              cfg.tiers.map((t, i) => (
                <Badge
                  key={i}
                  className={`text-xs ${
                    (t.amount || 0) >= 5 ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : (t.amount || 0) >= 2 ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                    : 'bg-slate-600/40 text-slate-200'
                  }`}
                  data-testid={`stake-tier-preview-${i}`}
                >
                  {t.min_conf}-{t.max_conf}% → ${t.amount}{t.label ? ` · ${t.label}` : ''}
                </Badge>
              ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
