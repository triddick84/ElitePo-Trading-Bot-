import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Activity, RefreshCw, AlertTriangle, CheckCircle2, WifiOff } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatAge = (seconds) => {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
};

const healthMeta = {
  healthy: { label: 'LIVE', Icon: CheckCircle2, text: 'text-emerald-300', bg: 'bg-emerald-900/40', border: 'border-emerald-500/40', icon: 'text-emerald-400', bar: 'bg-emerald-500' },
  stale: { label: 'STALE', Icon: AlertTriangle, text: 'text-amber-300', bg: 'bg-amber-900/40', border: 'border-amber-500/40', icon: 'text-amber-400', bar: 'bg-amber-500' },
  offline: { label: 'OFFLINE', Icon: WifiOff, text: 'text-red-300', bg: 'bg-red-900/40', border: 'border-red-500/40', icon: 'text-red-400', bar: 'bg-red-500' },
  degraded: { label: 'DEGRADED', Icon: AlertTriangle, text: 'text-amber-300', bg: 'bg-amber-900/40', border: 'border-amber-500/40', icon: 'text-amber-400', bar: 'bg-amber-500' },
  unknown: { label: 'UNKNOWN', Icon: AlertTriangle, text: 'text-slate-300', bg: 'bg-slate-900/40', border: 'border-slate-500/40', icon: 'text-slate-400', bar: 'bg-slate-500' }
};

const OTCDataHealthWidget = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/signals/otc-candle-stats`);
      if (res.data.success) setData(res.data);
    } catch (_e) { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (!data) return null;

  const symbols = data.by_symbol || [];
  const overall = data.overall_health || 'unknown';
  const summary = data.summary || {};
  const overallMeta = healthMeta[overall] || healthMeta.unknown;
  const OverallIcon = overallMeta.Icon;

  // Sort: healthy → stale → offline, then by count
  const sorted = [...symbols].sort((a, b) => {
    const order = { healthy: 0, stale: 1, offline: 2, unknown: 3 };
    const diff = (order[a.health] ?? 9) - (order[b.health] ?? 9);
    return diff !== 0 ? diff : b.candle_count - a.candle_count;
  });

  return (
    <Card data-testid="otc-data-health-widget" className="bg-slate-900/80 border border-cyan-500/20 backdrop-blur-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-cyan-600/20 to-blue-600/20 border-b border-cyan-500/20">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-bold text-white tracking-wide">OTC DATA HEALTH</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            data-testid="otc-overall-health-badge"
            className={`text-xs ${overallMeta.text} ${overallMeta.bg} border ${overallMeta.border} flex items-center gap-1`}
          >
            <OverallIcon className="w-3 h-3" />
            {overallMeta.label}
          </Badge>
          <Button
            data-testid="otc-health-refresh-btn"
            size="sm"
            variant="ghost"
            onClick={fetchData}
            disabled={loading}
            className="h-6 w-6 p-0 text-cyan-400 hover:text-white"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <div className="p-4 space-y-2">
        {/* Summary row */}
        <div className="flex items-center justify-between text-xs pb-2 border-b border-slate-800">
          <span className="text-slate-400" data-testid="otc-total-candles">
            Total: <span className="font-mono text-white">{(data.total_candles || 0).toLocaleString()}</span> candles
          </span>
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className="text-emerald-400" data-testid="otc-healthy-count">● {summary.healthy || 0}</span>
            <span className="text-amber-400" data-testid="otc-stale-count">● {summary.stale || 0}</span>
            <span className="text-red-400" data-testid="otc-offline-count">● {summary.offline || 0}</span>
          </div>
        </div>

        {/* Empty state */}
        {sorted.length === 0 && (
          <div className="text-center py-6 text-xs text-slate-500">
            <WifiOff className="w-5 h-5 mx-auto mb-1.5 text-slate-600" />
            No OTC candles collected yet. Start the Tampermonkey script on Pocket Option.
          </div>
        )}

        {/* Per-symbol rows */}
        {sorted.slice(0, 6).map(s => {
          const meta = healthMeta[s.health] || healthMeta.unknown;
          const Icon = meta.Icon;
          const barWidth = Math.round((s.gap_ratio || 0) * 100);
          return (
            <div
              key={s.symbol}
              data-testid={`otc-symbol-row-${s.symbol}`}
              className="bg-slate-800/50 rounded-lg p-2.5 border border-slate-700/30"
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <Icon className={`w-3 h-3 ${meta.icon}`} />
                  <span className="text-xs font-medium text-white">{s.symbol}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono">
                  <span className="text-slate-400">
                    {(s.candle_count || 0).toLocaleString()} rows
                  </span>
                  <span className={meta.icon}>
                    {formatAge(s.last_scrape_age_seconds)}
                  </span>
                </div>
              </div>

              {/* Ingestion bar */}
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-slate-700/60 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${meta.bar} transition-all duration-500`}
                    style={{ width: `${barWidth}%` }}
                  />
                </div>
                <span className="text-[10px] text-slate-500 font-mono w-20 text-right">
                  {s.ingestion_rate_per_min || 0}/min
                </span>
              </div>
            </div>
          );
        })}

        {sorted.length > 6 && (
          <div className="text-center text-[10px] text-slate-500">
            +{sorted.length - 6} more symbols
          </div>
        )}
      </div>
    </Card>
  );
};

export default OTCDataHealthWidget;
