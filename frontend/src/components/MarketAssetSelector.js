import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MarketAssetSelector = ({ onSelectionChange, hideExpirations = false, selectedAssets: externalSelectedAssets, maxSelection, config, setConfig }) => {
  const [assets, setAssets] = useState({
    forex: [],
    crypto: [],
    stocks: [],
    commodities: [],
    indices: []
  });
  
  // Ensure we always have an array for selectedAssets
  const getInitialAssets = () => {
    if (Array.isArray(config?.selected_assets)) return config.selected_assets;
    if (Array.isArray(externalSelectedAssets)) return externalSelectedAssets;
    return [];
  };
  
  // Use config.selected_assets if passed, otherwise use externalSelectedAssets or local state
  const [selectedAssets, setSelectedAssets] = useState(getInitialAssets);
  const [selectedExpirations, setSelectedExpirations] = useState(
    Array.isArray(config?.selected_expirations) ? config.selected_expirations : []
  );
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
  
  // Sync with external config/selectedAssets if provided
  useEffect(() => {
    if (config?.selected_assets !== undefined && Array.isArray(config.selected_assets)) {
      setSelectedAssets(config.selected_assets);
    } else if (externalSelectedAssets !== undefined && Array.isArray(externalSelectedAssets)) {
      setSelectedAssets(externalSelectedAssets);
    }
    if (config?.selected_expirations !== undefined && Array.isArray(config.selected_expirations)) {
      setSelectedExpirations(config.selected_expirations);
    }
  }, [config?.selected_assets, config?.selected_expirations, externalSelectedAssets]);

  const expirations = [
    { value: '5s', label: '5 Seconds', icon: '⚡' },
    { value: '15s', label: '15 Seconds', icon: '🔥' },
    { value: '30s', label: '30 Seconds', icon: '💨' },
    { value: '1m', label: '1 Minute', icon: '⏱️' },
    { value: '2m', label: '2 Minutes', icon: '🕐' },
    { value: '3m', label: '3 Minutes', icon: '🕐' },
    { value: '5m', label: '5 Minutes', icon: '🕔' }
  ];

  useEffect(() => {
    fetchAssets();
    // Only fetch configuration from server if config prop isn't provided
    if (!config) {
      fetchConfiguration();
    }
  }, [config]);

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
      // Only update local state if config prop isn't controlling it
      if (!config) {
        setSelectedAssets(response.data.selected_assets || []);
        setSelectedExpirations(response.data.selected_expirations || []);
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const handleAssetToggle = (symbol, marketType) => {
    const assetKey = marketType === 'otc' ? `${symbol}_OTC` : symbol;
    const currentAssets = Array.isArray(selectedAssets) ? selectedAssets : [];
    const newSelected = currentAssets.includes(assetKey)
      ? currentAssets.filter(a => a !== assetKey)
      : [...currentAssets, assetKey];
    
    setSelectedAssets(newSelected);
    updateConfiguration(newSelected, selectedExpirations);
  };

  const handleTimeframeToggle = (timeframe) => {
    const currentExpirations = Array.isArray(selectedExpirations) ? selectedExpirations : [];
    const newExpirations = currentExpirations.includes(timeframe)
      ? currentExpirations.filter(t => t !== timeframe)
      : [...currentExpirations, timeframe];
    
    setSelectedExpirations(newExpirations);
    updateConfiguration(selectedAssets, newExpirations);
  };

  const updateConfiguration = async (assets, expirations) => {
    try {
      // If hideExpirations is true, only update assets - don't touch expirations
      const updateData = hideExpirations
        ? { selected_assets: assets }
        : { selected_assets: assets, selected_expirations: expirations };
      
      await axios.put(`${API}/config`, updateData);
      
      // Update parent config if setConfig is provided
      if (setConfig) {
        setConfig(prev => ({
          ...prev,
          selected_assets: assets,
          ...(hideExpirations ? {} : { selected_expirations: expirations })
        }));
      }
      
      if (onSelectionChange) {
        onSelectionChange({ assets, expirations });
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
    const currentAssets = Array.isArray(selectedAssets) ? selectedAssets : [];
    const newAssets = [...currentAssets];
    
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
    updateConfiguration(newAssets, selectedExpirations);
  };

  const clearAll = () => {
    setSelectedAssets([]);
    updateConfiguration([], selectedExpirations);
  };

  const renderAssetCategory = (category, categoryAssets, icon) => {
    if (!categoryAssets || categoryAssets.length === 0) return null;

    const filteredAssets = categoryAssets.filter(asset => {
      const hasOTC = asset.market_types.includes('otc');
      const hasRegular = asset.market_types.includes('regular');
      return (showOTC && hasOTC) || (showRegular && hasRegular);
    });

    if (filteredAssets.length === 0) return null;
    
    // Ensure selectedAssets is always an array for safe checking
    const safeSelectedAssets = Array.isArray(selectedAssets) ? selectedAssets : [];

    return (
      <div key={category} className="border border-slate-700/50 rounded-lg overflow-hidden bg-slate-800/30">
        <div className="w-full flex items-center justify-between p-4 bg-slate-800/30 rounded-t-lg">
          <button
            onClick={() => toggleCategory(category)}
            className="flex items-center space-x-3 flex-1 hover:opacity-80 transition-opacity"
          >
            <span className="text-2xl">{icon}</span>
            <div>
              <h3 className="text-lg font-semibold text-white capitalize">{category}</h3>
              <p className="text-sm text-slate-400">{filteredAssets.length} assets available</p>
            </div>
          </button>
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
            <button
              onClick={() => toggleCategory(category)}
              className="text-slate-400 hover:text-white transition-colors"
            >
              {expandedCategories[category] ? '▼' : '▶'}
            </button>
          </div>
        </div>

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
                          checked={safeSelectedAssets.includes(`${asset.symbol}_OTC`)}
                          onCheckedChange={() => handleAssetToggle(asset.symbol, 'otc')}
                        />
                        <span className="text-sm text-purple-400 font-medium">OTC</span>
                      </label>
                    )}
                    {asset.market_types.includes('regular') && showRegular && (
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <Checkbox
                          checked={safeSelectedAssets.includes(asset.symbol)}
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
      {/* Timeframe Selection - only show if not hidden */}
      {!hideExpirations && (
        <Card className="p-6 glass-dark border-emerald-500/20">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-xl font-semibold text-white">⏱️ Trading Expirations</h3>
              <p className="text-slate-400 text-sm mt-1">Select expirations for signal generation</p>
            </div>
            <div className="text-emerald-400 font-medium">
              {selectedExpirations.length} selected
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
            {expirations.map(tf => (
              <button
                key={tf.value}
                onClick={() => handleTimeframeToggle(tf.value)}
                className={`flex flex-col items-center justify-center p-4 rounded-lg border-2 transition-all ${
                  selectedExpirations.includes(tf.value)
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
      )}

      {/* Asset Selection */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-semibold text-white">📊 Market Assets</h3>
            <p className="text-slate-400 text-sm mt-1">
              Select assets for signal generation • {Array.isArray(selectedAssets) ? selectedAssets.length : 0} assets selected
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
