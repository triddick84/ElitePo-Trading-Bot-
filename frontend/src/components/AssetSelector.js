import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Switch } from './ui/switch';
import { Label } from './ui/label';

const AssetSelector = ({ onSelectionChange, selectedAssets = [], selectedTimeframes = ['1min'] }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');
  const [localSelectedAssets, setLocalSelectedAssets] = useState(selectedAssets);
  const [localSelectedTimeframes, setLocalSelectedTimeframes] = useState(selectedTimeframes);

  // Complete Pocket Option Asset List
  const pocketOptionAssets = {
    forex: {
      name: 'Forex',
      icon: '💱',
      regular: [
        // Major Pairs
        { symbol: 'EURUSD', name: 'Euro/US Dollar', market: 'regular' },
        { symbol: 'GBPUSD', name: 'British Pound/US Dollar', market: 'regular' },
        { symbol: 'USDJPY', name: 'US Dollar/Japanese Yen', market: 'regular' },
        { symbol: 'USDCHF', name: 'US Dollar/Swiss Franc', market: 'regular' },
        { symbol: 'AUDUSD', name: 'Australian Dollar/US Dollar', market: 'regular' },
        { symbol: 'USDCAD', name: 'US Dollar/Canadian Dollar', market: 'regular' },
        { symbol: 'NZDUSD', name: 'New Zealand Dollar/US Dollar', market: 'regular' },
        
        // Minor Pairs
        { symbol: 'EURGBP', name: 'Euro/British Pound', market: 'regular' },
        { symbol: 'EURJPY', name: 'Euro/Japanese Yen', market: 'regular' },
        { symbol: 'GBPJPY', name: 'British Pound/Japanese Yen', market: 'regular' },
        { symbol: 'CHFJPY', name: 'Swiss Franc/Japanese Yen', market: 'regular' },
        { symbol: 'EURCHF', name: 'Euro/Swiss Franc', market: 'regular' },
        { symbol: 'AUDCAD', name: 'Australian Dollar/Canadian Dollar', market: 'regular' },
        { symbol: 'CADJPY', name: 'Canadian Dollar/Japanese Yen', market: 'regular' },
        { symbol: 'AUDCHF', name: 'Australian Dollar/Swiss Franc', market: 'regular' },
        { symbol: 'AUDJPY', name: 'Australian Dollar/Japanese Yen', market: 'regular' },
        { symbol: 'EURAUD', name: 'Euro/Australian Dollar', market: 'regular' },
        { symbol: 'EURCAD', name: 'Euro/Canadian Dollar', market: 'regular' },
        { symbol: 'GBPAUD', name: 'British Pound/Australian Dollar', market: 'regular' },
        { symbol: 'GBPCAD', name: 'British Pound/Canadian Dollar', market: 'regular' },
        { symbol: 'GBPCHF', name: 'British Pound/Swiss Franc', market: 'regular' },
        { symbol: 'NZDCAD', name: 'New Zealand Dollar/Canadian Dollar', market: 'regular' },
        { symbol: 'NZDCHF', name: 'New Zealand Dollar/Swiss Franc', market: 'regular' },
        { symbol: 'NZDJPY', name: 'New Zealand Dollar/Japanese Yen', market: 'regular' },
      ],
      otc: [
        // OTC Forex (24/7 Trading)
        { symbol: 'EURUSD_OTC', name: 'Euro/US Dollar (OTC)', market: 'otc' },
        { symbol: 'GBPUSD_OTC', name: 'British Pound/US Dollar (OTC)', market: 'otc' },
        { symbol: 'USDJPY_OTC', name: 'US Dollar/Japanese Yen (OTC)', market: 'otc' },
        { symbol: 'USDCHF_OTC', name: 'US Dollar/Swiss Franc (OTC)', market: 'otc' },
        { symbol: 'AUDUSD_OTC', name: 'Australian Dollar/US Dollar (OTC)', market: 'otc' },
        { symbol: 'USDCAD_OTC', name: 'US Dollar/Canadian Dollar (OTC)', market: 'otc' },
        { symbol: 'NZDUSD_OTC', name: 'New Zealand Dollar/US Dollar (OTC)', market: 'otc' },
        
        // Exotic Pairs OTC
        { symbol: 'NGENUSD_OTC', name: 'Nigerian Naira/US Dollar (OTC)', market: 'otc' },
        { symbol: 'KESUSD_OTC', name: 'Kenyan Shilling/US Dollar (OTC)', market: 'otc' },
        { symbol: 'ZARUSD_OTC', name: 'South African Rand/US Dollar (OTC)', market: 'otc' },
        { symbol: 'UAHUSD_OTC', name: 'Ukrainian Hryvnia/US Dollar (OTC)', market: 'otc' },
        { symbol: 'USDRUB_OTC', name: 'US Dollar/Russian Ruble (OTC)', market: 'otc' },
        { symbol: 'USDTRY_OTC', name: 'US Dollar/Turkish Lira (OTC)', market: 'otc' },
        { symbol: 'USDBRL_OTC', name: 'US Dollar/Brazilian Real (OTC)', market: 'otc' },
        { symbol: 'USDMXN_OTC', name: 'US Dollar/Mexican Peso (OTC)', market: 'otc' },
        { symbol: 'USDINR_OTC', name: 'US Dollar/Indian Rupee (OTC)', market: 'otc' },
      ]
    },
    
    crypto: {
      name: 'Cryptocurrency',
      icon: '₿',
      regular: [
        { symbol: 'BTCUSD', name: 'Bitcoin/US Dollar', market: 'regular' },
        { symbol: 'ETHUSD', name: 'Ethereum/US Dollar', market: 'regular' },
        { symbol: 'LTCUSD', name: 'Litecoin/US Dollar', market: 'regular' },
        { symbol: 'XRPUSD', name: 'Ripple/US Dollar', market: 'regular' },
        { symbol: 'ADAUSD', name: 'Cardano/US Dollar', market: 'regular' },
        { symbol: 'DOTUSD', name: 'Polkadot/US Dollar', market: 'regular' },
        { symbol: 'BNBUSD', name: 'Binance Coin/US Dollar', market: 'regular' },
        { symbol: 'SOLUSD', name: 'Solana/US Dollar', market: 'regular' },
        { symbol: 'AVAXUSD', name: 'Avalanche/US Dollar', market: 'regular' },
        { symbol: 'DASHUSD', name: 'Dash/US Dollar', market: 'regular' },
        { symbol: 'BCHUSD', name: 'Bitcoin Cash/US Dollar', market: 'regular' },
        { symbol: 'DOGEUSD', name: 'Dogecoin/US Dollar', market: 'regular' },
        
        // Crypto vs EUR
        { symbol: 'BTCEUR', name: 'Bitcoin/Euro', market: 'regular' },
        { symbol: 'ETHEUR', name: 'Ethereum/Euro', market: 'regular' },
        { symbol: 'LTCEUR', name: 'Litecoin/Euro', market: 'regular' },
        
        // Crypto vs GBP
        { symbol: 'BTCGBP', name: 'Bitcoin/British Pound', market: 'regular' },
        { symbol: 'ETHGBP', name: 'Ethereum/British Pound', market: 'regular' },
        
        // Crypto vs JPY
        { symbol: 'BTCJPY', name: 'Bitcoin/Japanese Yen', market: 'regular' },
        { symbol: 'ETHJPY', name: 'Ethereum/Japanese Yen', market: 'regular' },
      ],
      otc: [
        { symbol: 'BTCUSD_OTC', name: 'Bitcoin/US Dollar (OTC)', market: 'otc' },
        { symbol: 'ETHUSD_OTC', name: 'Ethereum/US Dollar (OTC)', market: 'otc' },
        { symbol: 'LTCUSD_OTC', name: 'Litecoin/US Dollar (OTC)', market: 'otc' },
        { symbol: 'XRPUSD_OTC', name: 'Ripple/US Dollar (OTC)', market: 'otc' },
        { symbol: 'ADAUSD_OTC', name: 'Cardano/US Dollar (OTC)', market: 'otc' },
        { symbol: 'BNBUSD_OTC', name: 'Binance Coin/US Dollar (OTC)', market: 'otc' },
      ]
    },
    
    stocks: {
      name: 'Stocks',
      icon: '📈',
      regular: [
        // Tech Stocks
        { symbol: 'AAPL', name: 'Apple Inc.', market: 'regular' },
        { symbol: 'GOOGL', name: 'Alphabet Inc. (Google)', market: 'regular' },
        { symbol: 'MSFT', name: 'Microsoft Corporation', market: 'regular' },
        { symbol: 'AMZN', name: 'Amazon.com Inc.', market: 'regular' },
        { symbol: 'TSLA', name: 'Tesla Inc.', market: 'regular' },
        { symbol: 'META', name: 'Meta Platforms Inc. (Facebook)', market: 'regular' },
        { symbol: 'NVDA', name: 'NVIDIA Corporation', market: 'regular' },
        { symbol: 'NFLX', name: 'Netflix Inc.', market: 'regular' },
        { symbol: 'AMD', name: 'Advanced Micro Devices', market: 'regular' },
        { symbol: 'INTC', name: 'Intel Corporation', market: 'regular' },
        { symbol: 'PLTR', name: 'Palantir Technologies', market: 'regular' },
        
        // Financial
        { symbol: 'JPM', name: 'JPMorgan Chase & Co.', market: 'regular' },
        { symbol: 'BAC', name: 'Bank of America Corp.', market: 'regular' },
        { symbol: 'WFC', name: 'Wells Fargo & Co.', market: 'regular' },
        { symbol: 'GS', name: 'Goldman Sachs Group Inc.', market: 'regular' },
        { symbol: 'V', name: 'Visa Inc.', market: 'regular' },
        { symbol: 'MA', name: 'Mastercard Inc.', market: 'regular' },
        { symbol: 'COIN', name: 'Coinbase Global Inc.', market: 'regular' },
        
        // Other Major Stocks
        { symbol: 'BA', name: 'Boeing Company', market: 'regular' },
        { symbol: 'KO', name: 'Coca-Cola Company', market: 'regular' },
        { symbol: 'PFE', name: 'Pfizer Inc.', market: 'regular' },
        { symbol: 'JNJ', name: 'Johnson & Johnson', market: 'regular' },
        { symbol: 'DIS', name: 'Walt Disney Company', market: 'regular' },
        { symbol: 'NKE', name: 'Nike Inc.', market: 'regular' },
        { symbol: 'MCD', name: 'McDonald\'s Corporation', market: 'regular' },
        { symbol: 'WMT', name: 'Walmart Inc.', market: 'regular' },
        { symbol: 'GME', name: 'GameStop Corp.', market: 'regular' },
        { symbol: 'AMC', name: 'AMC Entertainment Holdings', market: 'regular' },
        { symbol: 'MARA', name: 'Marathon Digital Holdings', market: 'regular' },
      ],
      otc: [
        // OTC Stocks (24/7 Trading)
        { symbol: 'AAPL_OTC', name: 'Apple Inc. (OTC)', market: 'otc' },
        { symbol: 'GOOGL_OTC', name: 'Alphabet Inc. (OTC)', market: 'otc' },
        { symbol: 'MSFT_OTC', name: 'Microsoft Corporation (OTC)', market: 'otc' },
        { symbol: 'AMZN_OTC', name: 'Amazon.com Inc. (OTC)', market: 'otc' },
        { symbol: 'TSLA_OTC', name: 'Tesla Inc. (OTC)', market: 'otc' },
        { symbol: 'META_OTC', name: 'Meta Platforms Inc. (OTC)', market: 'otc' },
        { symbol: 'NVDA_OTC', name: 'NVIDIA Corporation (OTC)', market: 'otc' },
        { symbol: 'NFLX_OTC', name: 'Netflix Inc. (OTC)', market: 'otc' },
        { symbol: 'BA_OTC', name: 'Boeing Company (OTC)', market: 'otc' },
        { symbol: 'GME_OTC', name: 'GameStop Corp. (OTC)', market: 'otc' },
      ]
    },
    
    commodities: {
      name: 'Commodities',
      icon: '🥇',
      regular: [
        { symbol: 'XAUUSD', name: 'Gold/US Dollar', market: 'regular' },
        { symbol: 'XAGUSD', name: 'Silver/US Dollar', market: 'regular' },
        { symbol: 'USOIL', name: 'US Crude Oil (WTI)', market: 'regular' },
        { symbol: 'UKOIL', name: 'UK Brent Crude Oil', market: 'regular' },
        { symbol: 'NATGAS', name: 'Natural Gas', market: 'regular' },
        { symbol: 'COPPER', name: 'Copper', market: 'regular' },
        { symbol: 'PLATINUM', name: 'Platinum', market: 'regular' },
      ],
      otc: [
        { symbol: 'XAUUSD_OTC', name: 'Gold/US Dollar (OTC)', market: 'otc' },
        { symbol: 'XAGUSD_OTC', name: 'Silver/US Dollar (OTC)', market: 'otc' },
        { symbol: 'USOIL_OTC', name: 'US Crude Oil (OTC)', market: 'otc' },
        { symbol: 'UKOIL_OTC', name: 'UK Brent Crude Oil (OTC)', market: 'otc' },
        { symbol: 'NATGAS_OTC', name: 'Natural Gas (OTC)', market: 'otc' },
      ]
    },
    
    indices: {
      name: 'Indices',
      icon: '📊',
      regular: [
        { symbol: 'SPX500', name: 'S&P 500', market: 'regular' },
        { symbol: 'NAS100', name: 'NASDAQ 100', market: 'regular' },
        { symbol: 'DJ30', name: 'Dow Jones 30', market: 'regular' },
        { symbol: 'UK100', name: 'FTSE 100', market: 'regular' },
        { symbol: 'GER30', name: 'DAX 30', market: 'regular' },
        { symbol: 'FRA40', name: 'CAC 40', market: 'regular' },
        { symbol: 'JPN225', name: 'Nikkei 225', market: 'regular' },
        { symbol: 'AUS200', name: 'ASX 200', market: 'regular' },
        { symbol: 'VIX', name: 'Volatility Index', market: 'regular' },
        { symbol: 'RUSSELL2000', name: 'Russell 2000', market: 'regular' },
      ],
      otc: [
        { symbol: 'SPX500_OTC', name: 'S&P 500 (OTC)', market: 'otc' },
        { symbol: 'NAS100_OTC', name: 'NASDAQ 100 (OTC)', market: 'otc' },
        { symbol: 'DJ30_OTC', name: 'Dow Jones 30 (OTC)', market: 'otc' },
        { symbol: 'UK100_OTC', name: 'FTSE 100 (OTC)', market: 'otc' },
        { symbol: 'GER30_OTC', name: 'DAX 30 (OTC)', market: 'otc' },
      ]
    }
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
      const categoryData = pocketOptionAssets[category];
      [...categoryData.regular, ...categoryData.otc].forEach(asset => {
        allAssets.push({
          ...asset,
          category,
          categoryName: categoryData.name,
          icon: categoryData.icon
        });
      });
    });
    return allAssets;
  };

  const filteredAssets = getAllAssets().filter(asset => {
    const matchesSearch = asset.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         asset.name.toLowerCase().includes(searchTerm.toLowerCase());
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
                <SelectItem value="forex">💱 Forex</SelectItem>
                <SelectItem value="crypto">₿ Cryptocurrency</SelectItem>
                <SelectItem value="stocks">📈 Stocks</SelectItem>
                <SelectItem value="commodities">🥇 Commodities</SelectItem>
                <SelectItem value="indices">📊 Indices</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Category Cards */}
          {Object.keys(pocketOptionAssets).map(categoryKey => {
            const category = pocketOptionAssets[categoryKey];
            const categoryAssets = [...category.regular, ...category.otc];
            const selectedCount = categoryAssets.filter(asset => 
              localSelectedAssets.includes(`${asset.symbol}_${asset.market}`)
            ).length;
            
            if (activeCategory !== 'all' && activeCategory !== categoryKey) return null;

            return (
              <Card key={categoryKey} className="p-6 glass-dark border-slate-700/50">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <span className="text-2xl">{category.icon}</span>
                    <div>
                      <h4 className="text-white font-semibold text-lg">{category.name}</h4>
                      <p className="text-slate-400 text-sm">
                        {categoryAssets.length} assets • {selectedCount} selected
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
                <div className="mb-6">
                  <h5 className="text-emerald-400 font-medium mb-3 flex items-center">
                    <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2"></span>
                    Regular Exchange
                  </h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {category.regular.map(asset => {
                      const assetId = `${asset.symbol}_${asset.market}`;
                      const isSelected = localSelectedAssets.includes(assetId);
                      
                      return (
                        <div
                          key={assetId}
                          onClick={() => handleAssetToggle(asset)}
                          className={`p-3 rounded-lg border cursor-pointer transition-all duration-200 ${
                            isSelected
                              ? 'border-emerald-500/50 bg-emerald-500/10'
                              : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-white font-medium">{asset.symbol}</p>
                              <p className="text-slate-400 text-xs">{asset.name}</p>
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

                {/* OTC Market Assets */}
                <div>
                  <h5 className="text-blue-400 font-medium mb-3 flex items-center">
                    <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
                    OTC Market (24/7)
                  </h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {category.otc.map(asset => {
                      const assetId = `${asset.symbol}_${asset.market}`;
                      const isSelected = localSelectedAssets.includes(assetId);
                      
                      return (
                        <div
                          key={assetId}
                          onClick={() => handleAssetToggle(asset)}
                          className={`p-3 rounded-lg border cursor-pointer transition-all duration-200 ${
                            isSelected
                              ? 'border-blue-500/50 bg-blue-500/10'
                              : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-white font-medium">{asset.symbol}</p>
                              <p className="text-slate-400 text-xs">{asset.name}</p>
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