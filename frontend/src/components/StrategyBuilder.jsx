import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Switch } from './ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { toast } from 'sonner';
import { 
  Plus, 
  Trash2, 
  Copy, 
  Save, 
  Play,
  Settings,
  TrendingUp,
  Activity,
  BarChart3,
  Layers,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle,
  Zap
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Indicator category icons
const categoryIcons = {
  trend: <TrendingUp className="w-4 h-4" />,
  momentum: <Activity className="w-4 h-4" />,
  volatility: <BarChart3 className="w-4 h-4" />,
  volume: <Layers className="w-4 h-4" />,
  oscillator: <Zap className="w-4 h-4" />,
  pattern: <Settings className="w-4 h-4" />,
  custom: <Settings className="w-4 h-4" />
};

// Comparison operators
const operators = [
  { value: '>', label: 'Greater than (>)' },
  { value: '<', label: 'Less than (<)' },
  { value: '>=', label: 'Greater or equal (>=)' },
  { value: '<=', label: 'Less or equal (<=)' },
  { value: '=', label: 'Equal to (=)' },
  { value: 'crosses_above', label: 'Crosses Above ↗' },
  { value: 'crosses_below', label: 'Crosses Below ↘' }
];

// Timeframe options
const timeframes = [
  { value: '5s', label: '5 Seconds' },
  { value: '15s', label: '15 Seconds' },
  { value: '30s', label: '30 Seconds' },
  { value: '1m', label: '1 Minute' },
  { value: '2m', label: '2 Minutes' },
  { value: '3m', label: '3 Minutes' },
  { value: '5m', label: '5 Minutes' },
  { value: '15m', label: '15 Minutes' },
  { value: '30m', label: '30 Minutes' },
  { value: '1h', label: '1 Hour' }
];

// Asset options - Complete list including OTC markets
const assets = [
  // ===================== REGULAR MARKETS =====================
  // Forex Major
  { value: 'EURUSD', label: 'EUR/USD', category: 'Forex Major', market: 'regular' },
  { value: 'GBPUSD', label: 'GBP/USD', category: 'Forex Major', market: 'regular' },
  { value: 'USDJPY', label: 'USD/JPY', category: 'Forex Major', market: 'regular' },
  { value: 'AUDUSD', label: 'AUD/USD', category: 'Forex Major', market: 'regular' },
  { value: 'USDCHF', label: 'USD/CHF', category: 'Forex Major', market: 'regular' },
  { value: 'USDCAD', label: 'USD/CAD', category: 'Forex Major', market: 'regular' },
  { value: 'NZDUSD', label: 'NZD/USD', category: 'Forex Major', market: 'regular' },
  // Forex Minor
  { value: 'EURGBP', label: 'EUR/GBP', category: 'Forex Minor', market: 'regular' },
  { value: 'EURJPY', label: 'EUR/JPY', category: 'Forex Minor', market: 'regular' },
  { value: 'EURCHF', label: 'EUR/CHF', category: 'Forex Minor', market: 'regular' },
  { value: 'EURCAD', label: 'EUR/CAD', category: 'Forex Minor', market: 'regular' },
  { value: 'EURAUD', label: 'EUR/AUD', category: 'Forex Minor', market: 'regular' },
  { value: 'GBPJPY', label: 'GBP/JPY', category: 'Forex Minor', market: 'regular' },
  { value: 'GBPCHF', label: 'GBP/CHF', category: 'Forex Minor', market: 'regular' },
  { value: 'GBPCAD', label: 'GBP/CAD', category: 'Forex Minor', market: 'regular' },
  { value: 'CHFJPY', label: 'CHF/JPY', category: 'Forex Minor', market: 'regular' },
  { value: 'CADJPY', label: 'CAD/JPY', category: 'Forex Minor', market: 'regular' },
  { value: 'AUDJPY', label: 'AUD/JPY', category: 'Forex Minor', market: 'regular' },
  { value: 'AUDCHF', label: 'AUD/CHF', category: 'Forex Minor', market: 'regular' },
  { value: 'NZDJPY', label: 'NZD/JPY', category: 'Forex Minor', market: 'regular' },
  // Forex Exotic
  { value: 'USDMXN', label: 'USD/MXN', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDBRL', label: 'USD/BRL', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDTRY', label: 'USD/TRY', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDZAR', label: 'USD/ZAR', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDPLN', label: 'USD/PLN', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDSGD', label: 'USD/SGD', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDHKD', label: 'USD/HKD', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDTHB', label: 'USD/THB', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDSEK', label: 'USD/SEK', category: 'Forex Exotic', market: 'regular' },
  { value: 'USDNOK', label: 'USD/NOK', category: 'Forex Exotic', market: 'regular' },
  // Crypto Major
  { value: 'BTCUSD', label: 'BTC/USD', category: 'Crypto', market: 'regular' },
  { value: 'ETHUSD', label: 'ETH/USD', category: 'Crypto', market: 'regular' },
  { value: 'LTCUSD', label: 'LTC/USD', category: 'Crypto', market: 'regular' },
  { value: 'ADAUSD', label: 'ADA/USD', category: 'Crypto', market: 'regular' },
  { value: 'DOTUSD', label: 'DOT/USD', category: 'Crypto', market: 'regular' },
  { value: 'BNBUSD', label: 'BNB/USD', category: 'Crypto', market: 'regular' },
  // Crypto Altcoins
  { value: 'DOGEUSD', label: 'DOGE/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'SOLUSD', label: 'SOL/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'AVAXUSD', label: 'AVAX/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'MATICUSD', label: 'MATIC/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'LINKUSD', label: 'LINK/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'TONUSD', label: 'TON/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'ATOMUSD', label: 'ATOM/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'NEARUSD', label: 'NEAR/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'APTOUSD', label: 'APT/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'OPUSD', label: 'OP/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'ARBUSD', label: 'ARB/USD', category: 'Crypto Alt', market: 'regular' },
  { value: 'UNIUSD', label: 'UNI/USD', category: 'Crypto DeFi', market: 'regular' },
  { value: 'AAVEUSD', label: 'AAVE/USD', category: 'Crypto DeFi', market: 'regular' },
  { value: 'SHIBUSDT', label: 'SHIB/USD', category: 'Crypto Meme', market: 'regular' },
  { value: 'FLOKIUSD', label: 'FLOKI/USD', category: 'Crypto Meme', market: 'regular' },
  // Stocks - Tech
  { value: 'AAPL', label: 'AAPL - Apple', category: 'Stocks Tech', market: 'regular' },
  { value: 'MSFT', label: 'MSFT - Microsoft', category: 'Stocks Tech', market: 'regular' },
  { value: 'GOOGL', label: 'GOOGL - Alphabet', category: 'Stocks Tech', market: 'regular' },
  { value: 'AMZN', label: 'AMZN - Amazon', category: 'Stocks Tech', market: 'regular' },
  { value: 'TSLA', label: 'TSLA - Tesla', category: 'Stocks Tech', market: 'regular' },
  { value: 'META', label: 'META - Meta', category: 'Stocks Tech', market: 'regular' },
  { value: 'NFLX', label: 'NFLX - Netflix', category: 'Stocks Tech', market: 'regular' },
  { value: 'NVDA', label: 'NVDA - NVIDIA', category: 'Stocks Tech', market: 'regular' },
  { value: 'BABA', label: 'BABA - Alibaba', category: 'Stocks Tech', market: 'regular' },
  // Stocks - Financial
  { value: 'JPM', label: 'JPM - JPMorgan', category: 'Stocks Finance', market: 'regular' },
  { value: 'BAC', label: 'BAC - Bank of America', category: 'Stocks Finance', market: 'regular' },
  { value: 'WFC', label: 'WFC - Wells Fargo', category: 'Stocks Finance', market: 'regular' },
  { value: 'GS', label: 'GS - Goldman Sachs', category: 'Stocks Finance', market: 'regular' },
  { value: 'MS', label: 'MS - Morgan Stanley', category: 'Stocks Finance', market: 'regular' },
  // Stocks - Consumer
  { value: 'MCD', label: 'MCD - McDonalds', category: 'Stocks Consumer', market: 'regular' },
  { value: 'KO', label: 'KO - Coca-Cola', category: 'Stocks Consumer', market: 'regular' },
  { value: 'WMT', label: 'WMT - Walmart', category: 'Stocks Consumer', market: 'regular' },
  { value: 'BA', label: 'BA - Boeing', category: 'Stocks Industrial', market: 'regular' },
  { value: 'CAT', label: 'CAT - Caterpillar', category: 'Stocks Industrial', market: 'regular' },
  { value: 'JNJ', label: 'JNJ - J&J', category: 'Stocks Healthcare', market: 'regular' },
  { value: 'PFE', label: 'PFE - Pfizer', category: 'Stocks Healthcare', market: 'regular' },
  // Commodities
  { value: 'XAUUSD', label: 'XAU/USD - Gold', category: 'Commodities', market: 'regular' },
  { value: 'XAGUSD', label: 'XAG/USD - Silver', category: 'Commodities', market: 'regular' },
  { value: 'BRENTOIL', label: 'Brent Oil', category: 'Commodities', market: 'regular' },
  { value: 'WTIUSD', label: 'WTI Crude Oil', category: 'Commodities', market: 'regular' },
  { value: 'NATGAS', label: 'Natural Gas', category: 'Commodities', market: 'regular' },
  { value: 'XPTUSD', label: 'XPT/USD - Platinum', category: 'Commodities', market: 'regular' },
  { value: 'XPDUSD', label: 'XPD/USD - Palladium', category: 'Commodities', market: 'regular' },
  // Indices
  { value: 'US100', label: 'US100 - NASDAQ', category: 'Indices', market: 'regular' },
  { value: 'US30', label: 'US30 - Dow Jones', category: 'Indices', market: 'regular' },
  { value: 'SPX500', label: 'SPX500 - S&P 500', category: 'Indices', market: 'regular' },
  { value: 'US2000', label: 'US2000 - Russell 2000', category: 'Indices', market: 'regular' },
  { value: 'GER40', label: 'GER40 - DAX', category: 'Indices', market: 'regular' },
  { value: 'UK100', label: 'UK100 - FTSE', category: 'Indices', market: 'regular' },
  { value: 'FRA40', label: 'FRA40 - CAC 40', category: 'Indices', market: 'regular' },
  { value: 'ESP35', label: 'ESP35 - IBEX 35', category: 'Indices', market: 'regular' },
  { value: 'ITA40', label: 'ITA40 - FTSE MIB', category: 'Indices', market: 'regular' },
  { value: 'E35EUR', label: 'E35EUR - EuroStoxx', category: 'Indices', market: 'regular' },
  { value: 'JPN225', label: 'JPN225 - Nikkei', category: 'Indices', market: 'regular' },
  { value: 'HK50', label: 'HK50 - Hang Seng', category: 'Indices', market: 'regular' },
  { value: 'CHINA50', label: 'CHINA50 - China A50', category: 'Indices', market: 'regular' },
  { value: 'AUS200', label: 'AUS200 - ASX 200', category: 'Indices', market: 'regular' },
  
  // ===================== OTC MARKETS (24/7 Trading) =====================
  // OTC Forex Major
  { value: 'EURUSD_OTC', label: '🟢 EUR/USD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'GBPUSD_OTC', label: '🟢 GBP/USD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'USDJPY_OTC', label: '🟢 USD/JPY OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'AUDUSD_OTC', label: '🟢 AUD/USD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'USDCHF_OTC', label: '🟢 USD/CHF OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'USDCAD_OTC', label: '🟢 USD/CAD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'NZDUSD_OTC', label: '🟢 NZD/USD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'EURGBP_OTC', label: '🟢 EUR/GBP OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'EURJPY_OTC', label: '🟢 EUR/JPY OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'GBPJPY_OTC', label: '🟢 GBP/JPY OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'AUDCAD_OTC', label: '🟢 AUD/CAD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'GBPCAD_OTC', label: '🟢 GBP/CAD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'GBPAUD_OTC', label: '🟢 GBP/AUD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'AUDNZD_OTC', label: '🟢 AUD/NZD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'NZDCAD_OTC', label: '🟢 NZD/CAD OTC', category: 'OTC Forex', market: 'otc' },
  // OTC Crypto
  { value: 'BTCUSD_OTC', label: '🟢 BTC/USD OTC', category: 'OTC Crypto', market: 'otc' },
  { value: 'ETHUSD_OTC', label: '🟢 ETH/USD OTC', category: 'OTC Crypto', market: 'otc' },
  { value: 'LTCUSD_OTC', label: '🟢 LTC/USD OTC', category: 'OTC Crypto', market: 'otc' },
  // OTC Commodities
  { value: 'XAUUSD_OTC', label: '🟢 Gold OTC', category: 'OTC Commodities', market: 'otc' },
  { value: 'XAGUSD_OTC', label: '🟢 Silver OTC', category: 'OTC Commodities', market: 'otc' },
  // OTC Indices
  { value: 'US100_OTC', label: '🟢 NASDAQ OTC', category: 'OTC Indices', market: 'otc' },
  { value: 'US30_OTC', label: '🟢 Dow Jones OTC', category: 'OTC Indices', market: 'otc' },
  { value: 'SPX500_OTC', label: '🟢 S&P 500 OTC', category: 'OTC Indices', market: 'otc' },
];

// Default empty condition
const createEmptyCondition = () => ({
  id: `cond_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
  indicator: 'RSI',
  parameters: { period: 14 },
  output: 'value',
  operator: '>',
  compare_to: 'value',
  compare_value: 70
});

// Default empty condition group
const createEmptyConditionGroup = () => ({
  id: `group_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
  conditions: [createEmptyCondition()],
  logical_operator: 'AND'
});

// Condition Editor Component
const ConditionEditor = ({ condition, indicators, onChange, onRemove, index }) => {
  const indicatorConfig = indicators[condition.indicator] || {};
  const outputs = indicatorConfig.outputs || ['value'];
  const parameters = indicatorConfig.parameters || {};

  const handleIndicatorChange = (newIndicator) => {
    const newConfig = indicators[newIndicator] || {};
    const newParams = {};
    Object.entries(newConfig.parameters || {}).forEach(([key, config]) => {
      newParams[key] = config.default;
    });
    onChange({
      ...condition,
      indicator: newIndicator,
      parameters: newParams,
      output: (newConfig.outputs || ['value'])[0]
    });
  };

  const handleParameterChange = (paramName, value) => {
    onChange({
      ...condition,
      parameters: { ...condition.parameters, [paramName]: value }
    });
  };

  return (
    <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-600/50 space-y-4">
      <div className="flex items-center justify-between">
        <Badge variant="outline" className="text-xs">
          Condition {index + 1}
        </Badge>
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          className="text-red-400 hover:text-red-300 hover:bg-red-500/20"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Indicator Selection */}
        <div>
          <Label className="text-xs text-slate-400">Indicator</Label>
          <Select value={condition.indicator} onValueChange={handleIndicatorChange}>
            <SelectTrigger className="bg-slate-700/50 border-slate-600">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-slate-800 border-slate-600 max-h-80">
              {Object.entries(indicators).map(([key, config]) => (
                <SelectItem key={key} value={key}>
                  <span className="flex items-center gap-2">
                    {categoryIcons[config.category] || <Settings className="w-4 h-4" />}
                    {config.name}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Output Selection (for multi-output indicators) */}
        {outputs.length > 1 && (
          <div>
            <Label className="text-xs text-slate-400">Output</Label>
            <Select 
              value={condition.output} 
              onValueChange={(v) => onChange({ ...condition, output: v })}
            >
              <SelectTrigger className="bg-slate-700/50 border-slate-600">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-600">
                {outputs.map(output => (
                  <SelectItem key={output} value={output}>
                    {output}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Operator Selection */}
        <div>
          <Label className="text-xs text-slate-400">Operator</Label>
          <Select 
            value={condition.operator} 
            onValueChange={(v) => onChange({ ...condition, operator: v })}
          >
            <SelectTrigger className="bg-slate-700/50 border-slate-600">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-slate-800 border-slate-600">
              {operators.map(op => (
                <SelectItem key={op.value} value={op.value}>
                  {op.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Compare Value */}
        <div>
          <Label className="text-xs text-slate-400">Compare To</Label>
          <Input
            type="number"
            value={condition.compare_value}
            onChange={(e) => onChange({ ...condition, compare_value: parseFloat(e.target.value) || 0 })}
            className="bg-slate-700/50 border-slate-600"
            step="0.01"
          />
        </div>
      </div>

      {/* Indicator Parameters */}
      {Object.keys(parameters).length > 0 && (
        <div className="pt-2 border-t border-slate-600/50">
          <Label className="text-xs text-slate-400 mb-2 block">Parameters</Label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(parameters).map(([paramName, paramConfig]) => (
              <div key={paramName}>
                <Label className="text-xs text-slate-500">{paramConfig.description || paramName}</Label>
                {paramConfig.type === 'select' ? (
                  <Select 
                    value={String(condition.parameters[paramName] || paramConfig.default)}
                    onValueChange={(v) => handleParameterChange(paramName, v)}
                  >
                    <SelectTrigger className="bg-slate-700/50 border-slate-600 h-8 text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-800 border-slate-600">
                      {(paramConfig.options || []).map(opt => (
                        <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    type="number"
                    value={condition.parameters[paramName] || paramConfig.default}
                    onChange={(e) => handleParameterChange(paramName, parseFloat(e.target.value) || paramConfig.default)}
                    min={paramConfig.min}
                    max={paramConfig.max}
                    step={paramConfig.type === 'float' ? 0.1 : 1}
                    className="bg-slate-700/50 border-slate-600 h-8 text-sm"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Condition Group Component
const ConditionGroupEditor = ({ group, indicators, onChange, onRemove, direction }) => {
  const addCondition = () => {
    onChange({
      ...group,
      conditions: [...group.conditions, createEmptyCondition()]
    });
  };

  const updateCondition = (index, updatedCondition) => {
    const newConditions = [...group.conditions];
    newConditions[index] = updatedCondition;
    onChange({ ...group, conditions: newConditions });
  };

  const removeCondition = (index) => {
    if (group.conditions.length > 1) {
      const newConditions = group.conditions.filter((_, i) => i !== index);
      onChange({ ...group, conditions: newConditions });
    }
  };

  return (
    <div className={`p-4 rounded-lg border-2 ${
      direction === 'call' ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'
    }`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Badge className={direction === 'call' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
            {direction === 'call' ? '📈 CALL' : '📉 PUT'} Condition Group
          </Badge>
          <Select 
            value={group.logical_operator} 
            onValueChange={(v) => onChange({ ...group, logical_operator: v })}
          >
            <SelectTrigger className="w-24 h-8 bg-slate-700/50 border-slate-600">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-slate-800 border-slate-600">
              <SelectItem value="AND">AND</SelectItem>
              <SelectItem value="OR">OR</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          className="text-red-400 hover:text-red-300"
        >
          <Trash2 className="w-4 h-4 mr-1" />
          Remove Group
        </Button>
      </div>

      <div className="space-y-3">
        {group.conditions.map((condition, index) => (
          <React.Fragment key={condition.id}>
            {index > 0 && (
              <div className="flex items-center justify-center">
                <Badge variant="outline" className="text-xs">
                  {group.logical_operator}
                </Badge>
              </div>
            )}
            <ConditionEditor
              condition={condition}
              indicators={indicators}
              index={index}
              onChange={(updated) => updateCondition(index, updated)}
              onRemove={() => removeCondition(index)}
            />
          </React.Fragment>
        ))}
      </div>

      <Button
        variant="outline"
        size="sm"
        onClick={addCondition}
        className="mt-3 w-full border-dashed"
      >
        <Plus className="w-4 h-4 mr-2" />
        Add Condition
      </Button>
    </div>
  );
};

// Main Strategy Builder Component
const StrategyBuilder = () => {
  // State
  const [indicators, setIndicators] = useState({});
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [activeTab, setActiveTab] = useState('builder');

  // Strategy form state
  const [strategyForm, setStrategyForm] = useState({
    name: 'New Strategy',
    description: '',
    call_conditions: [createEmptyConditionGroup()],
    put_conditions: [createEmptyConditionGroup()],
    timeframes: ['1m'],
    assets: ['EURUSD'],
    markets: ['regular'],
    min_confidence: 75,
    max_signals_per_hour: 10,
    cooldown_seconds: 60,
    is_active: true
  });

  // Fetch indicators and strategies on mount
  useEffect(() => {
    fetchIndicators();
    fetchStrategies();
  }, []);

  const fetchIndicators = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/custom-strategies/indicators`);
      setIndicators(response.data.indicators || {});
    } catch (error) {
      console.error('Error fetching indicators:', error);
      toast.error('Failed to load indicators');
    }
  };

  const fetchStrategies = async () => {
    try {
      setIsLoading(true);
      const response = await axios.get(`${API_URL}/api/custom-strategies`);
      setStrategies(response.data.strategies || []);
    } catch (error) {
      console.error('Error fetching strategies:', error);
      toast.error('Failed to load strategies');
    } finally {
      setIsLoading(false);
    }
  };

  const saveStrategy = async () => {
    try {
      setIsSaving(true);
      
      if (selectedStrategy) {
        // Update existing strategy
        await axios.put(`${API_URL}/api/custom-strategies/${selectedStrategy.id}`, strategyForm);
        toast.success('Strategy updated successfully!');
      } else {
        // Create new strategy
        await axios.post(`${API_URL}/api/custom-strategies`, strategyForm);
        toast.success('Strategy created successfully!');
      }
      
      fetchStrategies();
      resetForm();
    } catch (error) {
      console.error('Error saving strategy:', error);
      toast.error('Failed to save strategy');
    } finally {
      setIsSaving(false);
    }
  };

  const testStrategy = async () => {
    try {
      setIsTesting(true);
      setTestResult(null);
      
      // Save first if new strategy
      let strategyId = selectedStrategy?.id;
      if (!strategyId) {
        const createResponse = await axios.post(`${API_URL}/api/custom-strategies`, strategyForm);
        strategyId = createResponse.data.strategy?.id;
        if (!strategyId) {
          throw new Error('Failed to create strategy for testing');
        }
        fetchStrategies();
      }
      
      const response = await axios.post(
        `${API_URL}/api/custom-strategies/${strategyId}/test`,
        null,
        { params: { asset: strategyForm.assets[0], timeframe: strategyForm.timeframes[0] } }
      );
      
      setTestResult(response.data);
      
      if (response.data.signal_generated) {
        toast.success(`Signal generated: ${response.data.signal?.direction}`);
      } else {
        toast.info('No signal generated with current conditions');
      }
    } catch (error) {
      console.error('Error testing strategy:', error);
      toast.error('Failed to test strategy');
    } finally {
      setIsTesting(false);
    }
  };

  const deleteStrategy = async (strategyId) => {
    if (!window.confirm('Are you sure you want to delete this strategy?')) return;
    
    try {
      await axios.delete(`${API_URL}/api/custom-strategies/${strategyId}`);
      toast.success('Strategy deleted');
      fetchStrategies();
      if (selectedStrategy?.id === strategyId) {
        resetForm();
      }
    } catch (error) {
      console.error('Error deleting strategy:', error);
      toast.error('Failed to delete strategy');
    }
  };

  const duplicateStrategy = async (strategyId) => {
    try {
      await axios.post(`${API_URL}/api/custom-strategies/${strategyId}/duplicate`, null, {
        params: { new_name: `Copy of ${strategies.find(s => s.id === strategyId)?.name || 'Strategy'}` }
      });
      toast.success('Strategy duplicated');
      fetchStrategies();
    } catch (error) {
      console.error('Error duplicating strategy:', error);
      toast.error('Failed to duplicate strategy');
    }
  };

  const loadStrategy = (strategy) => {
    setSelectedStrategy(strategy);
    setStrategyForm({
      name: strategy.name,
      description: strategy.description || '',
      call_conditions: strategy.call_conditions || [createEmptyConditionGroup()],
      put_conditions: strategy.put_conditions || [createEmptyConditionGroup()],
      timeframes: strategy.timeframes || ['1m'],
      assets: strategy.assets || ['EURUSD'],
      markets: strategy.markets || ['regular'],
      min_confidence: strategy.min_confidence || 75,
      max_signals_per_hour: strategy.max_signals_per_hour || 10,
      cooldown_seconds: strategy.cooldown_seconds || 60,
      is_active: strategy.is_active !== false
    });
    setActiveTab('builder');
  };

  const resetForm = () => {
    setSelectedStrategy(null);
    setStrategyForm({
      name: 'New Strategy',
      description: '',
      call_conditions: [createEmptyConditionGroup()],
      put_conditions: [createEmptyConditionGroup()],
      timeframes: ['1m'],
      assets: ['EURUSD'],
      markets: ['regular'],
      min_confidence: 75,
      max_signals_per_hour: 10,
      cooldown_seconds: 60,
      is_active: true
    });
    setTestResult(null);
  };

  const addConditionGroup = (direction) => {
    const key = direction === 'call' ? 'call_conditions' : 'put_conditions';
    setStrategyForm(prev => ({
      ...prev,
      [key]: [...prev[key], createEmptyConditionGroup()]
    }));
  };

  const updateConditionGroup = (direction, index, updated) => {
    const key = direction === 'call' ? 'call_conditions' : 'put_conditions';
    setStrategyForm(prev => {
      const newGroups = [...prev[key]];
      newGroups[index] = updated;
      return { ...prev, [key]: newGroups };
    });
  };

  const removeConditionGroup = (direction, index) => {
    const key = direction === 'call' ? 'call_conditions' : 'put_conditions';
    if (strategyForm[key].length > 1) {
      setStrategyForm(prev => ({
        ...prev,
        [key]: prev[key].filter((_, i) => i !== index)
      }));
    }
  };

  const toggleTimeframe = (tf) => {
    setStrategyForm(prev => {
      const current = prev.timeframes || [];
      if (current.includes(tf)) {
        return { ...prev, timeframes: current.filter(t => t !== tf) };
      } else {
        return { ...prev, timeframes: [...current, tf] };
      }
    });
  };

  const toggleAsset = (asset) => {
    setStrategyForm(prev => {
      const current = prev.assets || [];
      if (current.includes(asset)) {
        return { ...prev, assets: current.filter(a => a !== asset) };
      } else {
        return { ...prev, assets: [...current, asset] };
      }
    });
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Custom Strategy Builder</h2>
          <p className="text-slate-400">Create custom trading strategies with AND/OR condition logic</p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={resetForm}
            variant="outline"
            className="border-slate-600"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Strategy
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-slate-800/50">
          <TabsTrigger value="builder">🛠️ Builder</TabsTrigger>
          <TabsTrigger value="strategies">📋 My Strategies ({strategies.length})</TabsTrigger>
        </TabsList>

        {/* Builder Tab */}
        <TabsContent value="builder" className="space-y-6">
          {/* Strategy Name & Description */}
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Strategy Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Strategy Name</Label>
                  <Input
                    value={strategyForm.name}
                    onChange={(e) => setStrategyForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="My Custom Strategy"
                    className="bg-slate-800/50 border-slate-600"
                  />
                </div>
                <div>
                  <Label>Description</Label>
                  <Input
                    value={strategyForm.description}
                    onChange={(e) => setStrategyForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Brief description of your strategy"
                    className="bg-slate-800/50 border-slate-600"
                  />
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Switch
                    checked={strategyForm.is_active}
                    onCheckedChange={(checked) => setStrategyForm(prev => ({ ...prev, is_active: checked }))}
                  />
                  <Label>Active</Label>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* CALL Conditions */}
          <Card className="glass-dark border-green-500/30">
            <CardHeader>
              <CardTitle className="text-green-400 flex items-center gap-2">
                📈 CALL Signal Conditions
                <Badge className="bg-green-500/20 text-green-400">BUY</Badge>
              </CardTitle>
              <CardDescription>
                Define conditions that must be met to generate a CALL (buy) signal
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {strategyForm.call_conditions.map((group, index) => (
                <ConditionGroupEditor
                  key={group.id}
                  group={group}
                  indicators={indicators}
                  direction="call"
                  onChange={(updated) => updateConditionGroup('call', index, updated)}
                  onRemove={() => removeConditionGroup('call', index)}
                />
              ))}
              <Button
                variant="outline"
                onClick={() => addConditionGroup('call')}
                className="w-full border-dashed border-green-500/50 text-green-400 hover:bg-green-500/10"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Condition Group (AND with other groups)
              </Button>
            </CardContent>
          </Card>

          {/* PUT Conditions */}
          <Card className="glass-dark border-red-500/30">
            <CardHeader>
              <CardTitle className="text-red-400 flex items-center gap-2">
                📉 PUT Signal Conditions
                <Badge className="bg-red-500/20 text-red-400">SELL</Badge>
              </CardTitle>
              <CardDescription>
                Define conditions that must be met to generate a PUT (sell) signal
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {strategyForm.put_conditions.map((group, index) => (
                <ConditionGroupEditor
                  key={group.id}
                  group={group}
                  indicators={indicators}
                  direction="put"
                  onChange={(updated) => updateConditionGroup('put', index, updated)}
                  onRemove={() => removeConditionGroup('put', index)}
                />
              ))}
              <Button
                variant="outline"
                onClick={() => addConditionGroup('put')}
                className="w-full border-dashed border-red-500/50 text-red-400 hover:bg-red-500/10"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Condition Group (AND with other groups)
              </Button>
            </CardContent>
          </Card>

          {/* Trading Parameters */}
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Trading Parameters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Timeframes */}
              <div>
                <Label className="mb-2 block">Timeframes</Label>
                <div className="flex flex-wrap gap-2">
                  {timeframes.map(tf => (
                    <Button
                      key={tf.value}
                      variant={strategyForm.timeframes.includes(tf.value) ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => toggleTimeframe(tf.value)}
                      className={strategyForm.timeframes.includes(tf.value) 
                        ? 'bg-purple-500/20 text-purple-400 border-purple-500/50'
                        : 'border-slate-600'}
                    >
                      {tf.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Assets */}
              <div>
                <Label className="mb-2 block">Assets ({strategyForm.assets.length} selected)</Label>
                
                {/* Market Type Filter */}
                <div className="flex gap-2 mb-3">
                  <Badge 
                    variant="outline" 
                    className="cursor-pointer hover:bg-blue-500/20"
                    onClick={() => {
                      const regularAssets = assets.filter(a => a.market === 'regular').map(a => a.value);
                      setStrategyForm(prev => ({ ...prev, assets: regularAssets }));
                    }}
                  >
                    🔵 Select All Regular
                  </Badge>
                  <Badge 
                    variant="outline" 
                    className="cursor-pointer hover:bg-green-500/20"
                    onClick={() => {
                      const otcAssets = assets.filter(a => a.market === 'otc').map(a => a.value);
                      setStrategyForm(prev => ({ ...prev, assets: otcAssets }));
                    }}
                  >
                    🟢 Select All OTC
                  </Badge>
                  <Badge 
                    variant="outline" 
                    className="cursor-pointer hover:bg-slate-500/20"
                    onClick={() => setStrategyForm(prev => ({ ...prev, assets: [] }))}
                  >
                    Clear All
                  </Badge>
                </div>

                {/* Category Sections */}
                <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                  {/* Regular Markets */}
                  <div className="p-3 bg-blue-500/5 rounded-lg border border-blue-500/20">
                    <div className="text-sm font-medium text-blue-400 mb-2">🔵 Regular Markets</div>
                    <div className="space-y-2">
                      {['Forex Major', 'Forex Minor', 'Forex Exotic', 'Crypto', 'Crypto Alt', 'Crypto DeFi', 'Crypto Meme', 'Stocks Tech', 'Stocks Finance', 'Stocks Consumer', 'Stocks Industrial', 'Stocks Healthcare', 'Commodities', 'Indices'].map(cat => {
                        const catAssets = assets.filter(a => a.category === cat && a.market === 'regular');
                        if (catAssets.length === 0) return null;
                        return (
                          <div key={cat}>
                            <div className="text-xs text-slate-500 mb-1">{cat}</div>
                            <div className="flex flex-wrap gap-1">
                              {catAssets.map(asset => (
                                <Button
                                  key={asset.value}
                                  variant={strategyForm.assets.includes(asset.value) ? 'default' : 'outline'}
                                  size="sm"
                                  onClick={() => toggleAsset(asset.value)}
                                  className={`text-xs h-7 ${strategyForm.assets.includes(asset.value) 
                                    ? 'bg-blue-500/20 text-blue-400 border-blue-500/50'
                                    : 'border-slate-600'}`}
                                >
                                  {asset.label}
                                </Button>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* OTC Markets */}
                  <div className="p-3 bg-green-500/5 rounded-lg border border-green-500/20">
                    <div className="text-sm font-medium text-green-400 mb-2">🟢 OTC Markets (24/7 Trading)</div>
                    <div className="space-y-2">
                      {['OTC Forex', 'OTC Crypto', 'OTC Commodities', 'OTC Indices'].map(cat => {
                        const catAssets = assets.filter(a => a.category === cat);
                        if (catAssets.length === 0) return null;
                        return (
                          <div key={cat}>
                            <div className="text-xs text-slate-500 mb-1">{cat.replace('OTC ', '')}</div>
                            <div className="flex flex-wrap gap-1">
                              {catAssets.map(asset => (
                                <Button
                                  key={asset.value}
                                  variant={strategyForm.assets.includes(asset.value) ? 'default' : 'outline'}
                                  size="sm"
                                  onClick={() => toggleAsset(asset.value)}
                                  className={`text-xs h-7 ${strategyForm.assets.includes(asset.value) 
                                    ? 'bg-green-500/20 text-green-400 border-green-500/50'
                                    : 'border-slate-600'}`}
                                >
                                  {asset.label}
                                </Button>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>

              {/* Risk Parameters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label>Min Confidence ({strategyForm.min_confidence}%)</Label>
                  <Slider
                    value={[strategyForm.min_confidence]}
                    onValueChange={(v) => setStrategyForm(prev => ({ ...prev, min_confidence: v[0] }))}
                    min={50}
                    max={99}
                    step={1}
                    className="mt-2"
                  />
                </div>
                <div>
                  <Label>Max Signals/Hour</Label>
                  <Input
                    type="number"
                    value={strategyForm.max_signals_per_hour}
                    onChange={(e) => setStrategyForm(prev => ({ ...prev, max_signals_per_hour: parseInt(e.target.value) || 10 }))}
                    min={1}
                    max={100}
                    className="bg-slate-800/50 border-slate-600"
                  />
                </div>
                <div>
                  <Label>Cooldown (seconds)</Label>
                  <Input
                    type="number"
                    value={strategyForm.cooldown_seconds}
                    onChange={(e) => setStrategyForm(prev => ({ ...prev, cooldown_seconds: parseInt(e.target.value) || 60 }))}
                    min={0}
                    max={3600}
                    className="bg-slate-800/50 border-slate-600"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Test Result */}
          {testResult && (
            <Alert className={testResult.signal_generated ? 'border-green-500/50 bg-green-500/10' : 'border-yellow-500/50 bg-yellow-500/10'}>
              {testResult.signal_generated ? (
                <CheckCircle className="h-4 w-4 text-green-400" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-yellow-400" />
              )}
              <AlertTitle>{testResult.signal_generated ? 'Signal Generated!' : 'No Signal'}</AlertTitle>
              <AlertDescription>
                {testResult.message}
                {testResult.signal && (
                  <div className="mt-2 text-sm">
                    <div><strong>Direction:</strong> {testResult.signal.direction}</div>
                    <div><strong>Confidence:</strong> {testResult.signal.confidence}%</div>
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3">
            <Button
              onClick={saveStrategy}
              disabled={isSaving}
              className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
            >
              <Save className="w-4 h-4 mr-2" />
              {isSaving ? 'Saving...' : (selectedStrategy ? 'Update Strategy' : 'Save Strategy')}
            </Button>
            <Button
              onClick={testStrategy}
              disabled={isTesting}
              className="bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30"
            >
              <Play className="w-4 h-4 mr-2" />
              {isTesting ? 'Testing...' : 'Test Strategy'}
            </Button>
          </div>
        </TabsContent>

        {/* Strategies List Tab */}
        <TabsContent value="strategies">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">My Custom Strategies</CardTitle>
              <CardDescription>Manage your saved trading strategies</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="text-center py-8 text-slate-400">Loading strategies...</div>
              ) : strategies.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  No strategies yet. Create your first one in the Builder tab!
                </div>
              ) : (
                <div className="space-y-3">
                  {strategies.map(strategy => (
                    <div
                      key={strategy.id}
                      className="p-4 bg-slate-800/50 rounded-lg border border-slate-600/50 flex items-center justify-between"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-white">{strategy.name}</h4>
                          <Badge variant={strategy.is_active ? 'default' : 'secondary'}>
                            {strategy.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </div>
                        <p className="text-sm text-slate-400 mt-1">{strategy.description || 'No description'}</p>
                        <div className="flex gap-2 mt-2">
                          {strategy.timeframes?.map(tf => (
                            <Badge key={tf} variant="outline" className="text-xs">{tf}</Badge>
                          ))}
                          <Badge variant="outline" className="text-xs text-blue-400">
                            {strategy.assets?.length || 0} assets
                          </Badge>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => loadStrategy(strategy)}
                          className="border-slate-600"
                        >
                          Edit
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => duplicateStrategy(strategy.id)}
                          className="border-slate-600"
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => deleteStrategy(strategy.id)}
                          className="border-red-500/50 text-red-400 hover:bg-red-500/20"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default StrategyBuilder;
