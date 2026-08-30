import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import {
  Target, TrendingUp, TrendingDown, RefreshCw, ArrowUpDown, Zap,
  ChevronDown, ChevronRight, Filter, Play,
} from 'lucide-react';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

const DEFAULT_UNIVERSE = [
  'EURUSD_OTC', 'GBPUSD_OTC', 'USDJPY_OTC', 'AUDUSD_OTC', 'EURJPY_OTC',
  'GBPJPY_OTC', 'AUDCAD_OTC', 'NZDUSD_OTC', 'CADCHF_OTC', 'EURGBP_OTC',
];

const scoreColor = (score) => {
  if (score >= 70) return 'text-emerald-400';
  if (score >= 50) return 'text-amber-400';
  if (score >= 30) return 'text-orange-400';
  return 'text-slate-500';
};
const scoreBg = (score) => {
  if (score >= 70) return 'bg-emerald-500/15 border-emerald-500/40';
  if (score >= 50) return 'bg-amber-500/15 border-amber-500/40';
  if (score >= 30) return 'bg-orange-500/10 border-orange-500/30';
  return 'bg-slate-800/40 border-slate-700/40';
};
const directionBadge = (dir) => {
  if (dir === 'CALL') return 'bg-emerald-500 text-black';
  if (dir === 'PUT') return 'bg-rose-500 text-white';
  return 'bg-slate-600 text-slate-200';
};

/**
 * Iter 109 — Elite Screener.
 *
 * Multi-asset scanner exposing the proprietary Elite Composite Score.
 * Combines 5 sub-scores per asset:
 *   • SMT       — Smart Money Trap (false breakout + Fib retrace)
 *   • Sweep     — Liquidity Sweep (swing sweep + rejection wick)
 *   • ATR Band  — ICT AI ATR envelope reversion
 *   • OB/FVG    — Order Block / Fair Value Gap proximity
 *   • Micro     — Kyle λ + Glosten-Milgrom health check
 *
 * Poll cadence: 5 seconds. Endpoint: /api/screener/scan
 */
