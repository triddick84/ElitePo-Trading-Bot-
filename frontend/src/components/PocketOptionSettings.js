/**
 * Pocket Option Integration Settings Page
 * 
 * Features:
 * - Connection status display (WebSocket, Bridge, Auto-Trade)
 * - Account type indicator (Demo/Real)
 * - Balance display
 * - Trade history and statistics
 * - SSID management
 * - Trading parameters configuration
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PocketOptionSettings = () => {
  // Connection states
  const [autoTradeStatus, setAutoTradeStatus] = useState(null);
  const [bridgeStatus, setBridgeStatus] = useState(null);
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [ssidStatus, setSsidStatus] = useState(null);
  
  // Trade data
  const [tradeHistory, setTradeHistory] = useState([]);
  const [tradeStats, setTradeStats] = useState(null);
  
  // Settings
  const [tradeAmount, setTradeAmount] = useState(1.0);
  const [minProbability, setMinProbability] = useState(75.0);
  const [maxTradesPerMinute, setMaxTradesPerMinute] = useState(5);
  const [autoTradeEnabled, setAutoTradeEnabled] = useState(false);
  
  // Loading states
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Fetch all status data
  const fetchAllStatus = useCallback(async () => {
    try {
      const [autoTradeRes, bridgeRes, telegramRes, ssidRes, historyRes] = await Promise.all([
        axios.get(`${API}/auto-trade/status`).catch(() => ({ data: null })),
        axios.get(`${API}/bridge/status`).catch(() => ({ data: null })),
        axios.get(`${API}/telegram/status`).catch(() => ({ data: null })),
        axios.get(`${API}/ssid/status`).catch(() => ({ data: null })),
        axios.get(`${API}/auto-trade/history?limit=20`).catch(() => ({ data: null }))
      ]);

      if (autoTradeRes.data) {
        setAutoTradeStatus(autoTradeRes.data);
        setTradeAmount(autoTradeRes.data.default_amount || 1.0);
        setMinProbability(autoTradeRes.data.min_probability || 75.0);
        setMaxTradesPerMinute(autoTradeRes.data.max_trades_per_minute || 5);
        setAutoTradeEnabled(autoTradeRes.data.is_auto_trade_enabled || false);
        setTradeStats(autoTradeRes.data.stats);
      }
      
      if (bridgeRes.data) setBridgeStatus(bridgeRes.data);
      if (telegramRes.data) setTelegramStatus(telegramRes.data);
      if (ssidRes.data) setSsidStatus(ssidRes.data);
      if (historyRes.data) {
        setTradeHistory(historyRes.data.trades || []);
        if (historyRes.data.stats) setTradeStats(historyRes.data.stats);
      }
      
    } catch (error) {
      console.error('Error fetching status:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllStatus();
    // Refresh every 10 seconds
    const interval = setInterval(fetchAllStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchAllStatus]);

  // Connect to Pocket Option
  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      const response = await axios.post(`${API}/auto-trade/connect`);
      if (response.data.success) {
        toast.success('✅ Connected to Pocket Option!');
        await fetchAllStatus();
      } else {
        toast.error(response.data.message || '❌ Connection failed');
      }
    } catch (error) {
      toast.error('❌ Failed to connect');
    } finally {
      setIsConnecting(false);
    }
  };

  // Disconnect from Pocket Option
  const handleDisconnect = async () => {
    try {
      const response = await axios.post(`${API}/auto-trade/disconnect`);
      if (response.data.success) {
        toast.success('✅ Disconnected');
        await fetchAllStatus();
      }
    } catch (error) {
      toast.error('❌ Failed to disconnect');
    }
  };

  // Toggle auto trading
  const handleToggleAutoTrade = async () => {
    try {
      const response = await axios.post(`${API}/auto-trade/enable?enabled=${!autoTradeEnabled}`);
      if (response.data.success) {
        setAutoTradeEnabled(!autoTradeEnabled);
        toast.success(`✅ Auto-trade ${!autoTradeEnabled ? 'enabled' : 'disabled'}`);
      }
    } catch (error) {
      toast.error('❌ Failed to toggle auto-trade');
    }
  };

  // Update trading settings
  const handleUpdateSettings = async () => {
    try {
      const response = await axios.put(`${API}/auto-trade/settings`, null, {
        params: {
          amount: tradeAmount,
          min_probability: minProbability,
          max_trades_per_minute: maxTradesPerMinute
        }
      });
      if (response.data.success) {
        toast.success('✅ Settings updated');
      }
    } catch (error) {
      toast.error('❌ Failed to update settings');
    }
  };

  // Refresh SSID
  const handleRefreshSSID = async () => {
    setIsRefreshing(true);
    try {
      const response = await axios.post(`${API}/ssid/refresh-now`);
      if (response.data.success) {
        toast.success('✅ SSID refreshed');
        await fetchAllStatus();
      } else {
        toast.error(response.data.message || '❌ Refresh failed');
      }
    } catch (error) {
      toast.error('❌ Failed to refresh SSID');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Test Telegram
  const handleTestTelegram = async () => {
    try {
      const response = await axios.post(`${API}/telegram/test`);
      if (response.data.success) {
        toast.success('✅ Test notification sent to Telegram!');
      } else {
        toast.error(response.data.message || '❌ Telegram test failed');
      }
    } catch (error) {
      toast.error('❌ Failed to send test notification');
    }
  };

  // Get connection status color and text
  const getConnectionStatus = () => {
    const isConnected = autoTradeStatus?.is_connected || false;
    const isRunning = autoTradeStatus?.is_running || false;
    
    if (isConnected && isRunning) {
      return { color: 'text-emerald-400', bg: 'bg-emerald-500', text: 'Connected', icon: '🟢' };
    } else if (isRunning) {
      return { color: 'text-yellow-400', bg: 'bg-yellow-500', text: 'Connecting...', icon: '🟡' };
    }
    return { color: 'text-red-400', bg: 'bg-red-500', text: 'Disconnected', icon: '🔴' };
  };

  const connectionStatus = getConnectionStatus();
  const isDemo = autoTradeStatus?.is_demo ?? true;
  const balance = autoTradeStatus?.balance || 0;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <span className="text-4xl">⚙️</span>
            Pocket Option Settings
          </h1>
          <p className="text-slate-400 mt-1">Manage your trading connection and parameters</p>
        </div>
        <Button 
          onClick={fetchAllStatus}
          variant="outline"
          className="border-slate-600 hover:bg-slate-700"
        >
          🔄 Refresh
        </Button>
      </div>

      {/* Connection Status Banner */}
      <Card className={`p-6 ${isDemo ? 'bg-gradient-to-r from-blue-900/50 to-purple-900/50 border-blue-500/50' : 'bg-gradient-to-r from-emerald-900/50 to-teal-900/50 border-emerald-500/50'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className={`w-20 h-20 rounded-full ${connectionStatus.bg}/20 flex items-center justify-center`}>
              <span className="text-5xl">{connectionStatus.icon}</span>
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className={`text-2xl font-bold ${connectionStatus.color}`}>
                  {connectionStatus.text}
                </h2>
                <span className={`px-3 py-1 rounded-full text-sm font-semibold ${isDemo ? 'bg-blue-600 text-blue-100' : 'bg-emerald-600 text-emerald-100'}`}>
                  {isDemo ? '🎮 DEMO' : '💰 REAL'}
                </span>
              </div>
              <p className="text-slate-400 mt-1">
                Pocket Option Trading Account
              </p>
              {balance > 0 && (
                <p className="text-2xl font-bold text-white mt-2">
                  💵 ${balance.toFixed(2)}
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-3">
            {autoTradeStatus?.is_running ? (
              <Button 
                onClick={handleDisconnect}
                variant="destructive"
                className="bg-red-600 hover:bg-red-700"
              >
                🔌 Disconnect
              </Button>
            ) : (
              <Button 
                onClick={handleConnect}
                disabled={isConnecting}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                {isConnecting ? '⏳ Connecting...' : '🔗 Connect'}
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column - Connection Details */}
        <div className="space-y-6">
          
          {/* Auto-Trade Control */}
          <Card className="p-5 glass-dark border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>🤖</span> Auto-Trade Control
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <div>
                  <p className="text-white font-medium">Auto-Trading</p>
                  <p className="text-xs text-slate-400">Execute signals automatically</p>
                </div>
                <Button
                  onClick={handleToggleAutoTrade}
                  className={autoTradeEnabled ? 'bg-emerald-600' : 'bg-slate-600'}
                  disabled={!autoTradeStatus?.is_running}
                >
                  {autoTradeEnabled ? '✅ ON' : '❌ OFF'}
                </Button>
              </div>
              
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <p className="text-sm text-slate-400 mb-2">Trade Amount ($)</p>
                <div className="flex items-center gap-3">
                  <Slider
                    value={[tradeAmount]}
                    onValueChange={(v) => setTradeAmount(v[0])}
                    min={1}
                    max={100}
                    step={1}
                    className="flex-1"
                  />
                  <span className="text-white font-bold w-16 text-right">${tradeAmount}</span>
                </div>
              </div>
              
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <p className="text-sm text-slate-400 mb-2">Min Probability (%)</p>
                <div className="flex items-center gap-3">
                  <Slider
                    value={[minProbability]}
                    onValueChange={(v) => setMinProbability(v[0])}
                    min={50}
                    max={95}
                    step={5}
                    className="flex-1"
                  />
                  <span className="text-white font-bold w-16 text-right">{minProbability}%</span>
                </div>
              </div>
              
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <p className="text-sm text-slate-400 mb-2">Max Trades/Minute</p>
                <div className="flex items-center gap-3">
                  <Slider
                    value={[maxTradesPerMinute]}
                    onValueChange={(v) => setMaxTradesPerMinute(v[0])}
                    min={1}
                    max={20}
                    step={1}
                    className="flex-1"
                  />
                  <span className="text-white font-bold w-16 text-right">{maxTradesPerMinute}</span>
                </div>
              </div>
              
              <Button 
                onClick={handleUpdateSettings}
                className="w-full bg-blue-600 hover:bg-blue-700"
              >
                💾 Save Settings
              </Button>
            </div>
          </Card>

          {/* SSID Status */}
          <Card className="p-5 glass-dark border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>🔑</span> SSID Status
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Status</span>
                <span className={ssidStatus?.ssid_status?.is_valid ? 'text-emerald-400' : 'text-red-400'}>
                  {ssidStatus?.ssid_status?.is_valid ? '✅ Valid' : '❌ Invalid'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Preview</span>
                <span className="text-white font-mono text-sm">
                  {ssidStatus?.ssid_status?.ssid_preview || 'N/A'}
                </span>
              </div>
              {ssidStatus?.ssid_status?.time_until_expiry_minutes !== undefined && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Expires In</span>
                  <span className={ssidStatus.ssid_status.time_until_expiry_minutes < 15 ? 'text-yellow-400' : 'text-emerald-400'}>
                    {Math.round(ssidStatus.ssid_status.time_until_expiry_minutes)} min
                  </span>
                </div>
              )}
              <Button 
                onClick={handleRefreshSSID}
                disabled={isRefreshing}
                variant="outline"
                className="w-full border-slate-600 hover:bg-slate-700"
              >
                {isRefreshing ? '⏳ Refreshing...' : '🔄 Refresh SSID'}
              </Button>
            </div>
          </Card>
        </div>

        {/* Middle Column - Service Status */}
        <div className="space-y-6">
          
          {/* Services Status */}
          <Card className="p-5 glass-dark border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>📡</span> Services Status
            </h3>
            <div className="space-y-3">
              
              {/* WebSocket Connection */}
              <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">🌐</span>
                  <div>
                    <p className="text-white font-medium">WebSocket</p>
                    <p className="text-xs text-slate-400">Direct API connection</p>
                  </div>
                </div>
                <span className={autoTradeStatus?.is_connected ? 'text-emerald-400' : 'text-red-400'}>
                  {autoTradeStatus?.is_connected ? '🟢 Connected' : '🔴 Offline'}
                </span>
              </div>
              
              {/* Bridge Connection */}
              <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">🌉</span>
                  <div>
                    <p className="text-white font-medium">Browser Bridge</p>
                    <p className="text-xs text-slate-400">Console script connection</p>
                  </div>
                </div>
                <span className={bridgeStatus?.connected ? 'text-emerald-400' : 'text-slate-400'}>
                  {bridgeStatus?.connected ? '🟢 Active' : '⚪ Inactive'}
                </span>
              </div>
              
              {/* Telegram */}
              <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">📱</span>
                  <div>
                    <p className="text-white font-medium">Telegram</p>
                    <p className="text-xs text-slate-400">@ElitePocket_bot</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={telegramStatus?.configured ? 'text-emerald-400' : 'text-red-400'}>
                    {telegramStatus?.configured ? '🟢' : '🔴'}
                  </span>
                  <Button
                    onClick={handleTestTelegram}
                    size="sm"
                    variant="outline"
                    className="border-slate-600 text-xs"
                  >
                    Test
                  </Button>
                </div>
              </div>
              
              {/* Auto-Trade Service */}
              <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">🤖</span>
                  <div>
                    <p className="text-white font-medium">Auto-Trade</p>
                    <p className="text-xs text-slate-400">Signal execution</p>
                  </div>
                </div>
                <span className={autoTradeStatus?.is_auto_trade_enabled ? 'text-emerald-400' : 'text-slate-400'}>
                  {autoTradeStatus?.is_auto_trade_enabled ? '🟢 Enabled' : '⚪ Disabled'}
                </span>
              </div>
            </div>
          </Card>

          {/* Trading Statistics */}
          <Card className="p-5 glass-dark border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>📊</span> Trading Statistics
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-4 bg-slate-800/50 rounded-lg">
                <p className="text-3xl font-bold text-white">{tradeStats?.total_trades || 0}</p>
                <p className="text-xs text-slate-400">Total Trades</p>
              </div>
              <div className="text-center p-4 bg-emerald-900/30 rounded-lg border border-emerald-500/30">
                <p className="text-3xl font-bold text-emerald-400">{tradeStats?.wins || 0}</p>
                <p className="text-xs text-slate-400">Wins</p>
              </div>
              <div className="text-center p-4 bg-red-900/30 rounded-lg border border-red-500/30">
                <p className="text-3xl font-bold text-red-400">{tradeStats?.losses || 0}</p>
                <p className="text-xs text-slate-400">Losses</p>
              </div>
              <div className="text-center p-4 bg-blue-900/30 rounded-lg border border-blue-500/30">
                <p className="text-3xl font-bold text-blue-400">{tradeStats?.win_rate || '0%'}</p>
                <p className="text-xs text-slate-400">Win Rate</p>
              </div>
            </div>
            <div className="mt-4 p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Total Profit</span>
                <span className={`text-2xl font-bold ${(tradeStats?.total_profit || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  ${(tradeStats?.total_profit || 0).toFixed(2)}
                </span>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column - Trade History */}
        <div className="space-y-6">
          <Card className="p-5 glass-dark border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>📜</span> Recent Trades
            </h3>
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {tradeHistory.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <p className="text-4xl mb-2">📭</p>
                  <p>No trades yet</p>
                  <p className="text-xs mt-1">Trades will appear here when executed</p>
                </div>
              ) : (
                tradeHistory.map((trade, index) => (
                  <div 
                    key={trade.id || index}
                    className={`p-3 rounded-lg border ${
                      trade.status === 'win' 
                        ? 'bg-emerald-900/20 border-emerald-500/30' 
                        : trade.status === 'lose'
                        ? 'bg-red-900/20 border-red-500/30'
                        : 'bg-slate-800/50 border-slate-600/30'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`text-lg ${trade.direction === 'call' ? 'text-emerald-400' : 'text-red-400'}`}>
                          {trade.direction === 'call' ? '📈' : '📉'}
                        </span>
                        <div>
                          <p className="text-white font-medium text-sm">{trade.symbol}</p>
                          <p className="text-xs text-slate-400">
                            {trade.direction?.toUpperCase()} • ${trade.amount}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold ${
                          trade.status === 'win' ? 'text-emerald-400' : 
                          trade.status === 'lose' ? 'text-red-400' : 'text-yellow-400'
                        }`}>
                          {trade.status === 'win' ? `+$${trade.profit?.toFixed(2)}` :
                           trade.status === 'lose' ? `-$${Math.abs(trade.profit || 0).toFixed(2)}` :
                           '⏳ Pending'}
                        </p>
                        <p className="text-xs text-slate-500">
                          {trade.strategy || 'Manual'}
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* Bridge Script Info */}
          <Card className="p-5 glass-dark border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>📋</span> Bridge Script
            </h3>
            <div className="space-y-3">
              <p className="text-sm text-slate-400">
                Use the bridge script to connect directly from your browser on Pocket Option.
              </p>
              <div className="p-3 bg-slate-800/50 rounded-lg">
                <p className="text-xs text-slate-400 mb-2">Messages Received</p>
                <p className="text-xl font-bold text-white">{bridgeStatus?.message_count || 0}</p>
              </div>
              <Button 
                onClick={() => {
                  window.open(`${API}/bridge/script`, '_blank');
                  toast.success('📋 Script opened in new tab!');
                }}
                className="w-full bg-purple-600 hover:bg-purple-700"
              >
                📥 Get Bridge Script
              </Button>
              <p className="text-xs text-slate-500 text-center">
                Paste the script in Pocket Option's browser console
              </p>
            </div>
          </Card>
        </div>
      </div>

      {/* Account Details Footer */}
      <Card className="p-5 glass-dark border-slate-700">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-6">
            <div>
              <p className="text-xs text-slate-400">Account Type</p>
              <p className={`text-lg font-bold ${isDemo ? 'text-blue-400' : 'text-emerald-400'}`}>
                {isDemo ? '🎮 Demo Account' : '💰 Real Account'}
              </p>
            </div>
            <div className="h-10 w-px bg-slate-700"></div>
            <div>
              <p className="text-xs text-slate-400">Balance</p>
              <p className="text-lg font-bold text-white">${balance.toFixed(2)}</p>
            </div>
            <div className="h-10 w-px bg-slate-700"></div>
            <div>
              <p className="text-xs text-slate-400">Connection</p>
              <p className={`text-lg font-bold ${connectionStatus.color}`}>
                {connectionStatus.icon} {connectionStatus.text}
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={() => toast.info('ℹ️ Use bridge script for best results')}
              variant="outline"
              className="border-slate-600"
            >
              ❓ Help
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default PocketOptionSettings;
