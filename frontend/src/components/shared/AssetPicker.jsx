/**
 * AssetPicker — reusable asset + market selector.
 *
 * Iter 83 (Jul 2026).
 *
 * Consumes GET /api/backtest/assets-universe (~366 symbols across Regular +
 * OTC markets, split into 10 classes: Forex, Commodities, Crypto, Indices,
 * US Stocks — each with a Regular and OTC variant).
 *
 * Provides bulk controls the user asked for:
 *   ▸ Select All Regular
 *   ▸ Select All OTC
 *   ▸ Select All / Clear All
 *   ▸ Per-class All / Clear (matches BacktestingPage behaviour)
 *   ▸ Text-search filter across symbols
 *
 * Props:
 *   value             string[]                current selection
 *   onChange          (next: string[]) => void
 *   restrictToMarket  "regular" | "otc" | null  (default null = both allowed)
 *   maxHeight         string (Tailwind: "max-h-80" etc — default "max-h-96")
 *   defaultCollapsed  boolean — start with classes collapsed (default true for
 *                     large lists, false when total ≤ 40)
 *   testIdPrefix      string — override the "asset-picker" data-testid prefix
 *                     when multiple pickers exist on the same page.
 */

import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Checkbox } from '../ui/checkbox';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const CLASS_ICON = {
  forex: '💱',
  forex_otc: '🟢💱',
  commodities: '🪙',
  commodities_otc: '🟢🪙',
  crypto: '₿',
  crypto_otc: '🟢₿',
  indices: '📊',
  indices_otc: '🟢📊',
  stocks: '🏛',
  stocks_otc: '🟢🏛',
};

