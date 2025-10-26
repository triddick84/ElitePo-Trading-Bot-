import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Label } from './ui/label';
import { Button } from './ui/button';

const ChartConfiguration = ({ onConfigChange }) => {
  const [chartConfig, setChartConfig] = useState({
    chartType: 'japanese_candles',
    chartTimeframe: '15s',
    signalTimeframe: '5s'
  });

  // Chart types available on Pocket Option
  const chartTypes = [
    { id: 'line', name: 'Line', icon: '📈', description: 'Simple line chart' },
    { id: 'bar', name: 'Bar', icon: '📊', description: 'OHLC bar chart' },
    { id: 'japanese_candles', name: 'Japanese Candles', icon: '🕯️', description: 'Traditional candlesticks' },
    { id: 'heikin_ashi', name: 'Heikin Ashi', icon: '🎌', description: 'Smoothed candles' }
  ];

  // Available timeframes
  const timeframes = [
    { id: '5s', name: '5 Seconds', category: 'ultra_short' },
    { id: '15s', name: '15 Seconds', category: 'ultra_short' },
    { id: '30s', name: '30 Seconds', category: 'short' },
    { id: '1m', name: '1 Minute', category: 'short' },
    { id: '3m', name: '3 Minutes', category: 'medium' },
    { id: '5m', name: '5 Minutes', category: 'medium' },
    { id: '15m', name: '15 Minutes', category: 'long' },
    { id: '30m', name: '30 Minutes', category: 'long' }
  ];

  // Notify parent component of changes
  useEffect(() => {
    if (onConfigChange) {
      onConfigChange(chartConfig);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartConfig.chartType, chartConfig.chartTimeframe, chartConfig.signalTimeframe]);

  const handleChartTypeChange = (typeId) => {
    setChartConfig(prev => ({ ...prev, chartType: typeId }));
  };

  const handleTimeframeChange = (field, value) => {
    setChartConfig(prev => ({ ...prev, [field]: value }));
  };

  return (
    <Card className="p-6 glass-dark border-slate-700/50 mb-6">
      <h3 className="text-xl font-semibold text-white mb-6 flex items-center space-x-2">
        <span>📊</span>
        <span>Chart Configuration</span>
        <span className="text-xs text-slate-400 font-normal ml-2">(Pocket Option Sync)</span>
      </h3>

      {/* Chart Type Selection */}
      <div className="mb-6">
        <Label className="text-slate-300 font-medium mb-3 block">
          Chart Type
        </Label>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {chartTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => handleChartTypeChange(type.id)}
              className={`p-4 rounded-xl border-2 transition-all duration-200 text-center ${
                chartConfig.chartType === type.id
                  ? 'border-emerald-500/50 bg-emerald-500/10'
                  : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
              }`}
            >
              <div className="text-3xl mb-2">{type.icon}</div>
              <div className="text-white font-medium text-sm">{type.name}</div>
              <div className="text-slate-400 text-xs mt-1">{type.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Timeframe Configuration */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Chart Timeframe (for analysis) */}
        <div>
          <Label className="text-slate-300 font-medium mb-3 block">
            📈 Chart Timeframe
            <span className="text-xs text-slate-500 ml-2">(Analysis period)</span>
          </Label>
          <div className="grid grid-cols-2 gap-2">
            {timeframes.map((tf) => (
              <button
                key={`chart-${tf.id}`}
                onClick={() => handleTimeframeChange('chartTimeframe', tf.id)}
                className={`p-3 rounded-lg border transition-all duration-200 text-sm ${
                  chartConfig.chartTimeframe === tf.id
                    ? 'border-blue-500 bg-blue-500/20 text-blue-300 font-semibold'
                    : 'border-slate-600/50 bg-slate-800/30 text-slate-400 hover:border-slate-500/50'
                }`}
              >
                {tf.name}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-2">
            💡 Timeframe used for chart analysis and indicator calculation
          </p>
        </div>

        {/* Signal/Trade Timeframe (for execution) */}
        <div>
          <Label className="text-slate-300 font-medium mb-3 block">
            ⚡ Signal Timeframe
            <span className="text-xs text-slate-500 ml-2">(Trade expiration)</span>
          </Label>
          <div className="grid grid-cols-2 gap-2">
            {timeframes.map((tf) => (
              <button
                key={`signal-${tf.id}`}
                onClick={() => handleTimeframeChange('signalTimeframe', tf.id)}
                className={`p-3 rounded-lg border transition-all duration-200 text-sm ${
                  chartConfig.signalTimeframe === tf.id
                    ? 'border-emerald-500 bg-emerald-500/20 text-emerald-300 font-semibold'
                    : 'border-slate-600/50 bg-slate-800/30 text-slate-400 hover:border-slate-500/50'
                }`}
              >
                {tf.name}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-2">
            💡 Timeframe for signal generation and trade expiration
          </p>
        </div>
      </div>

      {/* Configuration Summary */}
      <div className="mt-6 p-4 rounded-lg bg-slate-800/50 border border-slate-700/50">
        <h4 className="text-white font-semibold mb-2 flex items-center space-x-2">
          <span>📋</span>
          <span>Current Configuration</span>
        </h4>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Chart Type:</span>
            <span className="text-white font-medium">
              {chartTypes.find(t => t.id === chartConfig.chartType)?.name}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Chart Timeframe:</span>
            <span className="text-blue-300 font-medium">{chartConfig.chartTimeframe}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Signal Timeframe:</span>
            <span className="text-emerald-300 font-medium">{chartConfig.signalTimeframe}</span>
          </div>
        </div>
        
        {/* Example Description */}
        <div className="mt-3 p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
          <p className="text-purple-200 text-xs">
            <strong>Example:</strong> Analyze {chartConfig.chartTimeframe} {chartTypes.find(t => t.id === chartConfig.chartType)?.name.toLowerCase()} 
            {' '}to generate {chartConfig.signalTimeframe} binary options signals
          </p>
          <p className="text-purple-300 text-xs mt-1">
            📊 Analysis: {chartConfig.chartTimeframe} chart → ⚡ Signal: {chartConfig.signalTimeframe} trade
          </p>
        </div>
      </div>

      {/* Important Note */}
      <div className="mt-4 p-3 rounded-lg bg-orange-500/10 border border-orange-500/30">
        <div className="flex items-start space-x-2">
          <span className="text-orange-400 text-lg">⚠️</span>
          <div className="flex-1">
            <p className="text-orange-300 text-xs font-semibold">Important:</p>
            <p className="text-orange-200 text-xs mt-1">
              Chart timeframe should typically be LONGER than signal timeframe for better analysis
              (e.g., 15s chart for 5s signals, 5m chart for 1m signals)
            </p>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default ChartConfiguration;
