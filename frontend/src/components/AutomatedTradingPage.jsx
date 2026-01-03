/**
 * Automated Trading Page
 * 
 * Centralized page for all automated trading settings:
 * - Bot Controls (Start/Stop)
 * - Pocket Option Connection
 * - Money Management (Fixed, Martingale, Anti-Martingale, % of Balance)
 * - Trade Execution Settings
 * - Active Orders & Trade History
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Alert, AlertDescription } from './ui/alert';
import { toast } from 'sonner';
import { 
  Play, Square, Settings, TrendingUp, TrendingDown, DollarSign, 
  Activity, Zap, Shield, Target, RefreshCw, Wifi, WifiOff,
  ArrowUp, ArrowDown, BarChart3, Clock, AlertTriangle, CheckCircle
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Money Management Modes
const MONEY_MANAGEMENT_MODES = {
  FIXED: {
    id: 'fixed',
    name: 'Fixed Amount',
    description: 'Trade with a constant amount each time',
    icon: '💵'
  },
  MARTINGALE: {
    id: 'martingale',
    name: 'Martingale',
    description: 'Double stake after each loss to recover',
    icon: '📈'
  },
  ANTI_MARTINGALE: {
    id: 'anti_martingale',
    name: 'Anti-Martingale',
    description: 'Increase stake after wins, reset after loss',
    icon: '📉'
  },
  PERCENTAGE: {
    id: 'percentage',
    name: 'Percentage of Balance',
    description: 'Risk a percentage of your balance per trade',
    icon: '💰'
  },
  CUSTOM_MARTINGALE: {
    id: 'custom_martingale',
    name: 'Custom Martingale',
    description: 'Configure your own multiplier and step limits',
    icon: '⚙️'
  }
};

const AutomatedTradingPage = () => {
  // Connection State
  const [connectionStatus, setConnectionStatus] = useState({
    connected: false,
    balance: 0,
    account_type: 'demo',
    last_check: null
  });
  
  // Bot State
  const [botStatus, setBotStatus] = useState({
    is_running: false,
    auto_trade_enabled: false,
    trades_today: 0,
    wins: 0,
    losses: 0
  });
  
  // Trading Settings
  const [tradingSettings, setTradingSettings] = useState({
    auto_trade_enabled: false,
    min_confidence: 75,
    max_trades_per_hour: 10,
    max_trades_per_day: 50,
    cooldown_seconds: 30,
    account_type: 'demo'
  });
  
  // Money Management State
  const [moneyManagement, setMoneyManagement] = useState({
    mode: 'fixed',
    base_amount: 1,
    // Martingale settings
    martingale_multiplier: 2,
    martingale_max_steps: 5,
    martingale_reset_on_win: true,
    // Anti-Martingale settings
    anti_martingale_multiplier: 1.5,
    anti_martingale_max_steps: 3,
    // Percentage settings
    risk_percentage: 2,
    // Session settings
    session_profit_target: 50,
    session_stop_loss: -25,
    daily_profit_target: 100,
    daily_stop_loss: -50
  });
  
  // Current Session State
  const [sessionState, setSessionState] = useState({
    current_step: 0,
    current_amount: 1,
    session_profit: 0,
    session_trades: 0,
    consecutive_losses: 0,
    consecutive_wins: 0
  });
  
  // Active Orders
  const [activeOrders, setActiveOrders] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  
  // Loading States
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  
  // Fetch all data on mount
  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 5000);
    return () => clearInterval(interval);
  }, []);
  
  const fetchAllData = async () => {
    await Promise.all([
      fetchConnectionStatus(),
      fetchBotStatus(),
      fetchTradingSettings(),
      fetchActiveOrders(),
      fetchTradeHistory()
    ]);
    setIsLoading(false);
  };
  
  const fetchConnectionStatus = async () => {
    try {
      const response = await axios.get(`${API}/pocket-option/status`);
      setConnectionStatus(response.data);
    } catch (error) {
      console.error('Error fetching connection status:', error);
    }
  };
  
  const fetchBotStatus = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      setBotStatus(response.data);
    } catch (error) {
      console.error('Error fetching bot status:', error);
    }
  };
  
  const fetchTradingSettings = async () => {
    try {
      const response = await axios.get(`${API}/automated-trading/config`);
      if (response.data) {
        setTradingSettings(prev => ({ ...prev, ...response.data }));
        if (response.data.money_management) {
          setMoneyManagement(prev => ({ ...prev, ...response.data.money_management }));
        }
      }
    } catch (error) {
      console.error('Error fetching trading settings:', error);
    }
  };
  
  const fetchActiveOrders = async () => {
    try {
      const response = await axios.get(`${API}/automated-trading/active-orders`);
      setActiveOrders(response.data.orders || []);
    } catch (error) {
      console.error('Error fetching active orders:', error);
    }
  };
  
  const fetchTradeHistory = async () => {
    try {
      const response = await axios.get(`${API}/trade-executor/statistics`);
      if (response.data) {
        setTradeHistory(response.data.recent_trades || []);
        setSessionState(prev => ({
          ...prev,
          session_profit: response.data.total_profit || 0,
          session_trades: response.data.completed_count || 0
        }));
      }
    } catch (error) {
      console.error('Error fetching trade history:', error);
    }
  };
  
  // Bot Controls
  const handleStartBot = async () => {
    try {
      await axios.post(`${API}/bot/start`);
      toast.success('🚀 Trading bot started!');
      fetchBotStatus();
    } catch (error) {
      toast.error('Failed to start bot');
    }
  };
  
  const handleStopBot = async () => {
    try {
      await axios.post(`${API}/bot/stop`);
      toast.success('⏹️ Trading bot stopped');
      fetchBotStatus();
    } catch (error) {
      toast.error('Failed to stop bot');
    }
  };
  
  const handleToggleAutoTrade = async (enabled) => {
    try {
      await axios.post(`${API}/automated-trading/toggle`, { enabled });
      setTradingSettings(prev => ({ ...prev, auto_trade_enabled: enabled }));
      toast.success(enabled ? '✅ Auto-trading enabled' : '⏸️ Auto-trading paused');
    } catch (error) {
      toast.error('Failed to toggle auto-trading');
    }
  };
  
  // Save Settings
  const handleSaveSettings = async () => {
    setIsSaving(true);
    try {
      await axios.post(`${API}/automated-trading/config`, {
        ...tradingSettings,
        money_management: moneyManagement
      });
      toast.success('✅ Settings saved!');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };
  
  // Calculate next trade amount based on money management mode
  const calculateNextAmount = useCallback(() => {
    const { mode, base_amount, martingale_multiplier, martingale_max_steps,
            anti_martingale_multiplier, anti_martingale_max_steps, risk_percentage } = moneyManagement;
    const { consecutive_losses, consecutive_wins } = sessionState;
    
    switch (mode) {
      case 'fixed':
        return base_amount;
      
      case 'martingale':
        const martingaleStep = Math.min(consecutive_losses, martingale_max_steps);
        return base_amount * Math.pow(martingale_multiplier, martingaleStep);
      
      case 'anti_martingale':
        const antiStep = Math.min(consecutive_wins, anti_martingale_max_steps);
        return base_amount * Math.pow(anti_martingale_multiplier, antiStep);
      
      case 'percentage':
        return (connectionStatus.balance * risk_percentage) / 100;
      
      case 'custom_martingale':
        const customStep = Math.min(consecutive_losses, martingale_max_steps);
        return base_amount * Math.pow(martingale_multiplier, customStep);
      
      default:
        return base_amount;
    }
  }, [moneyManagement, sessionState, connectionStatus.balance]);
  
  // Reset session
  const handleResetSession = () => {
    setSessionState({
      current_step: 0,
      current_amount: moneyManagement.base_amount,
      session_profit: 0,
      session_trades: 0,
      consecutive_losses: 0,
      consecutive_wins: 0
    });
    toast.success('Session reset');
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Automated Trading</h1>
          <p className="text-slate-400 mt-1">Configure and control automated trading with Pocket Option</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className={connectionStatus.connected ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
            {connectionStatus.connected ? <Wifi className="w-3 h-3 mr-1" /> : <WifiOff className="w-3 h-3 mr-1" />}
            {connectionStatus.connected ? 'Connected' : 'Disconnected'}
          </Badge>
          <Badge className={botStatus.is_running ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'}>
            {botStatus.is_running ? 'Bot Active' : 'Bot Stopped'}
          </Badge>
        </div>
      </div>

      {/* Connection & Bot Status */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Balance</p>
                <p className="text-2xl font-bold text-white">${connectionStatus.balance?.toFixed(2) || '0.00'}</p>
              </div>
              <DollarSign className="w-8 h-8 text-green-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Session P/L</p>
                <p className={`text-2xl font-bold ${sessionState.session_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {sessionState.session_profit >= 0 ? '+' : ''}${sessionState.session_profit.toFixed(2)}
                </p>
              </div>
              {sessionState.session_profit >= 0 ? 
                <TrendingUp className="w-8 h-8 text-green-400" /> : 
                <TrendingDown className="w-8 h-8 text-red-400" />
              }
            </div>
          </CardContent>
        </Card>
        
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Win Rate</p>
                <p className="text-2xl font-bold text-white">
                  {botStatus.wins + botStatus.losses > 0 
                    ? ((botStatus.wins / (botStatus.wins + botStatus.losses)) * 100).toFixed(1) 
                    : '0'}%
                </p>
              </div>
              <Target className="w-8 h-8 text-purple-400" />
            </div>
            <p className="text-xs text-slate-500 mt-1">{botStatus.wins}W / {botStatus.losses}L</p>
          </CardContent>
        </Card>
        
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Next Trade</p>
                <p className="text-2xl font-bold text-white">${calculateNextAmount().toFixed(2)}</p>
              </div>
              <Zap className="w-8 h-8 text-yellow-400" />
            </div>
            <p className="text-xs text-slate-500 mt-1">{MONEY_MANAGEMENT_MODES[moneyManagement.mode.toUpperCase()]?.name || 'Fixed'}</p>
          </CardContent>
        </Card>
      </div>

      {/* Bot Controls */}
      <Card className="glass-dark border-slate-700/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-white flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Bot Controls
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-3">
              <Button
                onClick={handleStartBot}
                disabled={botStatus.is_running}
                className="bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30"
              >
                <Play className="w-4 h-4 mr-2" />
                Start Bot
              </Button>
              <Button
                onClick={handleStopBot}
                disabled={!botStatus.is_running}
                className="bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
              >
                <Square className="w-4 h-4 mr-2" />
                Stop Bot
              </Button>
            </div>
            
            <div className="h-8 w-px bg-slate-700" />
            
            <div className="flex items-center gap-3">
              <Label className="text-slate-300">Auto-Trade</Label>
              <Switch
                checked={tradingSettings.auto_trade_enabled}
                onCheckedChange={handleToggleAutoTrade}
              />
              <Badge className={tradingSettings.auto_trade_enabled ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'}>
                {tradingSettings.auto_trade_enabled ? 'ON' : 'OFF'}
              </Badge>
            </div>
            
            <div className="h-8 w-px bg-slate-700" />
            
            <div className="flex items-center gap-3">
              <Label className="text-slate-300">Account</Label>
              <Select 
                value={tradingSettings.account_type} 
                onValueChange={(v) => setTradingSettings(prev => ({ ...prev, account_type: v }))}
              >
                <SelectTrigger className="w-32 bg-slate-800/50 border-slate-600">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-600">
                  <SelectItem value="demo">🎮 Demo</SelectItem>
                  <SelectItem value="real">💰 Real</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <Button onClick={handleResetSession} variant="outline" className="border-slate-600 ml-auto">
              <RefreshCw className="w-4 h-4 mr-2" />
              Reset Session
            </Button>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="money" className="space-y-4">
        <TabsList className="bg-slate-800/50">
          <TabsTrigger value="money">💰 Money Management</TabsTrigger>
          <TabsTrigger value="settings">⚙️ Trade Settings</TabsTrigger>
          <TabsTrigger value="orders">📋 Active Orders ({activeOrders.length})</TabsTrigger>
          <TabsTrigger value="history">📊 Trade History</TabsTrigger>
        </TabsList>

        {/* Money Management Tab */}
        <TabsContent value="money" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Mode Selection */}
            <Card className="glass-dark border-slate-700/50">
              <CardHeader>
                <CardTitle className="text-white">Money Management Mode</CardTitle>
                <CardDescription>Choose how your trade amounts are calculated</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {Object.values(MONEY_MANAGEMENT_MODES).map((mode) => (
                  <div
                    key={mode.id}
                    onClick={() => setMoneyManagement(prev => ({ ...prev, mode: mode.id }))}
                    className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                      moneyManagement.mode === mode.id
                        ? 'border-purple-500 bg-purple-500/10'
                        : 'border-slate-600 hover:border-slate-500 bg-slate-800/30'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{mode.icon}</span>
                      <div>
                        <p className="font-medium text-white">{mode.name}</p>
                        <p className="text-sm text-slate-400">{mode.description}</p>
                      </div>
                      {moneyManagement.mode === mode.id && (
                        <CheckCircle className="w-5 h-5 text-purple-400 ml-auto" />
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Mode-specific Settings */}
            <Card className="glass-dark border-slate-700/50">
              <CardHeader>
                <CardTitle className="text-white">
                  {MONEY_MANAGEMENT_MODES[moneyManagement.mode.toUpperCase()]?.icon} {' '}
                  {MONEY_MANAGEMENT_MODES[moneyManagement.mode.toUpperCase()]?.name || 'Settings'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Base Amount (shown for all modes) */}
                <div>
                  <Label>Base Trade Amount ($)</Label>
                  <Input
                    type="number"
                    value={moneyManagement.base_amount}
                    onChange={(e) => setMoneyManagement(prev => ({ ...prev, base_amount: parseFloat(e.target.value) || 1 }))}
                    min={0.1}
                    step={0.1}
                    className="bg-slate-800/50 border-slate-600 mt-1"
                  />
                </div>

                {/* Martingale Settings */}
                {(moneyManagement.mode === 'martingale' || moneyManagement.mode === 'custom_martingale') && (
                  <>
                    <div>
                      <Label>Multiplier After Loss: {moneyManagement.martingale_multiplier}x</Label>
                      <Slider
                        value={[moneyManagement.martingale_multiplier]}
                        onValueChange={([v]) => setMoneyManagement(prev => ({ ...prev, martingale_multiplier: v }))}
                        min={1.5}
                        max={3}
                        step={0.1}
                        className="mt-2"
                      />
                    </div>
                    <div>
                      <Label>Max Steps (Losses before reset): {moneyManagement.martingale_max_steps}</Label>
                      <Slider
                        value={[moneyManagement.martingale_max_steps]}
                        onValueChange={([v]) => setMoneyManagement(prev => ({ ...prev, martingale_max_steps: v }))}
                        min={1}
                        max={10}
                        step={1}
                        className="mt-2"
                      />
                    </div>
                    <Alert className="bg-yellow-500/10 border-yellow-500/30">
                      <AlertTriangle className="w-4 h-4 text-yellow-400" />
                      <AlertDescription className="text-yellow-300 text-sm">
                        After {moneyManagement.martingale_max_steps} losses, max bet would be: 
                        <span className="font-bold ml-1">
                          ${(moneyManagement.base_amount * Math.pow(moneyManagement.martingale_multiplier, moneyManagement.martingale_max_steps)).toFixed(2)}
                        </span>
                      </AlertDescription>
                    </Alert>
                  </>
                )}

                {/* Anti-Martingale Settings */}
                {moneyManagement.mode === 'anti_martingale' && (
                  <>
                    <div>
                      <Label>Multiplier After Win: {moneyManagement.anti_martingale_multiplier}x</Label>
                      <Slider
                        value={[moneyManagement.anti_martingale_multiplier]}
                        onValueChange={([v]) => setMoneyManagement(prev => ({ ...prev, anti_martingale_multiplier: v }))}
                        min={1.1}
                        max={2}
                        step={0.1}
                        className="mt-2"
                      />
                    </div>
                    <div>
                      <Label>Max Win Steps: {moneyManagement.anti_martingale_max_steps}</Label>
                      <Slider
                        value={[moneyManagement.anti_martingale_max_steps]}
                        onValueChange={([v]) => setMoneyManagement(prev => ({ ...prev, anti_martingale_max_steps: v }))}
                        min={1}
                        max={5}
                        step={1}
                        className="mt-2"
                      />
                    </div>
                    <Alert className="bg-green-500/10 border-green-500/30">
                      <TrendingUp className="w-4 h-4 text-green-400" />
                      <AlertDescription className="text-green-300 text-sm">
                        After {moneyManagement.anti_martingale_max_steps} wins, bet would be: 
                        <span className="font-bold ml-1">
                          ${(moneyManagement.base_amount * Math.pow(moneyManagement.anti_martingale_multiplier, moneyManagement.anti_martingale_max_steps)).toFixed(2)}
                        </span>
                      </AlertDescription>
                    </Alert>
                  </>
                )}

                {/* Percentage Settings */}
                {moneyManagement.mode === 'percentage' && (
                  <>
                    <div>
                      <Label>Risk Per Trade: {moneyManagement.risk_percentage}%</Label>
                      <Slider
                        value={[moneyManagement.risk_percentage]}
                        onValueChange={([v]) => setMoneyManagement(prev => ({ ...prev, risk_percentage: v }))}
                        min={0.5}
                        max={10}
                        step={0.5}
                        className="mt-2"
                      />
                    </div>
                    <Alert className="bg-blue-500/10 border-blue-500/30">
                      <DollarSign className="w-4 h-4 text-blue-400" />
                      <AlertDescription className="text-blue-300 text-sm">
                        With current balance of ${connectionStatus.balance?.toFixed(2)}, next trade: 
                        <span className="font-bold ml-1">
                          ${((connectionStatus.balance * moneyManagement.risk_percentage) / 100).toFixed(2)}
                        </span>
                      </AlertDescription>
                    </Alert>
                  </>
                )}

                {/* Session Targets */}
                <div className="pt-4 border-t border-slate-700">
                  <h4 className="font-medium text-white mb-4">Session Targets</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-green-400">Profit Target ($)</Label>
                      <Input
                        type="number"
                        value={moneyManagement.session_profit_target}
                        onChange={(e) => setMoneyManagement(prev => ({ ...prev, session_profit_target: parseFloat(e.target.value) || 0 }))}
                        className="bg-slate-800/50 border-slate-600 mt-1"
                      />
                    </div>
                    <div>
                      <Label className="text-red-400">Stop Loss ($)</Label>
                      <Input
                        type="number"
                        value={moneyManagement.session_stop_loss}
                        onChange={(e) => setMoneyManagement(prev => ({ ...prev, session_stop_loss: parseFloat(e.target.value) || 0 }))}
                        className="bg-slate-800/50 border-slate-600 mt-1"
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Current Session Status */}
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Current Session Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                  <p className="text-slate-400 text-sm">Current Step</p>
                  <p className="text-xl font-bold text-white">{sessionState.current_step}</p>
                </div>
                <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                  <p className="text-slate-400 text-sm">Next Amount</p>
                  <p className="text-xl font-bold text-purple-400">${calculateNextAmount().toFixed(2)}</p>
                </div>
                <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                  <p className="text-slate-400 text-sm">Session Trades</p>
                  <p className="text-xl font-bold text-white">{sessionState.session_trades}</p>
                </div>
                <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                  <p className="text-slate-400 text-sm">Consecutive Losses</p>
                  <p className="text-xl font-bold text-red-400">{sessionState.consecutive_losses}</p>
                </div>
                <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                  <p className="text-slate-400 text-sm">Consecutive Wins</p>
                  <p className="text-xl font-bold text-green-400">{sessionState.consecutive_wins}</p>
                </div>
                <div className="text-center p-3 bg-slate-800/30 rounded-lg">
                  <p className="text-slate-400 text-sm">Session P/L</p>
                  <p className={`text-xl font-bold ${sessionState.session_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {sessionState.session_profit >= 0 ? '+' : ''}${sessionState.session_profit.toFixed(2)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trade Settings Tab */}
        <TabsContent value="settings">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Trade Execution Settings</CardTitle>
              <CardDescription>Configure automated trade execution parameters</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label>Minimum Signal Confidence: {tradingSettings.min_confidence}%</Label>
                  <Slider
                    value={[tradingSettings.min_confidence]}
                    onValueChange={([v]) => setTradingSettings(prev => ({ ...prev, min_confidence: v }))}
                    min={50}
                    max={99}
                    className="mt-2"
                  />
                  <p className="text-xs text-slate-500 mt-1">Only execute trades above this confidence level</p>
                </div>
                
                <div>
                  <Label>Max Trades Per Hour: {tradingSettings.max_trades_per_hour}</Label>
                  <Slider
                    value={[tradingSettings.max_trades_per_hour]}
                    onValueChange={([v]) => setTradingSettings(prev => ({ ...prev, max_trades_per_hour: v }))}
                    min={1}
                    max={60}
                    className="mt-2"
                  />
                </div>
                
                <div>
                  <Label>Max Trades Per Day: {tradingSettings.max_trades_per_day}</Label>
                  <Slider
                    value={[tradingSettings.max_trades_per_day]}
                    onValueChange={([v]) => setTradingSettings(prev => ({ ...prev, max_trades_per_day: v }))}
                    min={1}
                    max={200}
                    className="mt-2"
                  />
                </div>
                
                <div>
                  <Label>Cooldown Between Trades (seconds): {tradingSettings.cooldown_seconds}</Label>
                  <Slider
                    value={[tradingSettings.cooldown_seconds]}
                    onValueChange={([v]) => setTradingSettings(prev => ({ ...prev, cooldown_seconds: v }))}
                    min={5}
                    max={120}
                    className="mt-2"
                  />
                </div>
              </div>
              
              <div className="pt-4 border-t border-slate-700 flex justify-end">
                <Button onClick={handleSaveSettings} disabled={isSaving} className="bg-purple-500 hover:bg-purple-600">
                  {isSaving ? 'Saving...' : 'Save Settings'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Active Orders Tab */}
        <TabsContent value="orders">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Active Orders</CardTitle>
              <CardDescription>Currently open positions</CardDescription>
            </CardHeader>
            <CardContent>
              {activeOrders.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <Activity className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No active orders</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {activeOrders.map((order, idx) => (
                    <div key={idx} className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg">
                      <div className="flex items-center gap-4">
                        <Badge className={order.direction === 'call' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                          {order.direction === 'call' ? <ArrowUp className="w-3 h-3 mr-1" /> : <ArrowDown className="w-3 h-3 mr-1" />}
                          {order.direction?.toUpperCase()}
                        </Badge>
                        <div>
                          <p className="font-medium text-white">{order.asset}</p>
                          <p className="text-sm text-slate-400">${order.amount} • {order.duration}s</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-slate-400">{order.confidence}% confidence</p>
                        <p className="text-xs text-slate-500">{order.strategy}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trade History Tab */}
        <TabsContent value="history">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Recent Trade History</CardTitle>
            </CardHeader>
            <CardContent>
              {tradeHistory.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No trade history yet</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {tradeHistory.slice(0, 20).map((trade, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
                      <div className="flex items-center gap-3">
                        <Badge className={trade.result === 'win' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                          {trade.result === 'win' ? '✓' : '✗'}
                        </Badge>
                        <div>
                          <p className="text-sm font-medium text-white">{trade.asset}</p>
                          <p className="text-xs text-slate-400">{trade.direction} • ${trade.amount}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-medium ${trade.profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {trade.profit >= 0 ? '+' : ''}${trade.profit?.toFixed(2)}
                        </p>
                        <p className="text-xs text-slate-500">{new Date(trade.timestamp).toLocaleTimeString()}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AutomatedTradingPage;
