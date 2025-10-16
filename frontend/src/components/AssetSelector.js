import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL || '';

const AssetSelector = ({ onSelectionChange, selectedAssets = [], selectedTimeframes = ['1min'] }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');
  const [localSelectedAssets, setLocalSelectedAssets] = useState(selectedAssets);
  const [localSelectedTimeframes, setLocalSelectedTimeframes] = useState(selectedTimeframes);
  
  // API-driven asset data
  const [pocketOptionAssets, setPocketOptionAssets] = useState({
    forex: [],
    crypto: [],
    stocks: [],
    commodities: [],
    indices: []
  });
  const [assetSummary, setAssetSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showOTC, setShowOTC] = useState(true);

  // Fetch assets from API
  const fetchAssets = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/api/assets/all`);
      
      if (response.data.success) {
        setPocketOptionAssets(response.data.assets);
        setAssetSummary(response.data.summary);
        console.log('✅ Loaded Pocket Option assets:', response.data.summary);
      } else {
        toast.error('Failed to load asset list');
        console.error('Failed to load assets:', response.data.error);
      }
    } catch (error) {
      console.error('Error fetching assets:', error);
      toast.error('Error loading assets from server');
      
      // Fallback to minimal asset list
      setPocketOptionAssets({
        forex: [{ symbol: 'EURUSD', display_name: 'EUR/USD', description: 'Euro vs US Dollar' }],
        crypto: [{ symbol: 'BTCUSD', display_name: 'BTC/USD', description: 'Bitcoin vs US Dollar' }],
        stocks: [{ symbol: 'AAPL', display_name: 'AAPL - Apple Inc.', description: 'Technology - Consumer Electronics' }],
        commodities: [{ symbol: 'XAUUSD', display_name: 'Gold OTC', description: 'Precious Metals - Gold Spot Price' }],
        indices: [{ symbol: 'US100', display_name: 'US100 (NASDAQ)', description: 'US Technology Index' }]
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  // Category metadata
  const categoryInfo = {
    forex: { name: 'Forex', icon: '💱' },
    crypto: { name: 'Cryptocurrency', icon: '₿' },
    stocks: { name: 'Stocks', icon: '📈' },
    commodities: { name: 'Commodities', icon: '🛢️' },
    indices: { name: 'Indices', icon: '📊' }
  };

  // Pocket Option Timeframes
  const timeframes = [
    { value: '5s', label: '5 Seconds', category: 'ultra' },
    { value: '15s', label: '15 Seconds', category: 'ultra' },
    { value: '30s', label: '30 Seconds', category: 'ultra' },
    { value: '1m', label: '1 Minute', category: 'short' },
    { value: '2m', label: '2 Minutes', category: 'short' },
    { value: '3m', label: '3 Minutes', category: 'short' },
    { value: '5m', label: '5 Minutes', category: 'medium' },
    { value: '10m', label: '10 Minutes', category: 'medium' },
    { value: '15m', label: '15 Minutes', category: 'medium' },
    { value: '30m', label: '30 Minutes', category: 'long' }
  ];

  // Get all assets for filtering
  const getAllAssets = () => {
    const allAssets = [];
    Object.keys(pocketOptionAssets).forEach(category => {
      const categoryAssets = pocketOptionAssets[category];
      const categoryMeta = categoryInfo[category];
      
      if (Array.isArray(categoryAssets)) {
        // Handle API structure where assets are directly in an array
        categoryAssets.forEach(asset => {
          const marketTypes = asset.market_types || (asset.market_type ? [asset.market_type] : ['regular']);
          
          // Create separate entries for each market type (regular and OTC)
          marketTypes.forEach(marketType => {
            // Apply OTC filter
            if (!showOTC && marketType === 'otc') {
              return; // Skip OTC assets if showOTC is false
            }
            
            allAssets.push({
              ...asset,
              category,
              categoryName: categoryMeta?.name || category,
              icon: categoryMeta?.icon || '📊',
              // Ensure we have the required fields for compatibility
              symbol: asset.symbol,
              name: asset.display_name || asset.name || asset.symbol,
              market: marketType,
              // Add market type badge info
              isOTC: marketType === 'otc',
              marketLabel: marketType === 'otc' ? '🌙 OTC' : '🌞 Regular'
            });
          });
        });
      } else if (categoryAssets && typeof categoryAssets === 'object') {
        // Handle legacy structure with regular/otc arrays (fallback)
        const regularAssets = categoryAssets.regular || [];
        const otcAssets = categoryAssets.otc || [];
        
        [...regularAssets, ...otcAssets].forEach(asset => {
          const marketType = asset.market || asset.market_type || 'regular';
          
          // Apply OTC filter
          if (!showOTC && marketType === 'otc') {
            return; // Skip OTC assets if showOTC is false
          }
          
          allAssets.push({
            ...asset,
            category,
            categoryName: categoryMeta?.name || category,
            icon: categoryMeta?.icon || '📊',
            market: marketType,
            isOTC: marketType === 'otc',
            marketLabel: marketType === 'otc' ? '🌙 OTC' : '🌞 Regular'
          });
        });
      }
    });
    return allAssets;
  };

  const filteredAssets = getAllAssets().filter(asset => {
    const displayName = asset.display_name || asset.name || asset.symbol;
    const description = asset.description || '';
    const matchesSearch = asset.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         displayName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = activeCategory === 'all' || asset.category === activeCategory;
    return matchesSearch && matchesCategory;
  });

  const handleAssetToggle = (asset) => {
    const assetId = `${asset.symbol}_${asset.market}`;
    const newSelection = localSelectedAssets.includes(assetId)
      ? localSelectedAssets.filter(id => id !== assetId)
      : [...localSelectedAssets, assetId];
    
    setLocalSelectedAssets(newSelection);
    onSelectionChange?.(newSelection, localSelectedTimeframes);
  };

  const handleTimeframeToggle = (timeframe) => {
    const newTimeframes = localSelectedTimeframes.includes(timeframe)
      ? localSelectedTimeframes.filter(tf => tf !== timeframe)
      : [...localSelectedTimeframes, timeframe];
    
    setLocalSelectedTimeframes(newTimeframes);
    onSelectionChange?.(localSelectedAssets, newTimeframes);
  };

  const selectAllInCategory = (category) => {
    const categoryAssets = getAllAssets().filter(asset => asset.category === category);
    const categoryIds = categoryAssets.map(asset => `${asset.symbol}_${asset.market}`);
    const newSelection = [...new Set([...localSelectedAssets, ...categoryIds])];
    setLocalSelectedAssets(newSelection);
    onSelectionChange?.(newSelection, localSelectedTimeframes);
  };

  const clearAllInCategory = (category) => {
    const categoryAssets = getAllAssets().filter(asset => asset.category === category);
    const categoryIds = categoryAssets.map(asset => `${asset.symbol}_${asset.market}`);
    const newSelection = localSelectedAssets.filter(id => !categoryIds.includes(id));
    setLocalSelectedAssets(newSelection);
    onSelectionChange?.(newSelection, localSelectedTimeframes);
  };

  return (
    <div className="space-y-6" data-testid="asset-selector">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-semibold text-white">Asset & Timeframe Selection</h3>
          <p className="text-slate-400 text-sm">
            Select assets and timeframes for trading signal generation
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
            {localSelectedAssets.length} Assets
          </Badge>
          <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
            {localSelectedTimeframes.length} Timeframes
          </Badge>
        </div>
      </div>

      <Tabs defaultValue="assets" className="w-full">
        <TabsList className="grid w-full grid-cols-2 bg-slate-800/30">
          <TabsTrigger value="assets" className="data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400">
            Assets Selection
          </TabsTrigger>
          <TabsTrigger value="timeframes" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">
            Timeframes
          </TabsTrigger>
        </TabsList>

        {/* Assets Tab */}
        <TabsContent value="assets" className="space-y-4">
          {/* Search and Filters */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search assets (e.g., EURUSD, Bitcoin, Apple...)"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-800/50 border-slate-600 text-white"
              />
            </div>
            <Select value={activeCategory} onValueChange={setActiveCategory}>
              <SelectTrigger className="w-48 bg-slate-800/50 border-slate-600 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-600">
                <SelectItem value="all">All Categories</SelectItem>
                {Object.keys(categoryInfo).map(categoryKey => (
                  <SelectItem key={categoryKey} value={categoryKey}>
                    {categoryInfo[categoryKey].icon} {categoryInfo[categoryKey].name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Loading State */}
          {loading && (
            <Card className="p-6 glass-dark border-slate-700/50">
              <div className="flex items-center justify-center space-x-3">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-emerald-500"></div>
                <p className="text-slate-400">Loading assets...</p>
              </div>
            </Card>
          )}

          {/* Category Cards */}
          {!loading && Object.keys(pocketOptionAssets).map(categoryKey => {
            const categoryAssets = pocketOptionAssets[categoryKey];
            const categoryMeta = categoryInfo[categoryKey];
            
            // Handle both API structure (array) and legacy structure (object with regular/otc)
            let allAssets = [];
            let regularAssets = [];
            let otcAssets = [];
            
            if (Array.isArray(categoryAssets)) {
              // API structure: assets are directly in an array
              allAssets = categoryAssets;
              regularAssets = categoryAssets.filter(asset => 
                (asset.market_type || asset.market || 'regular') === 'regular'
              );
              otcAssets = categoryAssets.filter(asset => 
                (asset.market_type || asset.market || 'regular') === 'otc'
              );
            } else if (categoryAssets && typeof categoryAssets === 'object') {
              // Legacy structure: regular and otc arrays
              regularAssets = categoryAssets.regular || [];
              otcAssets = categoryAssets.otc || [];
              allAssets = [...regularAssets, ...otcAssets];
            }
            
            const selectedCount = allAssets.filter(asset => {
              const market = asset.market_type || asset.market || 'regular';
              return localSelectedAssets.includes(`${asset.symbol}_${market}`);
            }).length;
            
            if (activeCategory !== 'all' && activeCategory !== categoryKey) return null;

            return (
              <Card key={categoryKey} className="p-6 glass-dark border-slate-700/50">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <span className="text-2xl">{categoryMeta?.icon || '📊'}</span>
                    <div>
                      <h4 className="text-white font-semibold text-lg">{categoryMeta?.name || categoryKey}</h4>
                      <p className="text-slate-400 text-sm">
                        {allAssets.length} assets • {selectedCount} selected
                      </p>
                    </div>
                  </div>
                  <div className="flex space-x-2">
                    <Button
                      size="sm"
                      onClick={() => selectAllInCategory(categoryKey)}
                      className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
                    >
                      Select All
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => clearAllInCategory(categoryKey)}
                      className="bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
                    >
                      Clear All
                    </Button>
                  </div>
                </div>

                {/* Regular Exchange Assets */}
                {regularAssets.length > 0 && (
                  <div className="mb-6">
                    <h5 className="text-emerald-400 font-medium mb-3 flex items-center">
                      <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2"></span>
                      Regular Exchange
                    </h5>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {regularAssets.map(asset => {
                        const market = asset.market_type || asset.market || 'regular';
                        const assetId = `${asset.symbol}_${market}`;
                        const isSelected = localSelectedAssets.includes(assetId);
                        const displayName = asset.display_name || asset.name || asset.symbol;
                        
                        return (
                          <div
                            key={assetId}
                            onClick={() => handleAssetToggle({...asset, market})}
                            className={`p-3 rounded-lg border cursor-pointer transition-all duration-200 ${
                              isSelected
                                ? 'border-emerald-500/50 bg-emerald-500/10'
                                : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="text-white font-medium">{asset.symbol}</p>
                                <p className="text-slate-400 text-xs">{displayName}</p>
                                {asset.description && (
                                  <p className="text-slate-500 text-xs mt-1">{asset.description}</p>
                                )}
                              </div>
                              <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                                isSelected
                                  ? 'border-emerald-500 bg-emerald-500'
                                  : 'border-slate-400'
                              }`}>
                                {isSelected && <span className="text-white text-xs">✓</span>}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* OTC Market Assets */}
                {otcAssets.length > 0 && (
                  <div>
                    <h5 className="text-blue-400 font-medium mb-3 flex items-center">
                      <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
                      OTC Market (24/7)
                    </h5>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {otcAssets.map(asset => {
                        const market = asset.market_type || asset.market || 'otc';
                        const assetId = `${asset.symbol}_${market}`;
                        const isSelected = localSelectedAssets.includes(assetId);
                        const displayName = asset.display_name || asset.name || asset.symbol;
                        
                        return (
                          <div
                            key={assetId}
                            onClick={() => handleAssetToggle({...asset, market})}
                            className={`p-3 rounded-lg border cursor-pointer transition-all duration-200 ${
                              isSelected
                                ? 'border-blue-500/50 bg-blue-500/10'
                                : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="text-white font-medium">{asset.symbol}</p>
                                <p className="text-slate-400 text-xs">{displayName}</p>
                                {asset.description && (
                                  <p className="text-slate-500 text-xs mt-1">{asset.description}</p>
                                )}
                                <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 text-xs mt-1">
                                  24/7
                                </Badge>
                              </div>
                              <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                                isSelected
                                  ? 'border-blue-500 bg-blue-500'
                                  : 'border-slate-400'
                              }`}>
                                {isSelected && <span className="text-white text-xs">✓</span>}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </TabsContent>

        {/* Timeframes Tab */}
        <TabsContent value="timeframes" className="space-y-4">
          <Card className="p-6 glass-dark border-slate-700/50">
            <h4 className="text-white font-semibold text-lg mb-6">Select Trading Timeframes</h4>
            
            {/* Ultra Short (Seconds) */}
            <div className="mb-6">
              <h5 className="text-red-400 font-medium mb-3 flex items-center">
                <span className="w-2 h-2 bg-red-500 rounded-full mr-2"></span>
                Ultra Short Term (Seconds)
              </h5>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {timeframes.filter(tf => tf.category === 'ultra').map(timeframe => {
                  const isSelected = localSelectedTimeframes.includes(timeframe.value);
                  
                  return (
                    <div
                      key={timeframe.value}
                      onClick={() => handleTimeframeToggle(timeframe.value)}
                      className={`p-4 text-center rounded-lg border cursor-pointer transition-all duration-200 ${
                        isSelected
                          ? 'border-red-500/50 bg-red-500/10'
                          : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
                      }`}
                    >
                      <p className="text-white font-medium">{timeframe.label}</p>
                      <div className={`w-4 h-4 rounded border-2 mx-auto mt-2 flex items-center justify-center ${
                        isSelected
                          ? 'border-red-500 bg-red-500'
                          : 'border-slate-400'
                      }`}>
                        {isSelected && <span className="text-white text-xs">✓</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Short Term (Minutes) */}
            <div className="mb-6">
              <h5 className="text-yellow-400 font-medium mb-3 flex items-center">
                <span className="w-2 h-2 bg-yellow-500 rounded-full mr-2"></span>
                Short Term (1-3 Minutes)
              </h5>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {timeframes.filter(tf => tf.category === 'short').map(timeframe => {
                  const isSelected = localSelectedTimeframes.includes(timeframe.value);
                  
                  return (
                    <div
                      key={timeframe.value}
                      onClick={() => handleTimeframeToggle(timeframe.value)}
                      className={`p-4 text-center rounded-lg border cursor-pointer transition-all duration-200 ${
                        isSelected
                          ? 'border-yellow-500/50 bg-yellow-500/10'
                          : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
                      }`}
                    >
                      <p className="text-white font-medium">{timeframe.label}</p>
                      <div className={`w-4 h-4 rounded border-2 mx-auto mt-2 flex items-center justify-center ${
                        isSelected
                          ? 'border-yellow-500 bg-yellow-500'
                          : 'border-slate-400'
                      }`}>
                        {isSelected && <span className="text-white text-xs">✓</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Medium Term */}
            <div className="mb-6">
              <h5 className="text-emerald-400 font-medium mb-3 flex items-center">
                <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2"></span>
                Medium Term (5-15 Minutes)
              </h5>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {timeframes.filter(tf => tf.category === 'medium').map(timeframe => {
                  const isSelected = localSelectedTimeframes.includes(timeframe.value);
                  
                  return (
                    <div
                      key={timeframe.value}
                      onClick={() => handleTimeframeToggle(timeframe.value)}
                      className={`p-4 text-center rounded-lg border cursor-pointer transition-all duration-200 ${
                        isSelected
                          ? 'border-emerald-500/50 bg-emerald-500/10'
                          : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
                      }`}
                    >
                      <p className="text-white font-medium">{timeframe.label}</p>
                      <div className={`w-4 h-4 rounded border-2 mx-auto mt-2 flex items-center justify-center ${
                        isSelected
                          ? 'border-emerald-500 bg-emerald-500'
                          : 'border-slate-400'
                      }`}>
                        {isSelected && <span className="text-white text-xs">✓</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Long Term */}
            <div>
              <h5 className="text-blue-400 font-medium mb-3 flex items-center">
                <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
                Long Term (30 Minutes)
              </h5>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {timeframes.filter(tf => tf.category === 'long').map(timeframe => {
                  const isSelected = localSelectedTimeframes.includes(timeframe.value);
                  
                  return (
                    <div
                      key={timeframe.value}
                      onClick={() => handleTimeframeToggle(timeframe.value)}
                      className={`p-4 text-center rounded-lg border cursor-pointer transition-all duration-200 ${
                        isSelected
                          ? 'border-blue-500/50 bg-blue-500/10'
                          : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
                      }`}
                    >
                      <p className="text-white font-medium">{timeframe.label}</p>
                      <div className={`w-4 h-4 rounded border-2 mx-auto mt-2 flex items-center justify-center ${
                        isSelected
                          ? 'border-blue-500 bg-blue-500'
                          : 'border-slate-400'
                      }`}>
                        {isSelected && <span className="text-white text-xs">✓</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AssetSelector;