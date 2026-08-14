import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import {
  Activity, Wifi, WifiOff, AlertTriangle, CheckCircle2, Clock,
  Zap, TrendingUp, ShieldCheck, ShieldAlert, RefreshCw, Copy, Check,
  Cpu, Target, LineChart,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * Iter 106 — Connection Dashboard for the Mobile Auto-Trader page.
 *
 * Redesigned "at-a-glance" health panel so the user can tell instantly if
 * Tampermonkey is talking to the backend. Fixes the pain of "trades stop
 * working and I don't know why until I dig into logs".
 *
 * Live metrics (auto-refresh every 4s):
 *   1. Connection state chip (fresh / stale / lost / never seen)
 *   2. Installed script version vs latest (warns on stale)
 *   3. Asset & timeframe TM is currently tracking
 *   4. SSID bridge status (green = live token, grey = no token)
 *   5. Network latency (Iter 103 backend probe) — last / p50 / p99 ms
 *   6. Heartbeat age with a spinning ticker so you can SEE it updating
 */
const TampermonkeyConnectionDashboard = () => {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);  // increments every second → forces "N seconds ago" recalc
  const [copied, setCopied] = useState(false);
  const [manuallyRefreshing, setManuallyRefreshing] = useState(false);
  const wasConnectedRef = useRef(false);

  // ---- Poll /api/tampermonkey/status every 4s ----
  useEffect(() => {
    let cancelled = false;
    const load = async (isManual = false) => {
      try {
        if (isManual) setManuallyRefreshing(true);
        const r = await fetch(`${API}/api/tampermonkey/status`, { cache: 'no-store' });
        const data = await r.json();
        if (cancelled) return;
        setStatus(data);
        setError(null);
        // Fire a soft toast-style alert on state transition to LOST
        const nowConnected = !!data.connection_active;
        if (wasConnectedRef.current && !nowConnected) {
          // Best-effort browser notification if user granted permission
          try {
            if ('Notification' in window && Notification.permission === 'granted') {
              new Notification('Tampermonkey disconnected', {
                body: 'The bot lost contact with the backend. Check your PO tab.',
                silent: false,
              });
            }
          } catch (_e) { /* silent */ }
        }
        wasConnectedRef.current = nowConnected;
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      } finally {
        if (isManual) setManuallyRefreshing(false);
      }
    };
    load();
    const iv = setInterval(() => load(), 4000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  // ---- 1-second ticker for "N seconds ago" display ----
  useEffect(() => {
    const iv = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(iv);
  }, []);

  // Request notification permission once
  useEffect(() => {
    try {
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
      }
    } catch (_e) { /* silent */ }
  }, []);

  // ---- Derived UI values ----
  const derived = useMemo(() => {
    if (!status) return null;
    const state = status.connection_state || 'never_seen';
    const stale = !!status.is_stale;
    const heartbeatIso = status.settings?.last_heartbeat || null;
    let heartbeatAgeSec = null;
    if (heartbeatIso) {
      const t = new Date(heartbeatIso).getTime();
      if (!Number.isNaN(t)) heartbeatAgeSec = Math.max(0, (Date.now() - t) / 1000);
    }

    const bgByState = {
      fresh: 'from-emerald-900/40 via-emerald-800/20 to-slate-900',
      stale: 'from-amber-900/40 via-amber-800/20 to-slate-900',
      lost:  'from-rose-900/40 via-rose-800/20 to-slate-900',
      never_seen: 'from-slate-800/60 via-slate-800/30 to-slate-900',
    };
    const dotByState = {
      fresh: 'bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.7)]',
      stale: 'bg-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.6)]',
      lost:  'bg-rose-500 shadow-[0_0_12px_rgba(244,63,94,0.6)]',
      never_seen: 'bg-slate-500',
    };
    const chipByState = {
      fresh: 'bg-emerald-500/20 text-emerald-300 border-emerald-400/40',
      stale: 'bg-amber-500/20 text-amber-300 border-amber-400/40',
      lost:  'bg-rose-500/20 text-rose-300 border-rose-400/40',
      never_seen: 'bg-slate-500/20 text-slate-300 border-slate-400/40',
    };
    const labelByState = {
      fresh: 'CONNECTED',
      stale: 'STALE — heartbeat delayed',
      lost:  'DISCONNECTED',
      never_seen: 'NEVER SEEN — install & open PO',
    };
    const helpByState = {
      fresh: 'Tampermonkey is actively sending heartbeats. Trades will fire normally.',
      stale: 'Last heartbeat was more than 30s ago. The PO tab may be backgrounded or your network is slow.',
      lost:  'Tampermonkey has not checked in for over 2 minutes. Open your Pocket Option tab and confirm the userscript is enabled.',
      never_seen: 'Install the userscript below, then open Pocket Option in the same browser.',
    };

    return {
      state,
      stale,
      heartbeatAgeSec,
      bg: bgByState[state],
      dot: dotByState[state],
      chip: chipByState[state],
      label: labelByState[state],
      help: helpByState[state],
    };
  }, [status, tick]);   // tick refresh forces re-render every 1s

  const fmtAge = (sec) => {
    if (sec == null || !Number.isFinite(sec)) return '—';
    if (sec < 60) return `${Math.round(sec)}s ago`;
    if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
    return `${Math.round(sec / 3600)}h ago`;
  };

  const fmtMs = (v) => {
    if (v == null || !Number.isFinite(v)) return '—';
    return v < 10 ? `${v.toFixed(1)} ms` : `${Math.round(v)} ms`;
  };

  const scriptUrl = API ? `${API.replace(/\/api$/, '')}/api/tampermonkey/script` : '';

  const copyScriptUrl = () => {
    try {
      navigator.clipboard.writeText(scriptUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_e) { /* silent */ }
  };

  const manualRefresh = async () => {
    try {
      setManuallyRefreshing(true);
      const r = await fetch(`${API}/api/tampermonkey/status`, { cache: 'no-store' });
      const data = await r.json();
      setStatus(data);
      setError(null);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setManuallyRefreshing(false);
    }
  };

  if (!status && !error) {
    return (
      <Card className="bg-slate-800/50 border-slate-700 mb-6">
        <CardContent className="p-8 text-center text-slate-400">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-cyan-400 border-t-transparent mx-auto mb-3"></div>
          Loading Tampermonkey status…
        </CardContent>
      </Card>
    );
  }

  if (error && !status) {
    return (
      <Card className="bg-rose-950/40 border-rose-800/60 mb-6" data-testid="tm-conn-error">
        <CardContent className="p-6">
          <div className="flex items-center gap-3 text-rose-300">
            <AlertTriangle className="w-5 h-5" />
            <div>
              <p className="font-semibold">Cannot reach status endpoint</p>
              <p className="text-sm text-rose-400/80">{error}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const active = status.active_target || {};
  const lat = status.network_latency || {};

  return (
    <div className="space-y-4" data-testid="tm-connection-dashboard">
      {/* ---------- Hero status card ---------- */}
      <Card
        className={`bg-gradient-to-br ${derived.bg} border-slate-700/60 shadow-2xl overflow-hidden`}
        data-testid="tm-conn-hero"
      >
        <CardContent className="p-6">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className={`w-4 h-4 rounded-full ${derived.dot} ${derived.state === 'fresh' ? 'animate-pulse' : ''}`}></div>
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight" data-testid="tm-conn-state-label">
                    {derived.label}
                  </h2>
                  <Badge variant="outline" className={`text-[10px] uppercase tracking-wider ${derived.chip}`}>
                    {derived.state}
                  </Badge>
                </div>
                <p className="text-sm text-slate-300/90 mt-1 max-w-2xl">{derived.help}</p>
              </div>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Button
                onClick={manualRefresh}
                disabled={manuallyRefreshing}
                variant="outline"
                size="sm"
                className="border-slate-600 hover:bg-slate-700/60 text-slate-200"
                data-testid="tm-conn-refresh"
              >
                <RefreshCw className={`w-4 h-4 mr-1 ${manuallyRefreshing ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>

          {/* Heartbeat ticker */}
          <div className="mt-5 flex items-center gap-3 text-sm text-slate-300">
            <Clock className="w-4 h-4 text-cyan-400" />
            <span>Last heartbeat:</span>
            <span className="font-mono text-cyan-300" data-testid="tm-conn-heartbeat-age">
              {fmtAge(derived.heartbeatAgeSec)}
            </span>
            {status.settings?.last_heartbeat && (
              <span className="text-slate-500 text-xs hidden md:inline">
                ({new Date(status.settings.last_heartbeat).toLocaleTimeString()})
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ---------- Metric grid ---------- */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3" data-testid="tm-conn-metrics">
        {/* Version */}
        <Card className={`bg-slate-800/60 border ${derived.stale ? 'border-amber-500/60' : 'border-slate-700/60'}`} data-testid="tm-metric-version">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-400 uppercase tracking-wider">Script Version</span>
              <Cpu className="w-4 h-4 text-slate-500" />
            </div>
            <div className="text-lg font-bold text-white font-mono">
              {status.installed_version || <span className="text-slate-500">—</span>}
            </div>
            {status.latest_version && (
              <div className="text-xs mt-1">
                {derived.stale ? (
                  <span className="text-amber-400 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Update available: v{status.latest_version}
                  </span>
                ) : status.installed_version ? (
                  <span className="text-emerald-400/80 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Up to date (latest: {status.latest_version})
                  </span>
                ) : (
                  <span className="text-slate-500">Latest: v{status.latest_version}</span>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Active asset & timeframe */}
        <Card className="bg-slate-800/60 border-slate-700/60" data-testid="tm-metric-target">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-400 uppercase tracking-wider">Tracking</span>
              <Target className="w-4 h-4 text-slate-500" />
            </div>
            <div className="text-lg font-bold text-white font-mono">
              {active.asset || <span className="text-slate-500">—</span>}
            </div>
            <div className="text-xs mt-1 text-slate-400">
              TF <span className="text-cyan-300 font-mono">{active.timeframe || '—'}</span>
              {active.chart_type && (
                <>
                  <span className="mx-1 text-slate-600">·</span>
                  <span className="text-slate-300">{active.chart_type}</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* SSID Bridge */}
        <Card className="bg-slate-800/60 border-slate-700/60" data-testid="tm-metric-ssid">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-400 uppercase tracking-wider">SSID Bridge</span>
              {status.ssid_bridge_active ? (
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
              ) : (
                <ShieldAlert className="w-4 h-4 text-slate-500" />
              )}
            </div>
            <div className="text-lg font-bold">
              {status.ssid_bridge_active ? (
                <span className="text-emerald-400">Active</span>
              ) : (
                <span className="text-slate-400">Inactive</span>
              )}
            </div>
            <div className="text-xs mt-1 text-slate-500">
              {status.ssid_bridge_active
                ? 'Direct-WS trading unlocked'
                : 'DOM-click fallback in use'}
            </div>
          </CardContent>
        </Card>

        {/* Network latency last */}
        <Card className="bg-slate-800/60 border-slate-700/60" data-testid="tm-metric-latency-now">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-400 uppercase tracking-wider">Latency · Now</span>
              <Zap className="w-4 h-4 text-slate-500" />
            </div>
            <div className={`text-lg font-bold font-mono ${
              lat.last_ms == null ? 'text-slate-500'
                : lat.last_ms < 120 ? 'text-emerald-400'
                : lat.last_ms < 300 ? 'text-amber-400' : 'text-rose-400'
            }`}>
              {fmtMs(lat.last_ms)}
            </div>
            <div className="text-xs mt-1 text-slate-500">
              {lat.sample_count ? `${lat.sample_count} samples` : 'warming up'}
            </div>
          </CardContent>
        </Card>

        {/* Network latency p50 */}
        <Card className="bg-slate-800/60 border-slate-700/60" data-testid="tm-metric-latency-p50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-400 uppercase tracking-wider">Latency · p50</span>
              <LineChart className="w-4 h-4 text-slate-500" />
            </div>
            <div className={`text-lg font-bold font-mono ${
              lat.p50_ms == null ? 'text-slate-500'
                : lat.p50_ms < 120 ? 'text-emerald-400'
                : lat.p50_ms < 300 ? 'text-amber-400' : 'text-rose-400'
            }`}>
              {fmtMs(lat.p50_ms)}
            </div>
            <div className="text-xs mt-1 text-slate-500">median RTT</div>
          </CardContent>
        </Card>

        {/* Network latency p99 */}
        <Card className="bg-slate-800/60 border-slate-700/60" data-testid="tm-metric-latency-p99">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-400 uppercase tracking-wider">Latency · p99</span>
              <TrendingUp className="w-4 h-4 text-slate-500" />
            </div>
            <div className={`text-lg font-bold font-mono ${
              lat.p99_ms == null ? 'text-slate-500'
                : lat.p99_ms < 120 ? 'text-emerald-400'
                : lat.p99_ms < 300 ? 'text-amber-400' : 'text-rose-400'
            }`}>
              {fmtMs(lat.p99_ms)}
            </div>
            <div className="text-xs mt-1 text-slate-500">tail latency</div>
          </CardContent>
        </Card>
      </div>

      {/* ---------- Install / Update card (only visible if never_seen or stale) ---------- */}
      {(derived.state === 'never_seen' || derived.stale) && (
        <Card className="bg-slate-800/70 border-cyan-800/50" data-testid="tm-install-hint">
          <CardContent className="p-4">
            <div className="flex items-start gap-3 flex-wrap">
              {derived.state === 'never_seen' ? (
                <WifiOff className="w-5 h-5 text-slate-400 mt-1" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-400 mt-1" />
              )}
              <div className="flex-1 min-w-[240px]">
                <p className="text-white font-semibold text-sm">
                  {derived.state === 'never_seen'
                    ? 'Install the userscript to start trading'
                    : `Your userscript is behind — update to v${status.latest_version}`}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Open the URL below in Tampermonkey → New Script → paste → Save.
                </p>
                <div className="flex gap-2 mt-2 flex-wrap">
                  <code className="text-xs text-cyan-300 bg-slate-950/60 px-2 py-1 rounded border border-slate-700 font-mono break-all">
                    {scriptUrl}
                  </code>
                  <Button
                    onClick={copyScriptUrl}
                    size="sm"
                    variant="outline"
                    className="border-slate-600 text-slate-200 hover:bg-slate-700/60"
                    data-testid="tm-copy-url"
                  >
                    {copied ? <Check className="w-3 h-3 mr-1 text-emerald-400" /> : <Copy className="w-3 h-3 mr-1" />}
                    {copied ? 'Copied' : 'Copy URL'}
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default TampermonkeyConnectionDashboard;
