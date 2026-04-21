import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { ShieldCheck, ShieldAlert, Shield, RefreshCw, Link as LinkIcon } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const healthMeta = {
  healthy:  { label: 'CONNECTED', text: 'text-emerald-300', bg: 'bg-emerald-900/40', border: 'border-emerald-500/40', Icon: ShieldCheck, iconColor: 'text-emerald-400' },
  expiring: { label: 'EXPIRING',  text: 'text-amber-300',   bg: 'bg-amber-900/40',   border: 'border-amber-500/40',   Icon: ShieldAlert, iconColor: 'text-amber-400' },
  stale:    { label: 'STALE',     text: 'text-amber-300',   bg: 'bg-amber-900/40',   border: 'border-amber-500/40',   Icon: ShieldAlert, iconColor: 'text-amber-400' },
  expired:  { label: 'EXPIRED',   text: 'text-red-300',     bg: 'bg-red-900/40',     border: 'border-red-500/40',     Icon: Shield,      iconColor: 'text-red-400' },
  missing:  { label: 'NO SSID',   text: 'text-slate-300',   bg: 'bg-slate-900/40',   border: 'border-slate-500/40',   Icon: Shield,      iconColor: 'text-slate-400' },
};

const fmtAge = (s) => {
  if (s === null || s === undefined) return '—';
  if (s < 0) return '0s';
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
};

const SSIDStatusWidget = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/po/ssid/status`);
      if (res.data.success) setData(res.data);
    } catch (_e) { /* ignore */ }
    setLoading(false);
  }, []);

  const verifyConnection = async () => {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await axios.post(`${API}/po/ssid/connect`);
      setVerifyResult(res.data);
    } catch (e) {
      setVerifyResult({ success: false, error: e?.response?.data?.detail || e.message });
    }
    setVerifying(false);
  };

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 15000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  if (!data) return null;

  const meta = healthMeta[data.health] || healthMeta.missing;
  const Icon = meta.Icon;

  return (
    <Card data-testid="ssid-status-widget" className="bg-slate-900/80 border border-indigo-500/20 backdrop-blur-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-600/20 to-violet-600/20 border-b border-indigo-500/20">
        <div className="flex items-center gap-2">
          <LinkIcon className="w-4 h-4 text-indigo-400" />
          <span className="text-sm font-bold text-white tracking-wide">SSID BRIDGE</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            data-testid="ssid-health-badge"
            className={`text-xs ${meta.text} ${meta.bg} border ${meta.border} flex items-center gap-1`}
          >
            <Icon className={`w-3 h-3 ${meta.iconColor}`} />
            {meta.label}
          </Badge>
          <Button
            data-testid="ssid-refresh-btn"
            size="sm"
            variant="ghost"
            onClick={fetchStatus}
            disabled={loading}
            className="h-6 w-6 p-0 text-indigo-400 hover:text-white"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <div className="p-4 space-y-2 text-xs">
        {!data.has_ssid && (
          <div className="text-slate-400 leading-relaxed" data-testid="ssid-instructions">
            Install the Tampermonkey script and open any Pocket Option trading page. The SSID will be captured automatically from the WebSocket auth frame.
          </div>
        )}

        {data.has_ssid && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Account:</span>
              <span className="font-mono text-white" data-testid="ssid-account">
                uid {data.uid ?? '—'} · {data.is_demo ? 'DEMO' : 'LIVE'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Last Seen:</span>
              <span className={`font-mono ${meta.iconColor}`} data-testid="ssid-last-seen">
                {fmtAge(data.age_seconds)} ago
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Expires In:</span>
              <span className={`font-mono ${meta.iconColor}`} data-testid="ssid-expires-in">
                {fmtAge(data.expires_in_seconds)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Source:</span>
              <span className="font-mono text-slate-500 truncate ml-2 max-w-[140px]">{data.source || '—'}</span>
            </div>

            <div className="pt-2">
              <Button
                data-testid="ssid-verify-btn"
                size="sm"
                onClick={verifyConnection}
                disabled={verifying}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs h-8"
              >
                {verifying ? 'Verifying…' : 'Verify WS Connection'}
              </Button>
              {verifyResult && (
                <div
                  data-testid="ssid-verify-result"
                  className={`mt-2 text-[11px] font-mono ${verifyResult.connected ? 'text-emerald-400' : 'text-red-400'}`}
                >
                  {verifyResult.connected
                    ? `✓ Connected · balance=$${verifyResult.balance ?? '—'}`
                    : `✗ ${verifyResult.error || 'Connection failed'}`}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </Card>
  );
};

export default SSIDStatusWidget;
