import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MarketAssetSelector = ({ onSelectionChange }) => {
  const [assets, setAssets] = useState({
    forex: [],
    crypto: [],
    stocks: [],
    commodities: [],
    indices: []
  });
  const [selectedAssets, setSelectedAssets] = useState([]);
  const [selectedTimeframes, setSelectedTimeframes] = useState([]);
  const [showOTC, setShowOTC] = useState(true);
  const [showRegular, setShowRegular] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState({
    forex: true,
    crypto: false,
    stocks: false,
    commodities: false,
    indices: false
  });
  const [isLoading, setIsLoading] = useState(true);

  const timeframes = [
    { value: '5s', label: '5 Seconds', icon: '⚡' },
    { value: '15s', label: '15 Seconds', icon: '🔥' },
    { value: '30s', label: '30 Seconds', icon: '💨' },
    { value: '1m', label: '1 Minute', icon: '⏱️' },
    { value: '3m', label: '3 Minutes', icon: '🕐' },
    { value: '5m', label: '5 Minutes', icon: '🕔' },
    { value: '15m', label: '15 Minutes', icon: '🕒' },
    { value: '30m', label: '30 Minutes', icon: '🕞' }
  ];

  useEffect(() => {
    fetchAssets();
    fetchConfiguration();
  }, []);

  const fetchAssets = async () => {
    try {
      const response = await axios.get(`${API}/assets/all`);
      if (response.data.success) {
        setAssets(response.data.assets);
      }
    } catch (error) {
      console.error('Error fetching assets:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchConfiguration = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      setSelectedAssets(response.data.selected_assets || []);
      setSelectedTimeframes(response.data.selected_timeframes || []);
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const handleAssetToggle = (symbol, marketType) => {
    const assetKey = marketType === 'otc' ? `${symbol}_OTC` : symbol;
    const newSelected = selectedAssets.includes(assetKey)
      ? selectedAssets.filter(a => a !== assetKey)
      : [...selectedAssets, assetKey];
    
    setSelectedAssets(newSelected);
    updateConfiguration(newSelected, selectedTimeframes);
  };

  const handleTimeframeToggle = (timeframe) => {
    const newTimeframes = selectedTimeframes.includes(timeframe)
      ? selectedTimeframes.filter(t => t !== timeframe)
      : [...selectedTimeframes, timeframe];
    
    setSelectedTimeframes(newTimeframes);
    updateConfiguration(selectedAssets, newTimeframes);
  };

  const updateConfiguration = async (assets, timeframes) => {
    try {
      await axios.put(`${API}/config`, {
        selected_assets: assets,
        selected_timeframes: timeframes
      });
      
      if (onSelectionChange) {
        onSelectionChange({ assets, timeframes });
      }
    } catch (error) {
      console.error('Error updating configuration:', error);
    }
  };

  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  const selectAll = (category) => {
    const categoryAssets = assets[category] || [];
    const newAssets = [...selectedAssets];
    
    categoryAssets.forEach(asset => {
      if (showOTC && asset.market_types.includes('otc')) {
        const otcKey = `${asset.symbol}_OTC`;
        if (!newAssets.includes(otcKey)) {
          newAssets.push(otcKey);
        }
      }
      if (showRegular && asset.market_types.includes('regular')) {
        if (!newAssets.includes(asset.symbol)) {
          newAssets.push(asset.symbol);
        }
      }
    });
    
    setSelectedAssets(newAssets);
    updateConfiguration(newAssets, selectedTimeframes);
  };

  const clearAll = () => {
    setSelectedAssets([]);
    updateConfiguration([], selectedTimeframes);
  };

  const renderAssetCategory = (category, categoryAssets, icon) => {
    if (!categoryAssets || categoryAssets.length === 0) return null;

    const filteredAssets = categoryAssets.filter(asset => {
      const hasOTC = asset.market_types.includes('otc');
      const hasRegular = asset.market_types.includes('regular');
      return (showOTC && hasOTC) || (showRegular && hasRegular);
    });

    if (filteredAssets.length === 0) return null;

    return (
      <div key={category} className="border border-slate-700/50 rounded-lg overflow-hidden bg-slate-800/30">
        <button
          onClick={() => toggleCategory(category)}
          className="w-full flex items-center justify-between p-4 hover:bg-slate-700/30 transition-colors"
        >
          <div className="flex items-center space-x-3">
            <span className="text-2xl">{icon}</span>
            <div>
              <h3 className="text-lg font-semibold text-white capitalize">{category}</h3>
              <p className="text-sm text-slate-400">{filteredAssets.length} assets available</p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <Button
              onClick={(e) => {
                e.stopPropagation();
                selectAll(category);
              }}
              className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 text-xs px-2 py-1"
            >
              Select All
            </Button>
            <span className="text-slate-400">
              {expandedCategories[category] ? '▼' : '▶'}
            </span>
          </div>
        </button>

        {expandedCategories[category] && (
          <div className="p-4 pt-0 space-y-2 max-h-64 overflow-y-auto">
            {filteredAssets.map(asset => (
              <div key={asset.symbol} className="space-y-1">
                <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg hover:bg-slate-700/50 transition-colors">
                  <div className="flex-1">
                    <p className="text-white font-medium">{asset.display_name}</p>
                    <p className="text-slate-400 text-xs">{asset.description}</p>
                  </div>
                  <div className="flex items-center space-x-3">
                    {asset.market_types.includes('otc') && showOTC && (
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <Checkbox
                          checked={selectedAssets.includes(`${asset.symbol}_OTC`)}
                          onCheckedChange={() => handleAssetToggle(asset.symbol, 'otc')}
                        />
                        <span className="text-sm text-purple-400 font-medium">OTC</span>
                      </label>
                    )}
                    {asset.market_types.includes('regular') && showRegular && (
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <Checkbox
                          checked={selectedAssets.includes(asset.symbol)}
                          onCheckedChange={() => handleAssetToggle(asset.symbol, 'regular')}
                        />
                        <span className="text-sm text-blue-400 font-medium">Regular</span>
                      </label>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  if (isLoading) {
    return (
      <Card className="p-6 glass-dark border-slate-700/50">
        <div className="text-center text-slate-400 py-8">
          <div className="text-4xl mb-2">⏳</div>
          <p>Loading assets...</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Timeframe Selection */}
      <Card className="p-6 glass-dark border-emerald-500/20">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-xl font-semibold text-white">⏱️ Trading Timeframes</h3>
            <p className="text-slate-400 text-sm mt-1">Select timeframes for signal generation</p>
          </div>
          <div className="text-emerald-400 font-medium">
            {selectedTimeframes.length} selected
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
          {timeframes.map(tf => (
            <button
              key={tf.value}
              onClick={() => handleTimeframeToggle(tf.value)}
              className={`flex flex-col items-center justify-center p-4 rounded-lg border-2 transition-all ${
                selectedTimeframes.includes(tf.value)
                  ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400'
                  : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:border-slate-600'
              }`}
            >
              <span className="text-2xl mb-1">{tf.icon}</span>
              <span className="text-xs font-medium">{tf.label}</span>
            </button>
          ))}
        </div>
      </Card>

      {/* Asset Selection */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-semibold text-white">📊 Market Assets</h3>
            <p className="text-slate-400 text-sm mt-1">
              Select assets for signal generation • {selectedAssets.length} assets selected
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <Button
              onClick={clearAll}
              className="bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
            >
              Clear All
            </Button>
          </div>
        </div>

        {/* Market Type Filters */}
        <div className="flex items-center space-x-4 mb-6 p-4 bg-slate-800/50 rounded-lg">
          <span className="text-slate-400 font-medium">Show:</span>
          <label className="flex items-center space-x-2 cursor-pointer">
            <Checkbox
              checked={showOTC}
              onCheckedChange={setShowOTC}
            />
            <span className="text-white">OTC Markets (24/7)</span>
          </label>
          <label className="flex items-center space-x-2 cursor-pointer">
            <Checkbox
              checked={showRegular}
              onCheckedChange={setShowRegular}
            />
            <span className="text-white">Regular Markets</span>
          </label>
        </div>

        {/* Asset Categories */}
        <div className="space-y-4">
          {renderAssetCategory('forex', assets.forex, '💱')}
          {renderAssetCategory('crypto', assets.crypto, '₿')}
          {renderAssetCategory('stocks', assets.stocks, '📈')}
          {renderAssetCategory('commodities', assets.commodities, '🥇')}
          {renderAssetCategory('indices', assets.indices, '📊')}
        </div>
      </Card>
    </div>
  );
};

export default MarketAssetSelector;
