import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import { Input } from './ui/input';

const API = process.env.REACT_APP_BACKEND_URL || '';

const AssetSelectorDropdown = ({ selectedAssets, onAssetsChange, selectedTimeframes, onTimeframesChange }) => {
  const [loading, setLoading] = useState(true);
  const [allAssets, setAllAssets] = useState({});
  const [selectedMarketType, setSelectedMarketType] = useState('regular'); // 'regular' or 'otc'
  const [selectedCategory, setSelectedCategory] = useState('forex');
  const [searchTerm, setSearchTerm] = useState('');
  const [localSelectedAssets, setLocalSelectedAssets] = useState(selectedAssets || []);
  const [localSelectedTimeframes, setLocalSelectedTimeframes] = useState(selectedTimeframes || []);

  // Category metadata
  const categoryInfo = {
    forex: { name: 'Forex', icon: '💱', description: 'Currency Pairs' },
    cryptocurrency: { name: 'Cryptocurrency', icon: '₿', description: 'Digital Assets' },
    stocks: { name: 'Stocks', icon: '📈', description: 'Company Shares' },
    commodities: { name: 'Commodities', icon: '🛢️', description: 'Raw Materials' },
    indices: { name: 'Indices', icon: '📊', description: 'Market Indices' }
  };

  // Pocket Option timeframes
  const availableTimeframes = ['5s', '15s', '30s', '1m', '3m', '5m', '15m', '30m'];

  useEffect(() => {
    fetchAssets();
  }, []);

  const fetchAssets = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API}/api/assets/all`);
      const result = await response.json();
      
      // API returns { success: true, assets: {...} }
      const data = result.assets || result;
      
      setAllAssets(data);
      console.log('✅ Loaded Pocket Option assets:', {
        forex_count: data.forex?.length || 0,
        crypto_count: data.cryptocurrency?.length || 0,
        stocks_count: data.stocks?.length || 0,
        commodities_count: data.commodities?.length || 0,
        indices_count: data.indices?.length || 0
      });
    } catch (error) {
      console.error('Error fetching assets:', error);
    } finally {
      setLoading(false);
    }
  };

  // Get assets for current market type and category
  const getCurrentAssets = () => {
    if (!allAssets[selectedCategory]) return [];
    
    const categoryAssets = allAssets[selectedCategory];
    if (!Array.isArray(categoryAssets)) return [];
    
    const expandedAssets = categoryAssets
      .map(asset => {
        // Get market types - handle both array and single value
        let marketTypes = asset.market_types || [];
        
        // If no market_types defined, check if asset has market_type field
        if (marketTypes.length === 0 && asset.market_type) {
          marketTypes = [asset.market_type];
        }
        
        // If still no market types, default to both regular and otc
        if (marketTypes.length === 0) {
          marketTypes = ['regular', 'otc'];
        }
        
        // Create separate entries for each market type
        return marketTypes.map(marketType => ({
          ...asset,
          market_type: marketType,
          asset_id: `${asset.symbol}_${marketType}`,
          display_name: asset.display_name || asset.name || asset.symbol
        }));
      })
      .flat()
      .filter(asset => asset.market_type === selectedMarketType);
    
    // Apply search filter
    const filteredAssets = expandedAssets.filter(asset => {
      if (!searchTerm) return true;
      const search = searchTerm.toLowerCase();
      return (
        asset.symbol.toLowerCase().includes(search) ||
        asset.display_name.toLowerCase().includes(search)
      );
    });
    
    // Debug logging
    if (filteredAssets.length === 0 && expandedAssets.length > 0) {
      console.log(`No ${selectedMarketType} assets found in ${selectedCategory} after search filter`);
    }
    
    return filteredAssets;
  };

  const handleAssetToggle = (assetId) => {
    const newSelection = localSelectedAssets.includes(assetId)
      ? localSelectedAssets.filter(id => id !== assetId)
      : [...localSelectedAssets, assetId];
    
    setLocalSelectedAssets(newSelection);
    onAssetsChange(newSelection);
  };

  const handleTimeframeToggle = (timeframe) => {
    const newSelection = localSelectedTimeframes.includes(timeframe)
      ? localSelectedTimeframes.filter(t => t !== timeframe)
      : [...localSelectedTimeframes, timeframe];
    
    setLocalSelectedTimeframes(newSelection);
    onTimeframesChange(newSelection);
  };

  const handleSelectAllInCategory = () => {
    const categoryAssets = getCurrentAssets();
    const categoryAssetIds = categoryAssets.map(a => a.asset_id);
    const newSelection = [...new Set([...localSelectedAssets, ...categoryAssetIds])];
    setLocalSelectedAssets(newSelection);
    onAssetsChange(newSelection);
  };

  const handleClearAllInCategory = () => {
    const categoryAssets = getCurrentAssets();
    const categoryAssetIds = new Set(categoryAssets.map(a => a.asset_id));
    const newSelection = localSelectedAssets.filter(id => !categoryAssetIds.has(id));
    setLocalSelectedAssets(newSelection);
    onAssetsChange(newSelection);
  };

  const currentAssets = getCurrentAssets();
  const selectedInCategory = currentAssets.filter(a => localSelectedAssets.includes(a.asset_id)).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-semibold text-white">Asset Selection</h3>
          <p className="text-slate-400 text-sm mt-1">
            Select assets and timeframes for signal generation
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-green-400">{localSelectedAssets.length}</div>
          <div className="text-slate-400 text-sm">Assets Selected</div>
        </div>
      </div>

      {/* Market Type Selector */}
      <Card className="bg-slate-800/50 border-slate-700 p-6">
        <Label className="text-slate-300 font-medium mb-3 block">Market Type</Label>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => setSelectedMarketType('regular')}
            className={`p-4 rounded-lg border-2 transition-all ${
              selectedMarketType === 'regular'
                ? 'border-green-500 bg-green-500/20 text-white'
                : 'border-slate-600 bg-slate-800/50 text-slate-400 hover:border-slate-500'
            }`}
          >
            <div className="text-2xl mb-2">🌞</div>
            <div className="font-semibold">Regular Exchange</div>
            <div className="text-xs mt-1 opacity-75">Exchange trading hours</div>
          </button>
          
          <button
            onClick={() => setSelectedMarketType('otc')}
            className={`p-4 rounded-lg border-2 transition-all ${
              selectedMarketType === 'otc'
                ? 'border-blue-500 bg-blue-500/20 text-white'
                : 'border-slate-600 bg-slate-800/50 text-slate-400 hover:border-slate-500'
            }`}
          >
            <div className="text-2xl mb-2">🌙</div>
            <div className="font-semibold">OTC Markets</div>
            <div className="text-xs mt-1 opacity-75">24/7 Availability</div>
          </button>
        </div>
      </Card>

      {/* Category Selector */}
      <Card className="bg-slate-800/50 border-slate-700 p-6">
        <Label className="text-slate-300 font-medium mb-3 block">Asset Category</Label>
        <Select value={selectedCategory} onValueChange={setSelectedCategory}>
          <SelectTrigger className="bg-slate-800 border-slate-600 text-white">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-slate-800 border-slate-600">
            {Object.keys(categoryInfo).map(key => (
              <SelectItem key={key} value={key}>
                {categoryInfo[key].icon} {categoryInfo[key].name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Card>

      {/* Asset List */}
      <Card className="bg-slate-800/50 border-slate-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="text-lg font-semibold text-white flex items-center gap-2">
              {categoryInfo[selectedCategory].icon}
              {categoryInfo[selectedCategory].name}
              {selectedMarketType === 'otc' && <span className="text-blue-400 text-sm">(OTC 24/7)</span>}
              {selectedMarketType === 'regular' && <span className="text-green-400 text-sm">(Regular)</span>}
            </h4>
            <p className="text-slate-400 text-sm">
              {selectedInCategory} of {currentAssets.length} selected
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleSelectAllInCategory}
              className="border-slate-600 text-slate-300 hover:bg-slate-700"
            >
              Select All
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearAllInCategory}
              className="border-slate-600 text-slate-300 hover:bg-slate-700"
            >
              Clear All
            </Button>
          </div>
        </div>

        {/* Search */}
        <Input
          placeholder="Search assets..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="mb-4 bg-slate-800 border-slate-600 text-white"
        />

        {/* Asset Checkboxes */}
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {loading ? (
            <div className="text-center text-slate-400 py-8">Loading assets...</div>
          ) : currentAssets.length === 0 ? (
            <div className="text-center text-slate-400 py-8">
              No {selectedMarketType} assets available in {categoryInfo[selectedCategory].name}
            </div>
          ) : (
            currentAssets.map(asset => (
              <div
                key={asset.asset_id}
                className="flex items-center space-x-3 p-3 rounded-lg bg-slate-800/50 hover:bg-slate-700/50 transition-colors"
              >
                <Checkbox
                  id={asset.asset_id}
                  checked={localSelectedAssets.includes(asset.asset_id)}
                  onCheckedChange={() => handleAssetToggle(asset.asset_id)}
                />
                <label
                  htmlFor={asset.asset_id}
                  className="flex-1 cursor-pointer text-white"
                >
                  <div className="font-medium">{asset.symbol}</div>
                  <div className="text-sm text-slate-400">{asset.display_name}</div>
                </label>
                <div className={`text-xs px-2 py-1 rounded ${
                  selectedMarketType === 'otc' 
                    ? 'bg-blue-500/20 text-blue-400' 
                    : 'bg-green-500/20 text-green-400'
                }`}>
                  {selectedMarketType === 'otc' ? '24/7' : 'Exchange'}
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Timeframe Selection */}
      <Card className="bg-slate-800/50 border-slate-700 p-6">
        <h4 className="text-lg font-semibold text-white mb-4">Timeframes</h4>
        <div className="grid grid-cols-4 gap-3">
          {availableTimeframes.map(tf => (
            <button
              key={tf}
              onClick={() => handleTimeframeToggle(tf)}
              className={`p-3 rounded-lg font-medium transition-all ${
                localSelectedTimeframes.includes(tf)
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </Card>

      {/* Selection Summary */}
      <Card className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 border-blue-700/50 p-4">
        <div className="flex items-center justify-between text-sm">
          <div className="text-slate-300">
            <span className="font-semibold text-white">{localSelectedAssets.length}</span> assets • 
            <span className="font-semibold text-white ml-1">{localSelectedTimeframes.length}</span> timeframes selected
          </div>
          <div className="text-blue-400">
            Ready to generate signals
          </div>
        </div>
      </Card>
    </div>
  );
};

export default AssetSelectorDropdown;
