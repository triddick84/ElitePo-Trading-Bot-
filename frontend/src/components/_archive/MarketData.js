import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MarketData = () => {
  const [marketData, setMarketData] = useState(null);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchMarketData();
    const interval = setInterval(fetchMarketData, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchMarketData = async () => {
    try {
      const response = await axios.get(`${API}/market/data`);
      setMarketData(response.data);
    } catch (error) {
      console.error('Error fetching market data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const formatPrice = (price) => {
    return parseFloat(price).toFixed(4);
  };

  const formatPercentage = (percentage) => {
    const value = parseFloat(percentage);
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const getChangeColor = (change) => {
    if (change > 0) return 'text-green-400';
    if (change < 0) return 'text-red-400';
    return 'text-slate-400';
  };

  const getAssetIcon = (assetType) => {
    const icons = {
      forex: '💱',
      crypto: '₿',
      stocks: '📈',
      commodities: '🥇',
      otc: '🏛️'
    };
    return icons[assetType] || '📊';
  };

  const AssetCard = ({ asset, assetType }) => (
    <Card 
      className={`p-4 glass-dark border-slate-700/50 cursor-pointer transition-all duration-200 hover:border-emerald-500/30 hover:bg-emerald-500/5 ${
        selectedAsset?.symbol === asset.symbol ? 'border-emerald-500/50 bg-emerald-500/10' : ''
      }`}
      onClick={() => setSelectedAsset({ ...asset, type: assetType })}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <span className="text-2xl">{getAssetIcon(assetType)}</span>
          <div>
            <h4 className="text-white font-semibold">{asset.symbol}</h4>
            <p className="text-slate-400 text-sm capitalize">{assetType}</p>
          </div>
        </div>
        <Badge className="bg-slate-700/50 text-slate-300 border-slate-600">
          Live
        </Badge>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-slate-400 text-sm">Price</span>
          <span className="text-white font-bold text-lg">${formatPrice(asset.price)}</span>
        </div>
        
        <div className="flex items-center justify-between">
          <span className="text-slate-400 text-sm">Change</span>
          <span className={`font-medium ${getChangeColor(asset.change_percent)}`}>
            {formatPercentage(asset.change_percent)}
          </span>
        </div>

        {asset.volume && (
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-sm">Volume</span>
            <span className="text-slate-300 text-sm">
              {asset.volume.toLocaleString()}
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-700/50">
        <div className="text-xs text-slate-400">
          Bid: ${formatPrice(asset.bid || asset.price)}
        </div>
        <div className="text-xs text-slate-400">
          Ask: ${formatPrice(asset.ask || asset.price)}
        </div>
      </div>
    </Card>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        {[...Array(6)].map((_, i) => (
          <Card key={i} className="p-4 glass-dark border-slate-700/50">
            <div className="skeleton h-24 w-full rounded"></div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="market-data">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Market Data</h2>
          <p className="text-slate-400">Real-time market prices and trends across all asset classes</p>
        </div>
        <Button 
          onClick={fetchMarketData}
          className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
          data-testid="refresh-market-data"
        >
          🔄 Refresh
        </Button>
      </div>

      {marketData ? (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          {/* Asset Categories */}
          <div className="xl:col-span-3 space-y-6">
            {Object.entries(marketData).map(([assetType, assets]) => (
              <div key={assetType} className="space-y-4">
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">{getAssetIcon(assetType)}</span>
                  <h3 className="text-xl font-semibold text-white capitalize">
                    {assetType === 'otc' ? 'OTC Markets' : assetType}
                  </h3>
                  <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                    {assets.length} assets
                  </Badge>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid={`${assetType}-assets`}>
                  {assets.map((asset, index) => (
                    <AssetCard key={index} asset={asset} assetType={assetType} />
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Asset Details Sidebar */}
          <div className="xl:col-span-1">
            <Card className="p-6 glass-dark border-slate-700/50 sticky top-24">
              {selectedAsset ? (
                <div className="space-y-6" data-testid="asset-details">
                  <div className="text-center">
                    <span className="text-4xl">{getAssetIcon(selectedAsset.type)}</span>
                    <h3 className="text-xl font-bold text-white mt-2">{selectedAsset.symbol}</h3>
                    <p className="text-slate-400 capitalize">{selectedAsset.type}</p>
                  </div>

                  <div className="space-y-4">
                    <div className="text-center p-4 bg-slate-800/50 rounded-lg">
                      <p className="text-slate-400 text-sm mb-1">Current Price</p>
                      <p className="text-3xl font-bold text-white">${formatPrice(selectedAsset.price)}</p>
                      <p className={`text-lg font-medium ${getChangeColor(selectedAsset.change_percent)}`}>
                        {formatPercentage(selectedAsset.change_percent)}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                        <p className="text-slate-400 text-xs mb-1">Bid</p>
                        <p className="text-white font-medium">${formatPrice(selectedAsset.bid || selectedAsset.price)}</p>
                      </div>
                      <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                        <p className="text-slate-400 text-xs mb-1">Ask</p>
                        <p className="text-white font-medium">${formatPrice(selectedAsset.ask || selectedAsset.price)}</p>
                      </div>
                    </div>

                    {selectedAsset.volume && (
                      <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                        <p className="text-slate-400 text-xs mb-1">Volume</p>
                        <p className="text-white font-medium">{selectedAsset.volume.toLocaleString()}</p>
                      </div>
                    )}

                    <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                      <p className="text-slate-400 text-xs mb-1">Last Update</p>
                      <p className="text-white text-sm">
                        {new Date(selectedAsset.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-700/50">
                    <h4 className="text-white font-medium mb-3">Quick Analysis</h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Trend</span>
                        <span className={getChangeColor(selectedAsset.change_percent)}>
                          {selectedAsset.change_percent > 0 ? 'Bullish' : selectedAsset.change_percent < 0 ? 'Bearish' : 'Neutral'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Volatility</span>
                        <span className="text-slate-300">
                          {Math.abs(selectedAsset.change_percent) > 1 ? 'High' : 'Low'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <div className="text-4xl mb-4">📊</div>
                  <h3 className="text-lg font-semibold text-white mb-2">Select an Asset</h3>
                  <p className="text-slate-400 text-sm">
                    Click on any asset to view detailed information and analysis
                  </p>
                </div>
              )}
            </Card>
          </div>
        </div>
      ) : (
        <Card className="p-12 glass-dark border-slate-700/50 text-center">
          <div className="text-6xl mb-4">📊</div>
          <h3 className="text-xl font-semibold text-white mb-2">No Market Data Available</h3>
          <p className="text-slate-400">
            Unable to fetch market data. Please check your connection and try again.
          </p>
        </Card>
      )}
    </div>
  );
};

export default MarketData;