import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { 
  Activity, TrendingUp, TrendingDown, Clock, Zap, 
  RefreshCw, BarChart3, Target, ArrowUp, ArrowDown
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const REGIME_CONFIG = {
  trending_up: { label: 'Trending Up', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30', icon: TrendingUp },
  trending_down: { label: 'Trending Down', color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', icon: TrendingDown },
  ranging: { label: 'Ranging', color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30', icon: Activity },
  high_volatility: { label: 'High Volatility', color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30', icon: Zap },
  low_volatility: { label: 'Low Volatility', color: 'text-sky-400', bg: 'bg-sky-500/10 border-sky-500/30', icon: BarChart3 },
  unknown: { label: 'Analyzing...', color: 'text-slate-400', bg: 'bg-slate-500/10 border-slate-500/30', icon: RefreshCw }
};

const SESSION_CONFIG = {
  asian: { label: 'Asian (Tokyo)', quality: 65, color: 'text-pink-400' },
  london: { label: 'London', quality: 80, color: 'text-sky-400' },
  new_york: { label: 'New York', quality: 75, color: 'text-emerald-400' },
  overlap: { label: 'London/NY Overlap', quality: 95, color: 'text-yellow-400' },
  off_hours: { label: 'Off Hours', quality: 30, color: 'text-slate-500' }
};

const IQ720Widget = ({ selectedAsset }) => {
  const [regimeData, setRegimeData] = useState(null);
  const [signal, setSignal] = useState(null);
  const [kelly, setKelly] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  const symbol = selectedAsset || 'EURUSD';

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [regimeRes, signalRes, kellyRes] = await Promise.all([
        axios.get(`${API}/signals/iq720-market-regime?symbol=${symbol}`).catch(() => null),
        axios.post(`${API}/signals/iq720-ensemble`, { symbol, timeframe: 'M1', candle_count: 100 }).catch(() => null),
        axios.post(`${API}/signals/iq720-kelly`, { win_rate: 0.65, avg_win: 0.82, avg_loss: 1.0 }).catch(() => null)
      ]);

      if (regimeRes?.data?.success) setRegimeData(regimeRes.data);
      if (signalRes?.data) setSignal(signalRes.data);
      if (kellyRes?.data?.success) setKelly(kellyRes.data);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('IQ-720 widget fetch error:', err);
    }
    setLoading(false);
  }, [symbol]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const regime = regimeData?.regime || 'unknown';
  const regimeCfg = REGIME_CONFIG[regime] || REGIME_CONFIG.unknown;
  const RegimeIcon = regimeCfg.icon;
  const session = regimeData?.session || 'unknown';
  const sessionCfg = SESSION_CONFIG[session] || SESSION_CONFIG.off_hours;

  const sigDirection = signal?.signal?.direction;
  const sigConfidence = signal?.signal?.confidence;
  const confirmations = signal?.signal?.confirmations || [];

  return (
    <Card data-testid="iq720-widget" className="bg-slate-900/80 border border-indigo-500/20 backdrop-blur-md overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-600/20 to-violet-600/20 border-b border-indigo-500/20">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-indigo-400" />
          <span className="text-sm font-bold text-white tracking-wide">IQ-720 LIVE</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs text-indigo-300 border-indigo-500/40">{symbol}</Badge>
          <Button
            size="sm"
            variant="ghost"
            onClick={fetchAll}
            disabled={loading}
            className="h-6 w-6 p-0 text-indigo-400 hover:text-white"
            data-testid="iq720-refresh-btn"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {/* Market Regime */}
        <div data-testid="iq720-regime" className={`flex items-center justify-between p-2.5 rounded-lg border ${regimeCfg.bg}`}>
          <div className="flex items-center gap-2">
            <RegimeIcon className={`w-4 h-4 ${regimeCfg.color}`} />
            <span className="text-xs text-slate-400">Market Regime</span>
          </div>
          <span className={`text-sm font-semibold ${regimeCfg.color}`}>{regimeCfg.label}</span>
        </div>

        {/* Session */}
        <div data-testid="iq720-session" className="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/50">
          <div className="flex items-center gap-2">
            <Clock className={`w-4 h-4 ${sessionCfg.color}`} />
            <span className="text-xs text-slate-400">Session</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-sm font-semibold ${sessionCfg.color}`}>{sessionCfg.label}</span>
            <Badge variant="outline" className={`text-xs ${sessionCfg.quality >= 80 ? 'text-emerald-400 border-emerald-500/40' : sessionCfg.quality >= 60 ? 'text-amber-400 border-amber-500/40' : 'text-slate-500 border-slate-600/40'}`}>
              Q:{sessionCfg.quality}
            </Badge>
          </div>
        </div>

        {/* Kelly Position Sizing */}
        {kelly && (
          <div data-testid="iq720-kelly" className="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/50">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-cyan-400" />
              <span className="text-xs text-slate-400">Kelly Size</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-cyan-400">{kelly.kelly_percent}%</span>
              <span className="text-[10px] text-slate-500">of capital</span>
            </div>
          </div>
        )}

        {/* Signal */}
        {signal?.success && sigDirection && (
          <div data-testid="iq720-signal" className={`p-3 rounded-lg border ${sigDirection === 'CALL' ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {sigDirection === 'CALL' ? (
                  <ArrowUp className="w-5 h-5 text-emerald-400" />
                ) : (
                  <ArrowDown className="w-5 h-5 text-red-400" />
                )}
                <span className={`text-base font-black ${sigDirection === 'CALL' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {sigDirection}
                </span>
              </div>
              <Badge className={`text-xs font-bold ${sigConfidence >= 80 ? 'bg-emerald-600/80 text-white' : sigConfidence >= 70 ? 'bg-amber-600/80 text-white' : 'bg-slate-600/80 text-white'}`}>
                {sigConfidence}%
              </Badge>
            </div>
            <div className="flex flex-wrap gap-1">
              {confirmations.slice(0, 4).map((c, i) => (
                <Badge key={i} variant="outline" className="text-[10px] text-slate-300 border-slate-600/50 px-1.5 py-0">
                  {c}
                </Badge>
              ))}
              {confirmations.length > 4 && (
                <Badge variant="outline" className="text-[10px] text-slate-500 border-slate-600/50 px-1.5 py-0">
                  +{confirmations.length - 4}
                </Badge>
              )}
            </div>
          </div>
        )}

        {signal && !signal.success && (
          <div data-testid="iq720-no-signal" className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/50 text-center">
            <span className="text-xs text-slate-500">No clear signal — market conditions unclear</span>
          </div>
        )}

        {/* Footer timestamp */}
        {lastUpdate && (
          <div className="text-right">
            <span className="text-[10px] text-slate-600">
              Updated {lastUpdate.toLocaleTimeString()}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
};

export default IQ720Widget;