const EliteScreener = () => {
  const [assets, setAssets] = useState(DEFAULT_UNIVERSE.join(','));
  const [timeframe, setTimeframe] = useState('1m');
  const [minScore, setMinScore] = useState(0);
  const [directionFilter, setDirectionFilter] = useState('ALL');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState('elite_score');
  const [sortDir, setSortDir] = useState('desc');
  const [expanded, setExpanded] = useState({});
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastFetch, setLastFetch] = useState(null);
  const timerRef = useRef(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = `${API}/api/screener/scan?assets=${encodeURIComponent(assets)}&timeframe=${encodeURIComponent(timeframe)}&min_score=${minScore}`;
      const r = await fetch(url, { cache: 'no-store' });
      const j = await r.json();
      if (j.success) {
        setRows(j.results || []);
        setLastFetch(Date.now());
      } else {
        setError(j.error || 'scan failed');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!autoRefresh) {
      if (timerRef.current) clearInterval(timerRef.current);
      return undefined;
    }
    timerRef.current = setInterval(load, 5000);
    return () => timerRef.current && clearInterval(timerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, assets, timeframe, minScore]);

  const switchTmTarget = async (row) => {
    try {
      const asset = typeof row === 'string' ? row : row.asset;
      const direction = typeof row === 'object' ? row.direction : null;
      const confidence = typeof row === 'object' ? row.confidence : null;
      const elite_score = typeof row === 'object' ? row.elite_score : null;
      const r = await fetch(`${API}/api/tampermonkey/active-target`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset,
          timeframe,
          direction,
          confidence,
          elite_score,
          source: 'elite_screener',
          target_ttl_seconds: 90,
        }),
      });
      const j = await r.json();
      if (j.success !== false) {
        const dirLabel = direction ? ` · ${direction}` : '';
        const confLabel = confidence != null ? ` (${Math.round(confidence * (confidence > 1 ? 1 : 100))}%)` : '';
        toast.success(`TM → ${asset} @ ${timeframe}${dirLabel}${confLabel} — trade will fire when TM APP mode is on`);
      } else {
        toast.error(`Failed: ${j.error || 'unknown'}`);
      }
    } catch (e) {
      toast.error(`Network error: ${e.message}`);
    }
  };

  const filteredRows = useMemo(() => {
    let out = rows;
    if (directionFilter !== 'ALL') {
      out = out.filter((r) => r.direction === directionFilter);
    }
    out = [...out].sort((a, b) => {
      let av = a[sortBy] ?? 0;
      let bv = b[sortBy] ?? 0;
      if (sortBy === 'asset' || sortBy === 'direction') {
        av = String(av); bv = String(bv);
        return sortDir === 'desc' ? bv.localeCompare(av) : av.localeCompare(bv);
      }
      return sortDir === 'desc' ? bv - av : av - bv;
    });
    return out;
  }, [rows, directionFilter, sortBy, sortDir]);

  const flipSort = (col) => {
    if (sortBy === col) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(col);
      setSortDir('desc');
    }
  };

  const topScore = rows.length ? Math.max(...rows.map((r) => r.elite_score || 0)) : 0;
  const highQuality = rows.filter((r) => (r.elite_score || 0) >= 70).length;

  return (
    <div className="space-y-6" data-testid="elite-screener-page">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-emerald-500/25 bg-gradient-to-br from-emerald-950/40 via-slate-950 to-cyan-950/40 p-8">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_top_right,#10b981,transparent_50%)]" />
        <div className="relative">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-4xl font-bold text-white flex items-center gap-3">
                <Target className="w-9 h-9 text-emerald-400" />
                Elite Screener
              </h1>
              <p className="text-slate-400 mt-2 max-w-xl">
                Proprietary Elite Score across Smart Money Traps, Liquidity Sweeps,
                ICT ATR Bands, Order Blocks / FVGs, and Microstructure health.
              </p>
              <div className="flex items-center gap-2 mt-3">
                <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40">
                  Iter 109 · 5 confluence layers
                </Badge>
                <Badge className="bg-cyan-500/20 text-cyan-300 border-cyan-500/40">
                  Live · 5s poll
                </Badge>
                <Badge className="bg-purple-500/20 text-purple-300 border-purple-500/40">
                  {highQuality} elite setups
                </Badge>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <div className="text-right">
                <div className="text-slate-400 text-xs uppercase tracking-wider">Top Score</div>
                <div className={`text-5xl font-bold ${scoreColor(topScore)}`} data-testid="top-score">
                  {topScore.toFixed(1)}
                </div>
              </div>
              <Button
                onClick={load}
                disabled={loading}
                className="bg-emerald-500 hover:bg-emerald-600 text-black font-bold"
                data-testid="refresh-btn"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                {loading ? 'Scanning…' : 'Rescan'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="md:col-span-2">
              <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block">
                Assets (comma-separated)
              </label>
              <Input
                value={assets}
                onChange={(e) => setAssets(e.target.value)}
                className="bg-slate-950 border-slate-700 text-white font-mono text-xs"
                data-testid="assets-input"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block">
                Timeframe
              </label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 text-white rounded-md px-3 py-2 text-sm"
                data-testid="timeframe-select"
              >
                <option value="5s">5s</option>
                <option value="15s">15s</option>
                <option value="30s">30s</option>
                <option value="1m">1m</option>
                <option value="5m">5m</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block">
                Min Score: <span className="text-emerald-400 font-bold">{minScore}</span>
              </label>
              <input
                type="range" min="0" max="100" step="5"
                value={minScore}
                onChange={(e) => setMinScore(parseInt(e.target.value, 10))}
                className="w-full accent-emerald-500"
                data-testid="min-score-slider"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-400 uppercase tracking-wider flex items-center gap-1">
              <Filter className="w-3 h-3" /> Direction:
            </span>
            {['ALL', 'CALL', 'PUT', 'NEUTRAL'].map((d) => (
              <Button
                key={d}
                size="sm"
                variant="ghost"
                onClick={() => setDirectionFilter(d)}
                className={`text-xs h-7 ${
                  directionFilter === d
                    ? 'bg-emerald-500 text-black hover:bg-emerald-600'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
                data-testid={`filter-${d.toLowerCase()}`}
              >
                {d}
              </Button>
            ))}
            <div className="flex-1" />
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setAutoRefresh((v) => !v)}
              className={`text-xs h-7 ${
                autoRefresh
                  ? 'bg-cyan-500/20 text-cyan-300'
                  : 'bg-slate-800 text-slate-400'
              }`}
              data-testid="autorefresh-toggle"
            >
              {autoRefresh ? '● LIVE' : '❚❚ PAUSED'}
            </Button>
            {lastFetch && (
              <span className="text-xs text-slate-500">
                {Math.max(0, Math.floor((Date.now() - lastFetch) / 1000))}s ago
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-rose-500/40 bg-rose-950/20">
          <CardContent className="p-4 text-rose-300 text-sm">Error: {error}</CardContent>
        </Card>
      )}

      {/* Results table */}
      <Card className="border-slate-800 bg-slate-900/50 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-800 flex items-center gap-2">
          <Zap className="w-4 h-4 text-emerald-400" />
          <span className="text-white font-semibold text-sm">Scan Results</span>
          <Badge className="bg-slate-800 text-slate-300 border-slate-700 text-xs ml-auto">
            {filteredRows.length} / {rows.length}
          </Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="results-table">
            <thead>
              <tr className="bg-slate-950/60 text-xs uppercase tracking-wider text-slate-400">
                {[
                  { key: 'asset', label: 'Asset' },
                  { key: 'direction', label: 'Dir' },
                  { key: 'elite_score', label: 'Elite' },
                ].map((c) => (
                  <th key={c.key}
                      onClick={() => flipSort(c.key)}
                      className="px-3 py-2 text-left cursor-pointer hover:text-emerald-400 select-none">
                    <span className="inline-flex items-center gap-1">
                      {c.label}
                      <ArrowUpDown className="w-3 h-3 opacity-50" />
                    </span>
                  </th>
                ))}
                <th className="px-2 py-2 text-center">SMT</th>
                <th className="px-2 py-2 text-center">Sweep</th>
                <th className="px-2 py-2 text-center">ATR</th>
                <th className="px-2 py-2 text-center">OB/FVG</th>
                <th className="px-2 py-2 text-center">Micro</th>
                <th className="px-2 py-2 text-right">Entry</th>
                <th className="px-2 py-2 text-center">Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length === 0 && (
                <tr>
                  <td colSpan={10} className="text-center py-10 text-slate-500 text-sm">
                    {loading ? 'Scanning…' : 'No rows match the current filters.'}
                  </td>
                </tr>
              )}
              {filteredRows.map((r) => {
                const isExp = !!expanded[r.asset];
                const s = r.sub_scores || {};
                return (
                  <React.Fragment key={r.asset}>
                    <tr
                      className={`border-t border-slate-800 hover:bg-slate-800/40 cursor-pointer`}
                      onClick={() => setExpanded((e) => ({ ...e, [r.asset]: !e[r.asset] }))}
                      data-testid={`row-${r.asset}`}
                    >
                      <td className="px-3 py-2 font-mono text-white flex items-center gap-1">
                        {isExp ? <ChevronDown className="w-3 h-3 text-slate-500" />
                               : <ChevronRight className="w-3 h-3 text-slate-500" />}
                        {r.asset}
                      </td>
                      <td className="px-3 py-2">
                        <Badge className={`${directionBadge(r.direction)} text-xs font-bold`}>
                          {r.direction === 'CALL' && <TrendingUp className="w-3 h-3 mr-1" />}
                          {r.direction === 'PUT' && <TrendingDown className="w-3 h-3 mr-1" />}
                          {r.direction}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        <div className={`inline-block px-2 py-1 rounded border ${scoreBg(r.elite_score)}`}>
                          <span className={`font-bold ${scoreColor(r.elite_score)}`}>
                            {(r.elite_score || 0).toFixed(1)}
                          </span>
                        </div>
                      </td>
                      <td className={`px-2 py-2 text-center ${scoreColor(s.smt)}`}>{(s.smt || 0).toFixed(0)}</td>
                      <td className={`px-2 py-2 text-center ${scoreColor(s.sweep)}`}>{(s.sweep || 0).toFixed(0)}</td>
                      <td className={`px-2 py-2 text-center ${scoreColor(s.atr_band)}`}>{(s.atr_band || 0).toFixed(0)}</td>
                      <td className={`px-2 py-2 text-center ${scoreColor(s.ob_fvg)}`}>{(s.ob_fvg || 0).toFixed(0)}</td>
                      <td className={`px-2 py-2 text-center ${scoreColor(s.micro)}`}>{(s.micro || 0).toFixed(0)}</td>
                      <td className="px-2 py-2 text-right font-mono text-slate-300 text-xs">
                        {r.entry ? r.entry.toFixed(5) : '—'}
                      </td>
                      <td className="px-2 py-2 text-center">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => { e.stopPropagation(); switchTmTarget(r); }}
                          className="h-7 px-2 text-xs bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/30"
                          data-testid={`switch-${r.asset}`}
                        >
                          <Play className="w-3 h-3 mr-1" /> TM
                        </Button>
                      </td>
                    </tr>
                    {isExp && (
                      <tr className="bg-slate-950/40 border-t border-slate-800">
                        <td colSpan={10} className="px-6 py-4">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                            <div>
                              <div className="text-slate-400 uppercase tracking-wider mb-1">Setup</div>
                              <div className="text-slate-200 space-y-1">
                                <div>Entry: <span className="font-mono text-white">{r.entry?.toFixed(5) ?? '—'}</span></div>
                                <div>Stop:  <span className="font-mono text-rose-400">{r.stop?.toFixed(5) ?? '—'}</span></div>
                                <div>Target:<span className="font-mono text-emerald-400"> {r.target?.toFixed(5) ?? '—'}</span></div>
                                <div>Candles: <span className="text-slate-300">{r.n_candles}</span></div>
                                {r.reason && <div className="text-amber-400">Note: {r.reason}</div>}
                              </div>
                            </div>
                            <div className="md:col-span-2">
                              <div className="text-slate-400 uppercase tracking-wider mb-1">Sub-score Details</div>
                              <div className="space-y-1 text-slate-300 max-h-40 overflow-y-auto">
                                {Object.entries(r.sub_details || {}).map(([k, v]) => (
                                  <div key={k} className="flex items-start gap-2">
                                    <span className="text-cyan-400 font-mono uppercase w-16">{k}:</span>
                                    <span className="text-slate-400 font-mono text-[10px] break-all">
                                      {JSON.stringify(v)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Legend */}
      <Card className="border-slate-800 bg-slate-900/30">
        <CardContent className="p-4 text-xs text-slate-400">
          <div className="font-semibold text-slate-300 mb-2">Sub-score Legend</div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            <div><span className="text-cyan-400 font-semibold">SMT</span> — Smart Money Trap (false breakout + Fib 0.618-1.0)</div>
            <div><span className="text-cyan-400 font-semibold">Sweep</span> — Liquidity Sweep (swing pierce + close-back)</div>
            <div><span className="text-cyan-400 font-semibold">ATR</span> — MA ± ATR band mean-reversion</div>
            <div><span className="text-cyan-400 font-semibold">OB/FVG</span> — Order Block / Fair Value Gap retest</div>
            <div><span className="text-cyan-400 font-semibold">Micro</span> — Kyle λ + Glosten-Milgrom health</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default EliteScreener;