export const AssetPicker = ({
  value = [],
  onChange,
  restrictToMarket = null,
  maxHeight = 'max-h-96',
  defaultCollapsed = null,
  testIdPrefix = 'asset-picker',
  title = 'Assets & Markets',
  description = 'Select individual symbols, entire markets, or specific asset classes.',
}) => {
  const [classes, setClasses] = useState([]);       // raw response from API
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [collapsed, setCollapsed] = useState({});   // class-id → boolean

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const r = await axios.get(`${API_URL}/api/backtest/assets-universe`);
        if (cancelled) return;
        const all = r.data?.classes || [];
        const filtered = restrictToMarket === 'regular'
          ? all.filter(c => !c.id.endsWith('_otc'))
          : restrictToMarket === 'otc'
            ? all.filter(c => c.id.endsWith('_otc'))
            : all;
        setClasses(filtered);
        // Sensible default: collapse only when total symbols > 40
        const total = filtered.reduce((n, c) => n + (c.symbols?.length || 0), 0);
        const shouldCollapse = defaultCollapsed !== null ? defaultCollapsed : total > 40;
        const init = {};
        filtered.forEach(c => { init[c.id] = shouldCollapse; });
        setCollapsed(init);
        setError(null);
      } catch (e) {
        if (!cancelled) setError(e.message || 'Failed to load asset universe');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [restrictToMarket, defaultCollapsed]);

  // Fast lookups + computed groupings ----------------------------------------
  const selectedSet = useMemo(() => new Set(value), [value]);

  const allSymbols = useMemo(
    () => classes.flatMap(c => c.symbols || []),
    [classes]
  );

  const regularSymbols = useMemo(
    () => classes.filter(c => !c.id.endsWith('_otc')).flatMap(c => c.symbols || []),
    [classes]
  );

  const otcSymbols = useMemo(
    () => classes.filter(c => c.id.endsWith('_otc')).flatMap(c => c.symbols || []),
    [classes]
  );

  const selectedBreakdown = useMemo(() => {
    let reg = 0; let otc = 0;
    value.forEach(v => {
      if (v.includes('_OTC')) otc += 1;
      else reg += 1;
    });
    return { reg, otc };
  }, [value]);

  const filteredClasses = useMemo(() => {
    if (!search.trim()) return classes;
    const q = search.trim().toUpperCase();
    return classes
      .map(c => ({ ...c, symbols: (c.symbols || []).filter(s => s.toUpperCase().includes(q)) }))
      .filter(c => c.symbols.length > 0);
  }, [classes, search]);

  // Actions ------------------------------------------------------------------
  const setNext = (next) => onChange && onChange([...new Set(next)]);

  const toggleOne = (sym) => {
    if (selectedSet.has(sym)) setNext(value.filter(v => v !== sym));
    else setNext([...value, sym]);
  };

  const selectSymbols = (syms) => setNext([...value, ...syms]);
  const clearSymbols  = (syms) => {
    const drop = new Set(syms);
    setNext(value.filter(v => !drop.has(v)));
  };

  const selectAll     = () => setNext(allSymbols);
  const clearAll      = () => setNext([]);
  const selectAllRegular = () => selectSymbols(regularSymbols);
  const clearAllRegular  = () => clearSymbols(regularSymbols);
  const selectAllOtc     = () => selectSymbols(otcSymbols);
  const clearAllOtc      = () => clearSymbols(otcSymbols);

  const toggleClassCollapse = (id) => setCollapsed(p => ({ ...p, [id]: !p[id] }));

  // Class-level count helpers
  const classSelectedCount = (c) => {
    const list = c.symbols || [];
    let n = 0;
    for (const s of list) if (selectedSet.has(s)) n++;
    return n;
  };

  // Render -------------------------------------------------------------------
  if (loading) {
    return (
      <Card className="glass-dark border-slate-700/50">
        <CardHeader>
          <CardTitle className="text-white">{title}</CardTitle>
          <CardDescription>Loading asset universe…</CardDescription>
        </CardHeader>
      </Card>
    );
  }
  if (error) {
    return (
      <Card className="glass-dark border-red-700/50">
        <CardHeader>
          <CardTitle className="text-red-400">{title}</CardTitle>
          <CardDescription className="text-red-300">
            Failed to load asset universe: {error}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const showRegularBulk = restrictToMarket !== 'otc' && regularSymbols.length > 0;
  const showOtcBulk     = restrictToMarket !== 'regular' && otcSymbols.length > 0;
  const showBothBulk    = showRegularBulk && showOtcBulk;

  return (
    <Card className="glass-dark border-slate-700/50" data-testid={testIdPrefix}>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-white flex items-center gap-2">
              {title}
              <Badge
                data-testid={`${testIdPrefix}-selected-count`}
                className="bg-purple-600 text-xs"
              >
                {value.length} selected
              </Badge>
            </CardTitle>
            <CardDescription className="mt-1">
              {description}{' '}
              <span className="text-xs text-slate-500">
                ({allSymbols.length} available · {regularSymbols.length} Regular · {otcSymbols.length} OTC)
              </span>
            </CardDescription>
            {value.length > 0 && (
              <div className="mt-2 flex gap-2 text-xs">
                <Badge className="bg-blue-500/20 text-blue-300 border border-blue-500/40" data-testid={`${testIdPrefix}-breakdown-regular`}>
                  {selectedBreakdown.reg} Regular
                </Badge>
                <Badge className="bg-green-500/20 text-green-300 border border-green-500/40" data-testid={`${testIdPrefix}-breakdown-otc`}>
                  {selectedBreakdown.otc} OTC
                </Badge>
              </div>
            )}
          </div>
        </div>

        {/* Bulk toolbar */}
        <div className="mt-4 flex flex-wrap gap-2">
          {showBothBulk && (
            <>
              <Button
                data-testid={`${testIdPrefix}-select-all`}
                size="sm"
                variant="outline"
                onClick={selectAll}
                className="border-purple-500/50 text-purple-300 hover:bg-purple-500/20"
              >
                Select All ({allSymbols.length})
              </Button>
              <Button
                data-testid={`${testIdPrefix}-clear-all`}
                size="sm"
                variant="outline"
                onClick={clearAll}
                className="border-slate-500/50 text-slate-300 hover:bg-slate-500/20"
              >
                Clear All
              </Button>
              <span className="mx-1 border-l border-slate-700" />
            </>
          )}
          {showRegularBulk && (
            <>
              <Button
                data-testid={`${testIdPrefix}-select-all-regular`}
                size="sm"
                variant="outline"
                onClick={selectAllRegular}
                className="border-blue-500/50 text-blue-300 hover:bg-blue-500/20"
              >
                All Regular ({regularSymbols.length})
              </Button>
              <Button
                data-testid={`${testIdPrefix}-clear-all-regular`}
                size="sm"
                variant="ghost"
                onClick={clearAllRegular}
                className="text-xs text-blue-300/70 hover:text-blue-300"
              >
                Clear Regular
              </Button>
            </>
          )}
          {showOtcBulk && (
            <>
              <Button
                data-testid={`${testIdPrefix}-select-all-otc`}
                size="sm"
                variant="outline"
                onClick={selectAllOtc}
                className="border-green-500/50 text-green-300 hover:bg-green-500/20"
              >
                All OTC ({otcSymbols.length})
              </Button>
              <Button
                data-testid={`${testIdPrefix}-clear-all-otc`}
                size="sm"
                variant="ghost"
                onClick={clearAllOtc}
                className="text-xs text-green-300/70 hover:text-green-300"
              >
                Clear OTC
              </Button>
            </>
          )}
        </div>

        {/* Search */}
        <div className="mt-3">
          <Input
            data-testid={`${testIdPrefix}-search`}
            placeholder="Search symbols (e.g. EURUSD, BTC, XAU)…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-slate-900/60 border-slate-700 text-slate-200 placeholder:text-slate-500"
          />
        </div>
      </CardHeader>

      <CardContent className={`space-y-3 ${maxHeight} overflow-y-auto pr-1`}>
        {filteredClasses.length === 0 && (
          <div className="text-center text-slate-500 py-8 text-sm" data-testid={`${testIdPrefix}-empty`}>
            No symbols match "{search}".
          </div>
        )}
        {filteredClasses.map(cls => {
          const isOtc = cls.id.endsWith('_otc');
          const selCount = classSelectedCount(cls);
          const total = cls.symbols?.length || 0;
          const isFullySelected = selCount === total && total > 0;
          const isCollapsed = collapsed[cls.id];
          return (
            <div
              key={cls.id}
              data-testid={`${testIdPrefix}-class-${cls.id}`}
              className={`rounded-lg border ${
                isOtc ? 'border-green-500/20 bg-green-500/5' : 'border-blue-500/20 bg-blue-500/5'
              } p-3`}
            >
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <button
                  onClick={() => toggleClassCollapse(cls.id)}
                  className="flex items-center gap-2 text-white font-medium text-sm"
                  data-testid={`${testIdPrefix}-class-${cls.id}-toggle`}
                >
                  <span className="text-lg leading-none">{CLASS_ICON[cls.id] || (isOtc ? '🟢' : '📈')}</span>
                  <span>{cls.label}</span>
                  <Badge className={`text-[10px] ${isFullySelected ? 'bg-emerald-600' : 'bg-slate-700'}`}>
                    {selCount}/{total}
                  </Badge>
                  <span className="text-slate-500 text-xs">{isCollapsed ? '▶' : '▼'}</span>
                </button>
                <div className="flex gap-1">
                  <Button
                    data-testid={`${testIdPrefix}-class-${cls.id}-all`}
                    size="sm"
                    variant="ghost"
                    className="text-xs h-7 px-2 text-emerald-300 hover:bg-emerald-500/10"
                    onClick={() => selectSymbols(cls.symbols || [])}
                  >
                    All
                  </Button>
                  <Button
                    data-testid={`${testIdPrefix}-class-${cls.id}-clear`}
                    size="sm"
                    variant="ghost"
                    className="text-xs h-7 px-2 text-slate-400 hover:bg-slate-500/10"
                    onClick={() => clearSymbols(cls.symbols || [])}
                  >
                    Clear
                  </Button>
                </div>
              </div>
              {!isCollapsed && (
                <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-1">
                  {(cls.symbols || []).map(sym => {
                    const selected = selectedSet.has(sym);
                    return (
                      <label
                        key={sym}
                        data-testid={`${testIdPrefix}-symbol-${sym}`}
                        className={`flex items-center gap-2 p-1.5 rounded cursor-pointer text-xs transition-colors ${
                          selected
                            ? isOtc
                              ? 'bg-green-500/25 text-green-200'
                              : 'bg-blue-500/25 text-blue-200'
                            : 'text-slate-400 hover:bg-slate-800/50'
                        }`}
                      >
                        <Checkbox
                          checked={selected}
                          onCheckedChange={() => toggleOne(sym)}
                          data-testid={`${testIdPrefix}-symbol-${sym}-checkbox`}
                        />
                        <span className="truncate">{sym}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
};

export default AssetPicker;
