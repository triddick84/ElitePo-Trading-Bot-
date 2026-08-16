import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Activity, TrendingUp, TrendingDown, AlertTriangle, Target,
  RefreshCw, Info, Layers, Radar,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

// Common OTC pairs the user typically trades. The picker also allows
// arbitrary custom entry.
const DEFAULT_ASSETS = [
  'EURUSD_OTC', 'GBPUSD_OTC', 'USDJPY_OTC', 'AUDUSD_OTC',
  'USDCAD_OTC', 'EURGBP_OTC', 'NZDUSD_OTC', 'USDCHF_OTC',
];

/**
 * Iter 108 — Microstructure Analytics Dashboard (Option B).
 *
 * Full React tab that renders all AI/microstructure metrics per asset:
 *   • Kyle (1985) λ, β, σ_v, σ_u, informed profit, illiquidity_bps
 *   • Glosten-Milgrom (1985): Ask, Bid, spread bps, α_informed,
 *     adverse_selection_pct, interpretation
 *   • Comparison mode: pin up to 4 assets side-by-side to see which is
 *     currently the "cleanest" tape.
 *
 * Auto-refresh every 8s. Uses /api/microstructure/models endpoint (Iter 105).
 */
const MicrostructureDashboard = () => {
  const [selectedAsset, setSelectedAsset] = useState('EURUSD_OTC');
  const [lookback, setLookback] = useState(60);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [comparison, setComparison] = useState({});  // {asset: payload}
  const [customAsset, setCustomAsset] = useState('');
  const timerRef = useRef(null);

  const loadOne = async (asset, lb = lookback) => {
    const r = await fetch(
      `${API}/api/microstructure/models?asset=${encodeURIComponent(asset)}&lookback=${lb}`,
      { cache: 'no-store' },
    );
    return r.json();
  };

  // Primary asset refresh loop
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setRefreshing(true);
        const data = await loadOne(selectedAsset, lookback);
        if (cancelled) return;
        setPayload(data);
        setError(null);
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      } finally {
        if (!cancelled) setRefreshing(false);
      }
    };
    load();
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(load, 8_000);
    return () => { cancelled = true; if (timerRef.current) clearInterval(timerRef.current); };
  }, [selectedAsset, lookback]);

  // Comparison-mode fetcher (fires on demand only)
  const addToComparison = async (asset) => {
    if (comparison[asset] || Object.keys(comparison).length >= 4) return;
    try {
      const data = await loadOne(asset, lookback);
      setComparison((prev) => ({ ...prev, [asset]: data }));
    } catch (_e) { /* silent */ }
  };
  const removeFromComparison = (asset) => {
    setComparison((prev) => {
      const next = { ...prev }; delete next[asset]; return next;
    });
  };

  const kyle = payload?.kyle_result?.success ? payload.kyle_result.kyle : null;
  const gm   = payload?.gm_result?.success   ? payload.gm_result.gm   : null;
  const kyleErr = payload?.kyle_result?.reason;
  const gmErr   = payload?.gm_result?.reason;

  // Interpretation colour map
  const advColour = (pct) => {
    if (pct == null) return 'text-slate-400';
    if (pct < 15) return 'text-emerald-400';
    if (pct < 40) return 'text-amber-400';
    return 'text-rose-400';
  };
  const illColour = (bps) => {
    if (bps == null) return 'text-slate-400';
    if (bps < 5) return 'text-emerald-400';
    if (bps < 15) return 'text-amber-400';
    return 'text-rose-400';
  };

  const fmt = (v, dp = 6) => (v == null || !isFinite(Number(v)))
    ? '—' : Number(v).toFixed(dp);

  const combined = useMemo(() => {
    // Add primary asset to the comparison array first
    const rows = [];
    if (payload) rows.push({ asset: selectedAsset, data: payload, primary: true });
    for (const [a, d] of Object.entries(comparison)) rows.push({ asset: a, data: d });
    return rows;
  }, [payload, comparison, selectedAsset]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4 md:p-8" data-testid="microstructure-dashboard">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Radar className="w-7 h-7 text-cyan-400" />
            <h1 className="text-3xl md:text-4xl font-bold text-white">Microstructure Analytics</h1>
          </div>
          <p className="text-slate-400">
            Kyle (1985) price-impact & Glosten-Milgrom (1985) adverse-selection per asset
          </p>
          <div className="flex justify-center gap-2 mt-2">
            <Badge className="bg-cyan-600/70">Iter 105 · λ, β, σ_v, σ_u</Badge>
            <Badge className="bg-purple-600/70">Iter 108 · Live per-asset</Badge>
          </div>
        </div>

        {/* Asset picker + lookback slider + refresh */}
        <Card className="bg-slate-800/60 border-slate-700/60 mb-4" data-testid="ms-controls">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex-1 min-w-[220px]">
                <label className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Primary Asset</label>
                <div className="mt-1 flex gap-2 flex-wrap">
                  {DEFAULT_ASSETS.map((a) => (
                    <Button
                      key={a}
                      onClick={() => setSelectedAsset(a)}
                      size="sm"
                      variant={selectedAsset === a ? 'default' : 'outline'}
                      className={selectedAsset === a
                        ? 'bg-cyan-600 hover:bg-cyan-500 font-mono'
                        : 'border-slate-600 text-slate-300 hover:bg-slate-700 font-mono'}
                      data-testid={`ms-asset-${a}`}
                    >
                      {a.replace('_OTC', '')}
                    </Button>
                  ))}
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="text"
                    value={customAsset}
                    onChange={(e) => setCustomAsset(e.target.value.toUpperCase())}
                    placeholder="Custom, e.g. EURJPY_OTC"
                    className="flex-1 min-w-[160px] px-3 py-1 bg-slate-900/60 border border-slate-700 rounded text-slate-200 text-sm font-mono placeholder-slate-500"
                    data-testid="ms-custom-asset"
                  />
                  <Button
                    onClick={() => { if (customAsset) setSelectedAsset(customAsset); }}
                    size="sm"
                    className="bg-purple-600 hover:bg-purple-500"
                    data-testid="ms-custom-load"
                  >
                    Load
                  </Button>
                </div>
              </div>
              <div className="min-w-[140px]">
                <label className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Lookback</label>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="range" min="20" max="200" step="10"
                    value={lookback}
                    onChange={(e) => setLookback(parseInt(e.target.value, 10))}
                    className="flex-1"
                    data-testid="ms-lookback"
                  />
                  <span className="text-cyan-300 font-mono font-bold text-sm w-10 text-right">{lookback}</span>
                </div>
              </div>
              <Button
                onClick={() => loadOne(selectedAsset, lookback).then(setPayload)}
                disabled={refreshing}
                variant="outline"
                size="sm"
                className="border-slate-600 hover:bg-slate-700 text-slate-200"
                data-testid="ms-refresh"
              >
                <RefreshCw className={`w-4 h-4 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Kyle + GM primary cards */}
        <div className="grid md:grid-cols-2 gap-4 mb-4">
          {/* Kyle Model */}
          <Card className="bg-gradient-to-br from-slate-800/70 via-cyan-900/20 to-slate-900 border-slate-700/60" data-testid="ms-kyle-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-cyan-400" />
                  <h3 className="text-lg font-bold text-white">Kyle Model</h3>
                </div>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wider border-cyan-400/40 text-cyan-300">
                  price impact
                </Badge>
              </div>

              {kyleErr ? (
                <div className="flex items-center gap-2 text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded p-3">
                  <AlertTriangle className="w-4 h-4" /> {kyleErr}
                </div>
              ) : kyle ? (
                <>
                  <div className="grid grid-cols-2 gap-2 mb-3">
                    <Metric label="λ  (impact)"  value={fmt(kyle.lambda, 8)} className={illColour(kyle.illiquidity_bps)} />
                    <Metric label="β  (informed)" value={fmt(kyle.beta, 4)} />
                    <Metric label="σ_v" value={fmt(kyle.sigma_v, 6)} />
                    <Metric label="σ_u" value={fmt(kyle.sigma_u, 6)} />
                    <Metric label="Illiquidity" value={`${fmt(kyle.illiquidity_bps, 2)} bps`} className={illColour(kyle.illiquidity_bps)} />
                    <Metric label="Informed Profit" value={fmt(kyle.informed_profit, 6)} />
                  </div>
                  <div className={`text-sm font-semibold p-2 rounded ${illColour(kyle.illiquidity_bps)} bg-slate-900/60 border border-slate-700/40`}>
                    <Info className="inline w-3 h-3 mr-1" />
                    {kyle.interpretation}
                  </div>
                </>
              ) : (
                <div className="text-slate-500 py-4 text-center">loading Kyle model…</div>
              )}
            </CardContent>
          </Card>

          {/* Glosten-Milgrom Model */}
          <Card className="bg-gradient-to-br from-slate-800/70 via-purple-900/20 to-slate-900 border-slate-700/60" data-testid="ms-gm-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-purple-400" />
                  <h3 className="text-lg font-bold text-white">Glosten-Milgrom</h3>
                </div>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wider border-purple-400/40 text-purple-300">
                  adverse selection
                </Badge>
              </div>

              {gmErr ? (
                <div className="flex items-center gap-2 text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded p-3">
                  <AlertTriangle className="w-4 h-4" /> {gmErr}
                </div>
              ) : gm ? (
                <>
                  <div className="grid grid-cols-2 gap-2 mb-3">
                    <Metric label="Ask" value={fmt(gm.ask, 5)} />
                    <Metric label="Bid" value={fmt(gm.bid, 5)} />
                    <Metric label="Spread" value={fmt(gm.spread_abs, 5)} />
                    <Metric label="Spread bps" value={`${fmt(gm.spread_bps, 2)} bps`} />
                    <Metric label="α  informed" value={`${Math.round((gm.alpha_informed || 0) * 100)}%`} />
                    <Metric label="Adverse Sel" value={`${fmt(gm.adverse_selection_pct, 1)}%`} className={advColour(gm.adverse_selection_pct)} />
                  </div>
                  <div className={`text-sm font-semibold p-2 rounded ${advColour(gm.adverse_selection_pct)} bg-slate-900/60 border border-slate-700/40`}>
                    <Info className="inline w-3 h-3 mr-1" />
                    {gm.interpretation}
                  </div>
                </>
              ) : (
                <div className="text-slate-500 py-4 text-center">loading Glosten-Milgrom…</div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Comparison table */}
        <Card className="bg-slate-800/60 border-slate-700/60" data-testid="ms-comparison">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Target className="w-5 h-5 text-emerald-400" />
                <h3 className="text-lg font-bold text-white">Cross-Asset Comparison</h3>
                <span className="text-xs text-slate-400">
                  ({combined.length}/5 loaded — pin up to 4 extras)
                </span>
              </div>
              <div className="flex gap-2 flex-wrap">
                {DEFAULT_ASSETS.filter((a) => a !== selectedAsset && !comparison[a]).slice(0, 6).map((a) => (
                  <Button
                    key={a}
                    onClick={() => addToComparison(a)}
                    size="sm"
                    variant="outline"
                    className="border-slate-600 text-slate-300 hover:bg-slate-700 font-mono text-xs"
                    data-testid={`ms-pin-${a}`}
                    disabled={Object.keys(comparison).length >= 4}
                  >
                    + {a.replace('_OTC', '')}
                  </Button>
                ))}
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="ms-comparison-table">
                <thead>
                  <tr className="text-left border-b border-slate-700">
                    <th className="py-2 px-3 text-slate-400 font-semibold uppercase text-xs tracking-wider">Asset</th>
                    <th className="py-2 px-3 text-slate-400 font-semibold uppercase text-xs tracking-wider">Kyle λ</th>
                    <th className="py-2 px-3 text-slate-400 font-semibold uppercase text-xs tracking-wider">Illiq (bps)</th>
                    <th className="py-2 px-3 text-slate-400 font-semibold uppercase text-xs tracking-wider">α inf</th>
                    <th className="py-2 px-3 text-slate-400 font-semibold uppercase text-xs tracking-wider">Adv Sel</th>
                    <th className="py-2 px-3 text-slate-400 font-semibold uppercase text-xs tracking-wider">Spread bps</th>
                    <th className="py-2 px-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {combined.map((row) => {
                    const k = row.data?.kyle_result?.success ? row.data.kyle_result.kyle : null;
                    const g = row.data?.gm_result?.success ? row.data.gm_result.gm : null;
                    return (
                      <tr key={row.asset} className={`border-b border-slate-800/60 hover:bg-slate-800/40 ${row.primary ? 'bg-cyan-900/10' : ''}`} data-testid={`ms-row-${row.asset}`}>
                        <td className="py-2 px-3 font-mono font-bold text-white">
                          {row.primary && <span className="text-cyan-400 mr-1">★</span>}
                          {row.asset.replace('_OTC', '')}
                        </td>
                        <td className="py-2 px-3 font-mono text-slate-300">{fmt(k?.lambda, 6)}</td>
                        <td className={`py-2 px-3 font-mono font-bold ${illColour(k?.illiquidity_bps)}`}>{fmt(k?.illiquidity_bps, 2)}</td>
                        <td className="py-2 px-3 font-mono text-slate-300">{g?.alpha_informed != null ? `${Math.round(g.alpha_informed * 100)}%` : '—'}</td>
                        <td className={`py-2 px-3 font-mono font-bold ${advColour(g?.adverse_selection_pct)}`}>{g?.adverse_selection_pct != null ? `${g.adverse_selection_pct.toFixed(1)}%` : '—'}</td>
                        <td className="py-2 px-3 font-mono text-slate-300">{fmt(g?.spread_bps, 2)}</td>
                        <td className="py-2 px-3">
                          {!row.primary && (
                            <button
                              onClick={() => removeFromComparison(row.asset)}
                              className="text-rose-400 hover:text-rose-300 text-xs"
                              data-testid={`ms-unpin-${row.asset}`}
                              title="Remove from comparison"
                            >
                              ×
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {error && (
          <div className="mt-4 bg-rose-950/40 border border-rose-800 rounded p-3 text-rose-300 flex items-center gap-2" data-testid="ms-error">
            <AlertTriangle className="w-4 h-4" />
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

const Metric = ({ label, value, className = '' }) => (
  <div className="flex flex-col p-2 bg-slate-900/50 border border-slate-700/40 rounded">
    <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">{label}</span>
    <span className={`text-sm font-mono font-bold text-slate-200 ${className}`}>{value}</span>
  </div>
);

export default MicrostructureDashboard;
