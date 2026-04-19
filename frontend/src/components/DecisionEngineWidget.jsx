import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Brain, Shield, TrendingUp, TrendingDown, Activity, Zap, RefreshCw, AlertTriangle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DecisionEngineWidget = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/signals/engine-status`);
      if (res.data.success !== false) setStatus(res.data);
    } catch (e) { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (!status) return null;

  const perf = status.performance || {};
  const models = status.models || {};
  const trainedCount = Object.values(models).filter(m => m.trained).length;

  return (
    <Card data-testid="decision-engine-widget" className="bg-slate-900/80 border border-purple-500/20 backdrop-blur-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-purple-600/20 to-indigo-600/20 border-b border-purple-500/20">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-bold text-white tracking-wide">DECISION ENGINE v2.0</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs text-purple-300 border-purple-500/40">{trainedCount}/{Object.keys(models).length} Models</Badge>
          <Button size="sm" variant="ghost" onClick={fetchStatus} disabled={loading} className="h-6 w-6 p-0 text-purple-400 hover:text-white">
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {/* Performance Row */}
        <div className="grid grid-cols-4 gap-2">
          <div className="text-center">
            <div className={`text-lg font-bold ${perf.win_rate >= 60 ? 'text-emerald-400' : perf.win_rate >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
              {perf.win_rate || 0}%
            </div>
            <div className="text-[10px] text-slate-500">Win Rate</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-cyan-400">{perf.total_trades || 0}</div>
            <div className="text-[10px] text-slate-500">Trades</div>
          </div>
          <div className="text-center">
            <div className={`text-lg font-bold ${perf.sharpe_ratio > 1 ? 'text-emerald-400' : perf.sharpe_ratio > 0 ? 'text-amber-400' : 'text-red-400'}`}>
              {perf.sharpe_ratio || 0}
            </div>
            <div className="text-[10px] text-slate-500">Sharpe</div>
          </div>
          <div className="text-center">
            <div className={`text-lg font-bold ${perf.max_drawdown_pct < 5 ? 'text-emerald-400' : perf.max_drawdown_pct < 10 ? 'text-amber-400' : 'text-red-400'}`}>
              {perf.max_drawdown_pct || 0}%
            </div>
            <div className="text-[10px] text-slate-500">Max DD</div>
          </div>
        </div>

        {/* Risk Status */}
        {perf.consecutive_losses > 0 && (
          <div className={`flex items-center gap-2 p-2 rounded-lg ${perf.consecutive_losses >= 3 ? 'bg-red-500/10 border border-red-500/30' : 'bg-amber-500/10 border border-amber-500/30'}`}>
            <AlertTriangle className={`w-3 h-3 ${perf.consecutive_losses >= 3 ? 'text-red-400' : 'text-amber-400'}`} />
            <span className="text-xs text-slate-300">{perf.consecutive_losses} consecutive losses</span>
          </div>
        )}

        {/* Active Strategies */}
        <div className="flex flex-wrap gap-1">
          {Object.entries(status.active_strategies || {}).map(([strat, active]) => (
            <Badge key={strat} className={`text-[10px] ${active ? 'bg-indigo-600/60' : 'bg-slate-700/60'}`}>
              {strat.replace('_', ' ')}
            </Badge>
          ))}
        </div>

        {/* Models */}
        <div className="grid grid-cols-5 gap-1">
          {Object.entries(models).map(([name, info]) => (
            <div key={name} className={`text-center p-1.5 rounded ${info.trained ? 'bg-emerald-900/30 border border-emerald-500/20' : 'bg-slate-800/50 border border-slate-700/30'}`}>
              <div className="text-[9px] text-slate-400 truncate">{name.replace('_', ' ')}</div>
              <div className={`text-xs font-bold ${info.trained ? 'text-emerald-400' : 'text-slate-600'}`}>
                {info.accuracy || 0}%
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
};

export default DecisionEngineWidget;
