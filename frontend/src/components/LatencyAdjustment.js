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

  useEffect(() => {
    fetchLatencySettings();
  }, []);

  const fetchLatencySettings = async () => {
    try {
      const response = await axios.get(`${API}/latency/settings`);
      setLatencyOffset(response.data.latency_offset || 0);
      setLastUpdate(response.data.updated_at);
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
      toast.success(`✅ Latency offset updated to ${newOffset >= 0 ? '+' : ''}${newOffset.toFixed(1)}s`);
    } catch (error) {
      console.error('Error updating latency offset:', error);
      toast.error('❌ Failed to update latency offset');
    } finally {
      setIsLatencySaving(false);
    }
  };

  const getOffsetColor = () => {
    if (latencyOffset === 0) return 'text-emerald-400';
    if (latencyOffset < 0) return 'text-blue-400';
    return 'text-orange-400';
  };

  const getOffsetBg = () => {
    if (latencyOffset === 0) return 'bg-emerald-900/30 border-emerald-500/30';
    if (latencyOffset < 0) return 'bg-blue-900/30 border-blue-500/30';
    return 'bg-orange-900/30 border-orange-500/30';
  };

  if (compact) {
    return (
      <Card className={`p-4 glass-dark ${getOffsetBg()} border transition-all duration-300`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">⚡</span>
            <div>
              <h4 className="text-sm font-semibold text-white">Signal Timing</h4>
              <p className="text-xs text-slate-400">Fine-tune entry precision</p>
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
          min={-10}
          max={10}
          step={0.1}
          className="w-full mb-2"
          disabled={isLatencySaving}
        />
        
        <div className="flex justify-between text-xs text-slate-500">
          <span>Earlier</span>
          <span>Auto</span>
          <span>Later</span>
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
          <p className="text-slate-400 text-sm">Adjust when signals arrive for optimal entry execution</p>
        </div>
        <div className="text-4xl">🎛️</div>
      </div>
      
      <div className={`rounded-xl p-6 border transition-all duration-300 ${getOffsetBg()}`}>
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <label className="text-white font-medium">Timing Offset</label>
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
            min={-10}
            max={10}
            step={0.1}
            className="w-full"
            disabled={isLatencySaving}
          />
          
          <div className="flex justify-between mt-2 text-xs text-slate-400">
            <span>-10s (Signals Earlier)</span>
            <span>0s (Auto)</span>
            <span>+10s (Signals Later)</span>
          </div>
        </div>
        
        <div className="space-y-3">
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center text-blue-400 text-lg">
              ⏪
            </div>
            <div className="flex-1">
              <p className="text-blue-200 text-sm">
                <span className="font-semibold">Negative (-)</span>: Signals arrive earlier. 
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
                <span className="font-semibold">Positive (+)</span>: Signals arrive later. 
                Use if signals are arriving too early for your platform/network speed.
              </p>
            </div>
          </div>
        </div>
        
        <div className="mt-4 pt-4 border-t border-slate-600/30">
          <div className="flex items-start space-x-2 text-sm text-slate-300">
            <span className="text-lg">💡</span>
            <div>
              <p className="font-semibold mb-1">Pro Tip:</p>
              <p className="text-slate-400">
                Start at 0s and adjust based on your results. If trades execute late, use negative values. 
                If arriving too early, use positive values. Applies to both Force Generate and Auto Generate signals.
              </p>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default LatencyAdjustment;
