import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Slider } from './ui/slider';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const LatencyAdjustment = ({ compact = false }) => {
  const [latencyOffset, setLatencyOffset] = useState(0);
  const [isLatencySaving, setIsLatencySaving] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [presetMode, setPresetMode] = useState('custom');

  // Extended range: -30s to +30s
  const MIN_OFFSET = -30;
  const MAX_OFFSET = 30;
  const STEP = 0.5;

  // Preset configurations for common use cases
  const presets = {
    fast: { offset: -5, label: '⚡ Fast Entry', desc: 'For low-latency connections' },
    normal: { offset: 0, label: '🎯 Normal', desc: 'Default timing' },
    delayed: { offset: 5, label: '⏳ Delayed', desc: 'For slower connections' },
    conservative: { offset: 10, label: '🛡️ Conservative', desc: 'Extra confirmation time' },
    aggressive: { offset: -10, label: '🚀 Aggressive', desc: 'Early entry signals' },
    custom: { offset: latencyOffset, label: '🎛️ Custom', desc: 'Manual adjustment' }
  };

  useEffect(() => {
    fetchLatencySettings();
  }, []);

  const fetchLatencySettings = async () => {
    try {
      const response = await axios.get(`${API}/latency/settings`);
      const offset = response.data.latency_offset || 0;
      setLatencyOffset(offset);
      setLastUpdate(response.data.updated_at);
      
      // Determine preset mode
      if (offset === 0) setPresetMode('normal');
      else if (offset === -5) setPresetMode('fast');
      else if (offset === 5) setPresetMode('delayed');
      else if (offset === 10) setPresetMode('conservative');
      else if (offset === -10) setPresetMode('aggressive');
      else setPresetMode('custom');
    } catch (error) {
      console.error('Error fetching latency settings:', error);
    }
  };

  const updateLatencyOffset = async (newOffset) => {
    setIsLatencySaving(true);
    try {
      await axios.put(`${API}/latency/settings?latency_offset=${newOffset}`);
      setLatencyOffset(newOffset);
      setLastUpdate(new Date().toISOString());
      
      // Update preset mode
      if (newOffset === 0) setPresetMode('normal');
      else if (newOffset === -5) setPresetMode('fast');
      else if (newOffset === 5) setPresetMode('delayed');
      else if (newOffset === 10) setPresetMode('conservative');
      else if (newOffset === -10) setPresetMode('aggressive');
      else setPresetMode('custom');
      
      toast.success(`✅ Latency offset updated to ${newOffset >= 0 ? '+' : ''}${newOffset.toFixed(1)}s`);
    } catch (error) {
      console.error('Error updating latency offset:', error);
      toast.error('❌ Failed to update latency offset');
    } finally {
      setIsLatencySaving(false);
    }
  };

  const applyPreset = (presetKey) => {
    const preset = presets[presetKey];
    if (preset && presetKey !== 'custom') {
      updateLatencyOffset(preset.offset);
    }
    setPresetMode(presetKey);
  };

  const getOffsetColor = () => {
    if (latencyOffset === 0) return 'text-emerald-400';
    if (latencyOffset < -15) return 'text-red-400';
    if (latencyOffset < 0) return 'text-blue-400';
    if (latencyOffset > 15) return 'text-yellow-400';
    return 'text-orange-400';
  };

  const getOffsetBg = () => {
    if (latencyOffset === 0) return 'bg-emerald-900/30 border-emerald-500/30';
    if (latencyOffset < -15) return 'bg-red-900/30 border-red-500/30';
    if (latencyOffset < 0) return 'bg-blue-900/30 border-blue-500/30';
    if (latencyOffset > 15) return 'bg-yellow-900/30 border-yellow-500/30';
    return 'bg-orange-900/30 border-orange-500/30';
  };

  const getOffsetDescription = () => {
    if (latencyOffset === 0) return 'Synchronized with platform';
    if (latencyOffset <= -20) return 'Very early signals (aggressive)';
    if (latencyOffset <= -10) return 'Early signals';
    if (latencyOffset < 0) return 'Slightly early signals';
    if (latencyOffset >= 20) return 'Very late signals (conservative)';
    if (latencyOffset >= 10) return 'Late signals';
    return 'Slightly late signals';
  };

  if (compact) {
    return (
      <Card className={`p-4 glass-dark ${getOffsetBg()} border transition-all duration-300`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">⚡</span>
            <div>
              <h4 className="text-sm font-semibold text-white">Signal Timing</h4>
              <p className="text-xs text-slate-400">Range: {MIN_OFFSET}s to +{MAX_OFFSET}s</p>
            </div>
          </div>
          <div className="text-right">
            <div className={`text-2xl font-bold ${getOffsetColor()}`}>
              {latencyOffset >= 0 ? '+' : ''}{latencyOffset.toFixed(1)}s
            </div>
            {isLatencySaving && <span className="text-emerald-400 text-xs">Saving...</span>}
          </div>
        </div>
        
        <Slider
          value={[latencyOffset]}
          onValueChange={(values) => updateLatencyOffset(values[0])}
          min={MIN_OFFSET}
          max={MAX_OFFSET}
          step={STEP}
          className="w-full mb-2"
          disabled={isLatencySaving}
        />
        
        <div className="flex justify-between text-xs text-slate-500">
          <span>{MIN_OFFSET}s Earlier</span>
          <span>Auto</span>
          <span>+{MAX_OFFSET}s Later</span>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 glass-dark border-emerald-700/50">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-xl font-semibold text-white mb-2 flex items-center">
            <span className="mr-2">⚡</span>
            Signal Timing Control
          </h3>
          <p className="text-slate-400 text-sm">Extended range: {MIN_OFFSET}s to +{MAX_OFFSET}s for precise entry timing</p>
        </div>
        <div className="text-4xl">🎛️</div>
      </div>

      {/* Preset Buttons */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        {Object.entries(presets).filter(([key]) => key !== 'custom').map(([key, preset]) => (
          <button
            key={key}
            onClick={() => applyPreset(key)}
            className={`p-2 rounded-lg text-xs font-medium transition-all ${
              presetMode === key
                ? 'bg-emerald-600 text-white border-emerald-400'
                : 'bg-slate-700/50 text-slate-300 hover:bg-slate-600/50 border-slate-600'
            } border`}
          >
            {preset.label}
          </button>
        ))}
      </div>
      
      <div className={`rounded-xl p-6 border transition-all duration-300 ${getOffsetBg()}`}>
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <label className="text-white font-medium">Timing Offset</label>
              <p className="text-xs text-slate-400 mt-1">{getOffsetDescription()}</p>
            </div>
            <div className="flex items-center space-x-3">
              <span className={`text-3xl font-bold ${getOffsetColor()}`}>
                {latencyOffset >= 0 ? '+' : ''}{latencyOffset.toFixed(1)}s
              </span>
              {isLatencySaving && <span className="text-emerald-400 text-sm animate-pulse">Saving...</span>}
            </div>
          </div>
          
          <Slider
            value={[latencyOffset]}
            onValueChange={(values) => updateLatencyOffset(values[0])}
            min={MIN_OFFSET}
            max={MAX_OFFSET}
            step={STEP}
            className="w-full"
            disabled={isLatencySaving}
          />
          
          <div className="flex justify-between mt-2 text-xs text-slate-400">
            <span>{MIN_OFFSET}s (Signals Earlier)</span>
            <span>0s (Auto)</span>
            <span>+{MAX_OFFSET}s (Signals Later)</span>
          </div>

          {/* Quick adjustment buttons */}
          <div className="flex justify-center gap-2 mt-4">
            <button
              onClick={() => updateLatencyOffset(Math.max(MIN_OFFSET, latencyOffset - 5))}
              className="px-3 py-1 bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 rounded text-sm"
              disabled={isLatencySaving}
            >
              -5s
            </button>
            <button
              onClick={() => updateLatencyOffset(Math.max(MIN_OFFSET, latencyOffset - 1))}
              className="px-3 py-1 bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 rounded text-sm"
              disabled={isLatencySaving}
            >
              -1s
            </button>
            <button
              onClick={() => updateLatencyOffset(0)}
              className="px-3 py-1 bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 rounded text-sm"
              disabled={isLatencySaving}
            >
              Reset
            </button>
            <button
              onClick={() => updateLatencyOffset(Math.min(MAX_OFFSET, latencyOffset + 1))}
              className="px-3 py-1 bg-orange-600/30 hover:bg-orange-600/50 text-orange-300 rounded text-sm"
              disabled={isLatencySaving}
            >
              +1s
            </button>
            <button
              onClick={() => updateLatencyOffset(Math.min(MAX_OFFSET, latencyOffset + 5))}
              className="px-3 py-1 bg-orange-600/30 hover:bg-orange-600/50 text-orange-300 rounded text-sm"
              disabled={isLatencySaving}
            >
              +5s
            </button>
          </div>
        </div>
        
        <div className="space-y-3">
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 bg-red-500/20 rounded-lg flex items-center justify-center text-red-400 text-lg">
              🚀
            </div>
            <div className="flex-1">
              <p className="text-red-200 text-sm">
                <span className="font-semibold">Very Early ({MIN_OFFSET}s to -15s)</span>: Aggressive early entry. 
                Use for scalping or when you need maximum preparation time.
              </p>
            </div>
          </div>

          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center text-blue-400 text-lg">
              ⏪
            </div>
            <div className="flex-1">
              <p className="text-blue-200 text-sm">
                <span className="font-semibold">Early (-15s to -1s)</span>: Signals arrive earlier. 
                Use for fast connections or when you need more preparation time.
              </p>
            </div>
          </div>
          
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 bg-emerald-500/20 rounded-lg flex items-center justify-center text-emerald-400 text-lg">
              ⚡
            </div>
            <div className="flex-1">
              <p className="text-emerald-200 text-sm">
                <span className="font-semibold">Zero (0)</span>: Automatic timing. 
                Signals synchronized with Pocket Option candles (10s countdown to entry).
              </p>
            </div>
          </div>
          
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 bg-orange-500/20 rounded-lg flex items-center justify-center text-orange-400 text-lg">
              ⏩
            </div>
            <div className="flex-1">
              <p className="text-orange-200 text-sm">
                <span className="font-semibold">Late (+1s to +15s)</span>: Signals arrive later. 
                Use if signals are arriving too early for your platform/network speed.
              </p>
            </div>
          </div>

          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 bg-yellow-500/20 rounded-lg flex items-center justify-center text-yellow-400 text-lg">
              🛡️
            </div>
            <div className="flex-1">
              <p className="text-yellow-200 text-sm">
                <span className="font-semibold">Very Late (+15s to +{MAX_OFFSET}s)</span>: Conservative timing. 
                Extra confirmation time for high-stakes trades.
              </p>
            </div>
          </div>
        </div>
        
        <div className="mt-4 pt-4 border-t border-slate-600/30">
          <div className="flex items-start space-x-2 text-sm text-slate-300">
            <span className="text-lg">💡</span>
            <div>
              <p className="font-semibold mb-1">Pro Tips:</p>
              <ul className="text-slate-400 space-y-1 text-xs">
                <li>• For 5-second trades, use -5s to -10s for early preparation</li>
                <li>• For 1-minute trades, 0s to +5s is usually optimal</li>
                <li>• If trades execute late consistently, use negative values</li>
                <li>• Use presets for quick common configurations</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default LatencyAdjustment;
