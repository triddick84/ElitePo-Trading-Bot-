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
 * - Bridge Script Guide
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Bridge Script Guide Component
const BridgeScriptGuide = ({ isOpen, onClose }) => {
  const [bridgeScript, setBridgeScript] = useState('');
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // Fetch the bridge script
      axios.get(`${API}/bridge/script`)
        .then(res => setBridgeScript(res.data.script || ''))
        .catch(() => setBridgeScript('// Error loading script'));
    }
  }, [isOpen]);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(bridgeScript);
      setIsCopied(true);
      toast.success('✅ Script copied to clipboard!');
      setTimeout(() => setIsCopied(false), 3000);
    } catch (err) {
      toast.error('❌ Failed to copy script');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden border border-slate-700 shadow-2xl">
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-900/50 to-blue-900/50 p-6 border-b border-slate-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                <span className="text-3xl">📋</span>
                Bridge Script Guide
              </h2>
              <p className="text-slate-400 mt-1">Connect your Pocket Option browser to the trading bot</p>
            </div>
            <Button onClick={onClose} variant="ghost" className="text-slate-400 hover:text-white">
              ✕
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          {/* What is the Bridge Script */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              <span>🤔</span> What is the Bridge Script?
            </h3>
            <p className="text-slate-300 leading-relaxed">
              The Bridge Script is a JavaScript code that runs in your browser's console while you're on the 
              Pocket Option website. It captures real-time market data and your trading session information, 
              then sends it to our trading bot for automated signal execution.
            </p>
          </div>

          {/* Step by Step Guide */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>📝</span> Step-by-Step Instructions
            </h3>
            
            <div className="space-y-4">
              {/* Step 1 */}
              <div className="flex gap-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="flex-shrink-0 w-10 h-10 bg-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                  1
                </div>
                <div>
                  <h4 className="text-white font-medium mb-1">Open Pocket Option</h4>
                  <p className="text-slate-400 text-sm">
                    Go to <span className="text-emerald-400 font-mono">pocketoption.com</span> or{' '}
                    <span className="text-emerald-400 font-mono">po.trade</span> and log into your account.
                    Make sure you're on the trading page where you can see the charts.
                  </p>
                </div>
              </div>

              {/* Step 2 */}
              <div className="flex gap-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="flex-shrink-0 w-10 h-10 bg-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                  2
                </div>
                <div>
                  <h4 className="text-white font-medium mb-1">Open Developer Console</h4>
                  <p className="text-slate-400 text-sm mb-2">
                    Press the keyboard shortcut to open the browser's developer console:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <span className="px-3 py-1 bg-slate-700 rounded text-xs text-white">
                      <strong>Windows/Linux:</strong> F12 or Ctrl + Shift + J
                    </span>
                    <span className="px-3 py-1 bg-slate-700 rounded text-xs text-white">
                      <strong>Mac:</strong> Cmd + Option + J
                    </span>
                  </div>
                </div>
              </div>

              {/* Step 3 */}
              <div className="flex gap-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="flex-shrink-0 w-10 h-10 bg-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                  3
                </div>
                <div>
                  <h4 className="text-white font-medium mb-1">Go to Console Tab</h4>
                  <p className="text-slate-400 text-sm">
                    In the Developer Tools window, click on the <span className="text-emerald-400 font-semibold">"Console"</span> tab.
                    This is where you'll paste the bridge script.
                  </p>
                </div>
              </div>

              {/* Step 4 */}
              <div className="flex gap-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="flex-shrink-0 w-10 h-10 bg-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                  4
                </div>
                <div>
                  <h4 className="text-white font-medium mb-1">Copy the Bridge Script</h4>
                  <p className="text-slate-400 text-sm mb-2">
                    Click the button below to copy the entire bridge script to your clipboard:
                  </p>
                  <Button 
                    onClick={copyToClipboard}
                    className={`${isCopied ? 'bg-emerald-600' : 'bg-purple-600 hover:bg-purple-700'}`}
                  >
                    {isCopied ? '✅ Copied!' : '📋 Copy Bridge Script'}
                  </Button>
                </div>
              </div>

              {/* Step 5 */}
              <div className="flex gap-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="flex-shrink-0 w-10 h-10 bg-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                  5
                </div>
                <div>
                  <h4 className="text-white font-medium mb-1">Paste and Run</h4>
                  <p className="text-slate-400 text-sm">
                    Paste the script into the Console (Ctrl+V or Cmd+V) and press <span className="text-emerald-400 font-semibold">Enter</span> to run it.
                    You should see green messages confirming the bridge is active.
                  </p>
                </div>
              </div>

              {/* Step 6 */}
              <div className="flex gap-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <div className="flex-shrink-0 w-10 h-10 bg-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                  6
                </div>
                <div>
                  <h4 className="text-white font-medium mb-1">Verify Connection</h4>
                  <p className="text-slate-400 text-sm">
                    Come back to this page and check the <span className="text-emerald-400 font-semibold">"Browser Bridge"</span> status. 
                    It should change from "Inactive" to "Active" with a green indicator.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Important Notes */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              <span>⚠️</span> Important Notes
            </h3>
            <div className="space-y-3">
              <div className="flex items-start gap-3 p-3 bg-yellow-900/20 border border-yellow-500/30 rounded-lg">
                <span className="text-yellow-400 text-xl">💡</span>
                <p className="text-yellow-200 text-sm">
                  <strong>Keep the tab open:</strong> The bridge only works while the Pocket Option tab is open and active.
                  Don't close or minimize it.
                </p>
              </div>
              <div className="flex items-start gap-3 p-3 bg-blue-900/20 border border-blue-500/30 rounded-lg">
                <span className="text-blue-400 text-xl">🔄</span>
                <p className="text-blue-200 text-sm">
                  <strong>Re-run after refresh:</strong> If you refresh the Pocket Option page, you'll need to paste 
                  and run the script again.
                </p>
              </div>
              <div className="flex items-start gap-3 p-3 bg-emerald-900/20 border border-emerald-500/30 rounded-lg">
                <span className="text-emerald-400 text-xl">🔐</span>
                <p className="text-emerald-200 text-sm">
                  <strong>SSID Capture:</strong> The script automatically captures your session ID (SSID) and sends it
                  to enable auto-trading features.
                </p>
              </div>
              <div className="flex items-start gap-3 p-3 bg-purple-900/20 border border-purple-500/30 rounded-lg">
                <span className="text-purple-400 text-xl">📊</span>
                <p className="text-purple-200 text-sm">
                  <strong>Real-time data:</strong> Once connected, you'll receive live price data and can execute trades
                  automatically based on AI signals.
                </p>
              </div>
            </div>
          </div>

          {/* Troubleshooting */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              <span>🔧</span> Troubleshooting
            </h3>
            <div className="space-y-3">
              <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <h4 className="text-white font-medium mb-2">❓ Script shows error when pasting?</h4>
                <p className="text-slate-400 text-sm">
                  Some browsers block pasting in console. Type <code className="bg-slate-700 px-1 rounded">allow pasting</code> first,
                  then try pasting again.
                </p>
              </div>
              <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <h4 className="text-white font-medium mb-2">❓ Bridge not connecting?</h4>
                <p className="text-slate-400 text-sm">
                  Make sure you're on the actual trading page (not the homepage). Try refreshing Pocket Option
                  and running the script again.
                </p>
              </div>
              <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                <h4 className="text-white font-medium mb-2">❓ Not receiving market data?</h4>
                <p className="text-slate-400 text-sm">
                  Navigate to different trading pairs on Pocket Option. The script hooks into WebSocket connections
                  as they're created.
                </p>
              </div>
            </div>
          </div>

          {/* Script Preview */}
          <div>
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              <span>👁️</span> Script Preview
            </h3>
            <div className="bg-slate-950 rounded-lg p-4 border border-slate-700 max-h-48 overflow-y-auto">
              <pre className="text-xs text-slate-400 font-mono whitespace-pre-wrap">
                {bridgeScript.substring(0, 500)}...
              </pre>
            </div>
            <p className="text-xs text-slate-500 mt-2 text-center">
              Showing first 500 characters. Full script is ~15KB.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-700 bg-slate-800/50 flex items-center justify-between">
          <p className="text-sm text-slate-400">
            Need help? Check the console for detailed logs after running the script.
          </p>
          <div className="flex gap-3">
            <Button onClick={copyToClipboard} className="bg-purple-600 hover:bg-purple-700">
              {isCopied ? '✅ Copied!' : '📋 Copy Script'}
            </Button>
            <Button onClick={onClose} variant="outline" className="border-slate-600">
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const PocketOptionPage = () => {
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
  
  // Guide modal state
  const [showGuide, setShowGuide] = useState(false);

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
    const connectionState = autoTradeStatus?.connection_state || 'disconnected';
    const isConnected = autoTradeStatus?.is_connected || false;
    const isRunning = autoTradeStatus?.is_running || false;
    const reconnectAttempts = autoTradeStatus?.reconnect_attempts || 0;
    
    switch (connectionState) {
      case 'authenticated':
        return { color: 'text-emerald-400', bg: 'bg-emerald-500', text: 'Connected', icon: '🟢', pulse: false };
      case 'connected':
      case 'authenticating':
        return { color: 'text-blue-400', bg: 'bg-blue-500', text: 'Authenticating...', icon: '🔵', pulse: true };
      case 'connecting':
        return { color: 'text-yellow-400', bg: 'bg-yellow-500', text: 'Connecting...', icon: '🟡', pulse: true };
      case 'reconnecting':
        return { color: 'text-orange-400', bg: 'bg-orange-500', text: `Reconnecting (${reconnectAttempts})...`, icon: '🟠', pulse: true };
      case 'error':
        return { color: 'text-red-400', bg: 'bg-red-500', text: 'Connection Error', icon: '🔴', pulse: false };
      default:
        if (isConnected && isRunning) {
          return { color: 'text-emerald-400', bg: 'bg-emerald-500', text: 'Connected', icon: '🟢', pulse: false };
        }
        return { color: 'text-red-400', bg: 'bg-red-500', text: 'Disconnected', icon: '🔴', pulse: false };
    }
  };

  const connectionStatus = getConnectionStatus();
  const isDemo = autoTradeStatus?.is_demo ?? true;
  const balance = autoTradeStatus?.balance || 0;
  const connectionState = autoTradeStatus?.connection_state || 'disconnected';

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
            Pocket Option Integration
          </h1>
          <p className="text-slate-400 mt-1">Elite Pocket Option Trading Bot v8.4 - AI-Powered Automation</p>
        </div>
        <Button 
          onClick={fetchAllStatus}
          variant="outline"
          className="border-slate-600 hover:bg-slate-700"
        >
          🔄 Refresh
        </Button>
      </div>

      {/* Integration Overview Card */}
      <Card className="bg-gradient-to-r from-purple-900/30 to-indigo-900/30 border-purple-500/50 p-6">
        <div className="grid md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="text-4xl mb-2">🤖</div>
            <h3 className="text-white font-bold">Tampermonkey Script</h3>
            <p className="text-slate-400 text-sm mt-1">Auto-trades directly in your browser on Pocket Option</p>
          </div>
          <div className="text-center">
            <div className="text-4xl mb-2">🧠</div>
            <h3 className="text-white font-bold">AI Signal Engine</h3>
            <p className="text-slate-400 text-sm mt-1">XGBoost + LSTM + PPO ensemble for high-accuracy signals</p>
          </div>
          <div className="text-center">
            <div className="text-4xl mb-2">📊</div>
            <h3 className="text-white font-bold">Smart Auto-Invert</h3>
            <p className="text-slate-400 text-sm mt-1">Momentum-aware inversion based on RSI/EMA + backend analysis</p>
          </div>
        </div>
      </Card>

      {/* Connection Status Banner */}
      <Card className={`p-6 ${isDemo ? 'bg-gradient-to-r from-blue-900/50 to-purple-900/50 border-blue-500/50' : 'bg-gradient-to-r from-emerald-900/50 to-teal-900/50 border-emerald-500/50'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className={`w-20 h-20 rounded-full ${connectionStatus.bg}/20 flex items-center justify-center ${connectionStatus.pulse ? 'animate-pulse' : ''}`}>
              <span className="text-5xl">{connectionStatus.icon}</span>
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className={`text-2xl font-bold ${connectionStatus.color} ${connectionStatus.pulse ? 'animate-pulse' : ''}`}>
                  {connectionStatus.text}
                </h2>
                <span className={`px-3 py-1 rounded-full text-sm font-semibold ${isDemo ? 'bg-blue-600 text-blue-100' : 'bg-emerald-600 text-emerald-100'}`}>
                  {isDemo ? '🎮 DEMO' : '💰 REAL'}
                </span>
              </div>
              <p className="text-slate-400 mt-1">
                Pocket Option Trading Account
                {connectionState && connectionState !== 'disconnected' && (
                  <span className="ml-2 text-xs">({connectionState})</span>
                )}
              </p>
              {balance > 0 && (
                <p className="text-2xl font-bold text-white mt-2">
                  💵 ${balance.toFixed(2)}
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-2">
            {autoTradeStatus?.is_running || connectionState === 'reconnecting' ? (
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
                disabled={isConnecting || connectionState === 'connecting'}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                {isConnecting || connectionState === 'connecting' ? '⏳ Connecting...' : '🔗 Connect'}
              </Button>
            )}
            {connectionState === 'reconnecting' && (
              <p className="text-xs text-orange-400 text-center">
                Auto-reconnecting...
              </p>
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
                    <p className="text-xs text-slate-400">
                      {connectionState === 'reconnecting' ? 'Reconnecting...' : 'Direct API connection'}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={
                    connectionState === 'authenticated' ? 'text-emerald-400' :
                    connectionState === 'reconnecting' ? 'text-orange-400 animate-pulse' :
                    connectionState === 'connecting' ? 'text-yellow-400 animate-pulse' :
                    'text-red-400'
                  }>
                    {connectionState === 'authenticated' ? '🟢 Connected' :
                     connectionState === 'reconnecting' ? '🟠 Reconnecting' :
                     connectionState === 'connecting' ? '🟡 Connecting' :
                     '🔴 Offline'}
                  </span>
                  {autoTradeStatus?.reconnect_attempts > 0 && (
                    <p className="text-xs text-orange-400">
                      Attempt {autoTradeStatus.reconnect_attempts}
                    </p>
                  )}
                </div>
              </div>
              
              {/* Connection Tips */}
              {connectionState === 'reconnecting' && (
                <div className="p-3 bg-orange-900/20 border border-orange-500/30 rounded-lg">
                  <p className="text-xs text-orange-300">
                    💡 <strong>Tip:</strong> For best stability, use the <strong>Browser Bridge</strong> method. 
                    Click "How to Use Bridge Script" below.
                  </p>
                </div>
              )}
              
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
                onClick={() => setShowGuide(true)}
                className="w-full bg-purple-600 hover:bg-purple-700"
              >
                📖 How to Use Bridge Script
              </Button>
              <Button 
                onClick={() => {
                  window.open(`${API}/bridge/script`, '_blank');
                  toast.success('📋 Script opened in new tab!');
                }}
                variant="outline"
                className="w-full border-slate-600 hover:bg-slate-700"
              >
                📥 Open Script in New Tab
              </Button>
              <p className="text-xs text-slate-500 text-center">
                Click "How to Use" for step-by-step instructions
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
              onClick={() => setShowGuide(true)}
              variant="outline"
              className="border-slate-600"
            >
              📖 Setup Guide
            </Button>
          </div>
        </div>
      </Card>

      {/* Bridge Script Guide Modal */}
      <BridgeScriptGuide isOpen={showGuide} onClose={() => setShowGuide(false)} />
    </div>
  );
};

export default PocketOptionPage;
