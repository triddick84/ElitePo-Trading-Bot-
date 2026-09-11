/**
 * Iter 135 — PerfPill: live yfinance TTL cache hit-rate pill.
 *
 * Renders a compact pill on the top-right of the app header showing:
 *   • ⚡ hit-rate percentage (colour-coded green > 70 %, amber > 40 %, else grey)
 *   • cache size
 *
 * Auto-refreshes every 6 s. Hover shows a mini-tooltip with full stats.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Zap } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PerfPill = () => {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const fetchStats = async () => {
      try {
        const r = await axios.get(`${API}/perf/yf-cache`, { timeout: 4000 });
        if (!cancelled && r.data?.success) setStats(r.data);
      } catch (_e) {
        // silent — backend may still be starting
      }
    };
    fetchStats();
    const t = setInterval(fetchStats, 6000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  if (!stats) return null;

  const hitRate = Number(stats.hit_rate_pct || 0);
  const tone =
    hitRate >= 70 ? 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10' :
    hitRate >= 40 ? 'text-amber-300 border-amber-500/40 bg-amber-500/10' :
                    'text-slate-400 border-slate-600/40 bg-slate-800/40';

  return (
    <div
      data-testid="perf-pill"
      title={`yfinance cache · ${stats.hits} hits / ${stats.misses} misses · size ${stats.size}/${stats.max_entries} · TTL ${stats.ttl_seconds}s`}
      className={`hidden md:inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full text-xs font-medium border transition-colors cursor-help ${tone}`}
    >
      <Zap className="w-3 h-3" />
      <span data-testid="perf-pill-hitrate">{hitRate.toFixed(0)}%</span>
      <span className="text-[10px] opacity-70">cache</span>
    </div>
  );
};

export default PerfPill;
