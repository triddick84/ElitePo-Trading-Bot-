import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { Separator } from './ui/separator';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const AdaptiveStrategyConfig = () => {
  const [config, setConfig] = useState(null);
  const [availableIndicators, setAvailableIndicators] = useState([]);
  const [indicatorDetails, setIndicatorDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadConfig();
    loadAvailableIndicators();
  }, []);

  const loadConfig = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/adaptive-strategy/config`);
      if (response.data.success) {
        setConfig(response.data.config);
      }
    } catch (error) {
      console.error('Error loading adaptive strategy config:', error);
      toast.error('Failed to load adaptive strategy configuration');
    } finally {
      setLoading(false);
    }
  };

  const loadAvailableIndicators = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/adaptive-strategy/available-indicators`);
      if (response.data.success) {
        setAvailableIndicators(response.data.indicators);
        setIndicatorDetails(response.data.indicator_details);
      }
    } catch (error) {
      console.error('Error loading available indicators:', error);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      const response = await axios.put(`${BACKEND_URL}/api/adaptive-strategy/config`, config);
      if (response.data.success) {
        toast.success('✅ Adaptive strategy configuration saved!');
        setConfig(response.data.config);
      }
    } catch (error) {
      console.error('Error saving config:', error);
      toast.error('❌ Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const resetConfig = async () => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/adaptive-strategy/reset`);
      if (response.data.success) {
        toast.success('✅ Configuration reset to defaults');
        setConfig(response.data.config);
      }
    } catch (error) {
      console.error('Error resetting config:', error);
      toast.error('❌ Failed to reset configuration');
    }
  };

  const toggleIndicator = (marketType, indicator) => {
    setConfig(prev => {
      const indicators = prev[`${marketType}_indicators`];
      const newIndicators = indicators.includes(indicator)
        ? indicators.filter(i => i !== indicator)
        : [...indicators, indicator];
      return {
        ...prev,
        [`${marketType}_indicators`]: newIndicators
      };
    });
  };

  if (loading || !config) {
    return (
      <Card className="w-full bg-slate-900 border-slate-700">
        <CardContent className="p-6">
          <div className="text-center text-slate-400">Loading configuration...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Enable/Disable Adaptive System */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-2xl text-emerald-400">🎯 Adaptive Market Condition System</CardTitle>
              <CardDescription className="text-slate-400 mt-2">
                Automatically detect market conditions and apply optimized strategies
              </CardDescription>
            </div>
            <Switch
              checked={config.enabled}
              onCheckedChange={(checked) => setConfig({ ...config, enabled: checked })}
              className="data-[state=checked]:bg-emerald-500"
            />
          </div>
        </CardHeader>
      </Card>

      {config.enabled && (
        <>
          {/* ADX Thresholds */}
          <Card className="bg-slate-900 border-slate-700">
            <CardHeader>
              <CardTitle className="text-xl text-white">📊 Market Detection Thresholds</CardTitle>
              <CardDescription className="text-slate-400">
                Configure ADX thresholds for market condition detection
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-sm font-medium text-slate-300">
                    Trending Market Threshold (ADX)
                  </label>
                  <Badge variant="outline" className="bg-blue-500/20 text-blue-400 border-blue-500">
                    &gt; {config.adx_trending_threshold}
                  </Badge>
                </div>
                <Slider
                  value={[config.adx_trending_threshold]}
                  onValueChange={(value) => setConfig({ ...config, adx_trending_threshold: value[0] })}
                  min={15}
                  max={50}
                  step={0.5}
                  className="w-full"
                />
                <p className="text-xs text-slate-500 mt-1">
                  When ADX is above this value, market is considered trending
                </p>
              </div>

              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-sm font-medium text-slate-300">
                    Ranging Market Threshold (ADX)
                  </label>
                  <Badge variant="outline" className="bg-orange-500/20 text-orange-400 border-orange-500">
                    &lt; {config.adx_ranging_threshold}
                  </Badge>
                </div>
                <Slider
                  value={[config.adx_ranging_threshold]}
                  onValueChange={(value) => setConfig({ ...config, adx_ranging_threshold: value[0] })}
                  min={10}
                  max={30}
                  step={0.5}
                  className="w-full"
                />
                <p className="text-xs text-slate-500 mt-1">
                  When ADX is below this value, market is considered ranging/volatile
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Trending Market Indicators */}
          <Card className="bg-slate-900 border-slate-700">
            <CardHeader>
              <CardTitle className="text-xl text-white">📈 Trending Market Indicators</CardTitle>
              <CardDescription className="text-slate-400">
                Select indicators to use when market is trending
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {availableIndicators.map(indicator => {
                  const details = indicatorDetails[indicator];
                  const isSelected = config.trending_indicators.includes(indicator);
                  const isBestFor = details?.best_for === 'trending' || details?.best_for === 'both';
                  
                  return (
                    <div
                      key={indicator}
                      onClick={() => toggleIndicator('trending', indicator)}
                      className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                        isSelected
                          ? 'border-blue-500 bg-blue-500/10'
                          : 'border-slate-700 bg-slate-800 hover:border-slate-600'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white">{details?.name || indicator}</span>
                            {isBestFor && (
                              <Badge className="bg-blue-500/20 text-blue-400 border-blue-500 text-xs">
                                Recommended
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-slate-400 mt-1">{details?.description}</p>
                        </div>
                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                          isSelected ? 'bg-blue-500 border-blue-500' : 'border-slate-600'
                        }`}>
                          {isSelected && <span className="text-white text-xs">✓</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              
              <Separator className="my-4 bg-slate-700" />
              
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-sm font-medium text-slate-300">
                      Execution Delay (seconds)
                    </label>
                    <Badge variant="outline" className="bg-slate-700 text-white">
                      {config.trending_execution_delay}s
                    </Badge>
                  </div>
                  <Slider
                    value={[config.trending_execution_delay]}
                    onValueChange={(value) => setConfig({ ...config, trending_execution_delay: value[0] })}
                    min={0.5}
                    max={10}
                    step={0.5}
                    className="w-full"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Longer delay helps avoid whipsaws in trending markets
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Ranging Market Indicators */}
          <Card className="bg-slate-900 border-slate-700">
            <CardHeader>
              <CardTitle className="text-xl text-white">📉 Ranging/Volatile Market Indicators</CardTitle>
              <CardDescription className="text-slate-400">
                Select indicators to use when market is ranging or volatile
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {availableIndicators.map(indicator => {
                  const details = indicatorDetails[indicator];
                  const isSelected = config.ranging_indicators.includes(indicator);
                  const isBestFor = details?.best_for === 'ranging' || details?.best_for === 'both';
                  
                  return (
                    <div
                      key={indicator}
                      onClick={() => toggleIndicator('ranging', indicator)}
                      className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                        isSelected
                          ? 'border-orange-500 bg-orange-500/10'
                          : 'border-slate-700 bg-slate-800 hover:border-slate-600'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white">{details?.name || indicator}</span>
                            {isBestFor && (
                              <Badge className="bg-orange-500/20 text-orange-400 border-orange-500 text-xs">
                                Recommended
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-slate-400 mt-1">{details?.description}</p>
                        </div>
                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                          isSelected ? 'bg-orange-500 border-orange-500' : 'border-slate-600'
                        }`}>
                          {isSelected && <span className="text-white text-xs">✓</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              
              <Separator className="my-4 bg-slate-700" />
              
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-sm font-medium text-slate-300">
                      Execution Delay (seconds)
                    </label>
                    <Badge variant="outline" className="bg-slate-700 text-white">
                      {config.ranging_execution_delay}s
                    </Badge>
                  </div>
                  <Slider
                    value={[config.ranging_execution_delay]}
                    onValueChange={(value) => setConfig({ ...config, ranging_execution_delay: value[0] })}
                    min={0.5}
                    max={10}
                    step={0.5}
                    className="w-full"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Shorter delay for quick mean-reversion entries
                  </p>
                </div>

                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-sm font-medium text-slate-300">
                      Signal Threshold (%)
                    </label>
                    <Badge variant="outline" className="bg-slate-700 text-white">
                      {config.ranging_signal_threshold}%
                    </Badge>
                  </div>
                  <Slider
                    value={[config.ranging_signal_threshold]}
                    onValueChange={(value) => setConfig({ ...config, ranging_signal_threshold: value[0] })}
                    min={70}
                    max={95}
                    step={1}
                    className="w-full"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Higher threshold filters noise in volatile markets
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <div className="flex gap-4">
            <Button
              onClick={saveConfig}
              disabled={saving}
              className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {saving ? '⏳ Saving...' : '💾 Save Configuration'}
            </Button>
            <Button
              onClick={resetConfig}
              variant="outline"
              className="border-slate-600 text-slate-300 hover:bg-slate-800"
            >
              🔄 Reset to Defaults
            </Button>
          </div>
        </>
      )}
    </div>
  );
};

export default AdaptiveStrategyConfig;
