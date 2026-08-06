/**
 * Live Latency Dashboard — Iter 89.
 *
 * Surfaces:
 *   - Rolling p50/p95/p99 per backend route (from `/api/latency/stats`)
 *   - Signal pre-generation buffer hit rate + entries (from `/api/signal-prewarm/stats`)
 *
 * Auto-refreshes every 3 s so operators can watch traffic patterns live.
 */
import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Activity, Zap, TrendingUp, RefreshCw } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const API = BACKEND_URL ? `${BACKEND_URL}/api` : "";

const REFRESH_MS = 3000;

/** Colour a p99 value based on our /signals/latest threshold (250 ms). */
function p99Class(ms) {
  if (ms == null) return "text-slate-500";
  if (ms <= 100) return "text-emerald-400";
  if (ms <= 250) return "text-cyan-400";
  if (ms <= 500) return "text-amber-400";
  return "text-rose-400";
}

/** Cache the highest p99 across all routes for the header. */
function worstRoute(rows) {
  if (!rows || !rows.length) return null;
  return rows.reduce((worst, r) =>
    (r.p99 || 0) > (worst.p99 || 0) ? r : worst, rows[0]);
}

export default function LatencyDashboard() {
  const [routes, setRoutes] = useState([]);
  const [prewarm, setPrewarm] = useState(null);
  const [health, setHealth] = useState(null);
  const [lastFetch, setLastFetch] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchAll = async () => {
    try {
      const [statsRes, healthRes, pwRes] = await Promise.all([
        axios.get(`${API}/latency/stats`, { timeout: 5000 }),
        axios.get(`${API}/latency/healthy?p99_threshold_ms=250`, { timeout: 5000 }),
        axios.get(`${API}/signal-prewarm/stats`, { timeout: 5000 }),
      ]);
      setRoutes((statsRes.data?.routes || []).slice().sort(
        (a, b) => (b.p99 || 0) - (a.p99 || 0),
      ));
      setHealth(healthRes.data || null);
      setPrewarm(pwRes.data || null);
      setLastFetch(new Date());
    } catch (e) {
      // Silent — dashboard is read-only, don't spam toasts
    }
  };

  useEffect(() => {
    fetchAll();
    if (!autoRefresh) return;
    const t = setInterval(fetchAll, REFRESH_MS);
    return () => clearInterval(t);
  }, [autoRefresh]);

  const worst = useMemo(() => worstRoute(routes), [routes]);

  return (
    <div className="space-y-4" data-testid="latency-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="w-6 h-6 text-cyan-400" />
            Live Latency Dashboard
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Rolling percentiles across every backend route · refreshes every {REFRESH_MS / 1000}s
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={fetchAll}
            variant="outline"
            size="sm"
            className="border-slate-700"
            data-testid="latency-dashboard-refresh"
          >
            <RefreshCw className="w-4 h-4 mr-1" />
            Refresh
          </Button>
          <Button
            onClick={() => setAutoRefresh((v) => !v)}
            variant="outline"
            size="sm"
            className={
              autoRefresh
                ? "border-cyan-500/50 text-cyan-400"
                : "border-slate-700 text-slate-500"
            }
            data-testid="latency-dashboard-autorefresh"
          >
            {autoRefresh ? "Live ●" : "Paused"}
          </Button>
        </div>
      </div>

      {/* Summary Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Overall Health */}
        <Card className="glass-dark border-slate-700/50">
          <CardHeader className="pb-2">
            <CardDescription>Overall health</CardDescription>
            <CardTitle className={health?.ok ? "text-emerald-400" : "text-rose-400"}>
              {health?.ok ? "Healthy" : "Degraded"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-400 font-tabular">
            Threshold {(health?.threshold_ms || 250).toFixed(0)} ms
          </CardContent>
        </Card>

        {/* Worst route */}
        <Card className="glass-dark border-slate-700/50">
          <CardHeader className="pb-2">
            <CardDescription>Worst-latency route</CardDescription>
            <CardTitle className={p99Class(worst?.p99)}>
              {worst ? `${(worst.p99 || 0).toFixed(1)} ms` : "—"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-400 font-tabular truncate">
            {worst?.route || "(no traffic)"}
          </CardContent>
        </Card>

        {/* Prewarm hit rate */}
        <Card className="glass-dark border-slate-700/50">
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Zap className="w-3 h-3" />
              Prewarm hit rate
            </CardDescription>
            <CardTitle className="text-cyan-400">
              {prewarm ? `${prewarm.hit_rate_pct}%` : "—"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-400 font-tabular">
            {prewarm ? `${prewarm.hits} hits · ${prewarm.misses} miss` : "—"}
          </CardContent>
        </Card>

        {/* Buffer size */}
        <Card className="glass-dark border-slate-700/50">
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              Prewarm buffer
            </CardDescription>
            <CardTitle className="text-cyan-400">
              {prewarm ? `${prewarm.size} / ${prewarm.tracked_active}` : "—"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-slate-400 font-tabular">
            {prewarm ? `${prewarm.writes} writes · TTL ${prewarm.ttl_seconds}s` : "—"}
          </CardContent>
        </Card>
      </div>

      {/* Routes Table */}
      <Card className="glass-dark border-slate-700/50">
        <CardHeader>
          <CardTitle className="text-white text-lg">Per-route percentiles</CardTitle>
          <CardDescription>
            Sorted by p99 (worst first). Sub-100 ms is green; 100-250 ms cyan; 250-500 ms amber; over 500 ms rose.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {routes.length === 0 ? (
            <div className="text-slate-500 text-sm py-4 text-center" data-testid="latency-dashboard-empty">
              No route samples collected yet. Poll the app briefly and refresh.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="latency-dashboard-routes-table">
                <thead className="text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="text-left py-2 pr-3">Route</th>
                    <th className="text-right py-2 pr-3">n</th>
                    <th className="text-right py-2 pr-3">p50</th>
                    <th className="text-right py-2 pr-3">p95</th>
                    <th className="text-right py-2 pr-3">p99</th>
                    <th className="text-right py-2">max</th>
                  </tr>
                </thead>
                <tbody className="text-slate-200 font-tabular">
                  {routes.slice(0, 30).map((r, i) => (
                    <tr
                      key={r.route}
                      className="border-b border-slate-800/50 hover:bg-slate-800/20"
                      data-testid={`latency-dashboard-route-${i}`}
                    >
                      <td className="py-1.5 pr-3 truncate max-w-md" title={r.route}>
                        {r.route}
                      </td>
                      <td className="py-1.5 pr-3 text-right text-slate-500">{r.count}</td>
                      <td className="py-1.5 pr-3 text-right">{(r.p50 || 0).toFixed(1)}</td>
                      <td className="py-1.5 pr-3 text-right">{(r.p95 || 0).toFixed(1)}</td>
                      <td className={`py-1.5 pr-3 text-right font-semibold ${p99Class(r.p99)}`}>
                        {(r.p99 || 0).toFixed(1)}
                      </td>
                      <td className="py-1.5 text-right text-slate-500">
                        {(r.max || 0).toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Prewarm Buffer Entries */}
      {prewarm && prewarm.entries && prewarm.entries.length > 0 && (
        <Card className="glass-dark border-slate-700/50">
          <CardHeader>
            <CardTitle className="text-white text-lg">Prewarm buffer entries</CardTitle>
            <CardDescription>
              Signals pre-generated for actively-polled (asset, timeframe) combos.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="text-left py-2 pr-3">Asset</th>
                    <th className="text-left py-2 pr-3">TF</th>
                    <th className="text-left py-2 pr-3">Direction</th>
                    <th className="text-right py-2 pr-3">Conf</th>
                    <th className="text-right py-2 pr-3">Age (s)</th>
                    <th className="text-left py-2">Generator</th>
                  </tr>
                </thead>
                <tbody className="text-slate-200 font-tabular">
                  {prewarm.entries.map((e, i) => (
                    <tr
                      key={`${e.asset}-${e.timeframe}`}
                      className="border-b border-slate-800/50"
                      data-testid={`prewarm-entry-${i}`}
                    >
                      <td className="py-1.5 pr-3">{e.asset}</td>
                      <td className="py-1.5 pr-3">{e.timeframe}</td>
                      <td className="py-1.5 pr-3">
                        <Badge
                          className={
                            e.direction === "CALL"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : "bg-rose-500/20 text-rose-400"
                          }
                        >
                          {e.direction}
                        </Badge>
                      </td>
                      <td className="py-1.5 pr-3 text-right">{(e.confidence || 0).toFixed(1)}</td>
                      <td
                        className={`py-1.5 pr-3 text-right ${
                          e.age_sec > (prewarm.ttl_seconds || 3)
                            ? "text-rose-400"
                            : "text-emerald-400"
                        }`}
                      >
                        {(e.age_sec || 0).toFixed(2)}
                      </td>
                      <td className="py-1.5 text-slate-400 text-xs">{e.generator}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {lastFetch && (
        <div className="text-slate-500 text-xs text-right font-tabular">
          Last updated {lastFetch.toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
