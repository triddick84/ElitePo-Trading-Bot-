import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { Progress } from './ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import axios from 'axios';
import { toast } from 'sonner';
import ActiveOrdersTable from './ActiveOrdersTable';
import TradeHistoryTable from './TradeHistoryTable';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const AutomatedTradingPanel = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  
  // Configuration state
  const [config, setConfig] = useState({
    default_stake: 1.0,
    max_concurrent_trades: 5,
    min_confidence: 70.0,
    use_money_management: true,
    use_risk_rules: true
  });

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/automated-trading/status`);
      if (response.data.success) {
        setStatus(response.data);
        if (response.data.config) {
          setConfig(response.data.config);
        }
      }
    } catch (error) {
      console.error('Error loading status:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleAutomatedTrading = async () => {
    try {
      setUpdating(true);
      const endpoint = status?.is_enabled ? 'disable' : 'enable';
      const response = await axios.post(`${BACKEND_URL}/api/automated-trading/${endpoint}`);
      
      if (response.data.success) {
        toast.success(
          status?.is_enabled 
            ? '⏸️ Automated trading disabled' 
            : '✅ Automated trading enabled'
        );
        await loadStatus();
      } else {
        toast.error('Failed to toggle automated trading');
      }
    } catch (error) {
      console.error('Error toggling automated trading:', error);
      toast.error('Error toggling automated trading');
    } finally {
      setUpdating(false);
    }
  };

  const updateConfiguration = async () => {
    try {
      setUpdating(true);
      const response = await axios.post(
        `${BACKEND_URL}/api/automated-trading/config`,
        config
      );
      
      if (response.data.success) {
        toast.success('✅ Configuration updated');
        await loadStatus();
      } else {
        toast.error('Failed to update configuration');
      }
    } catch (error) {
      console.error('Error updating configuration:', error);
      toast.error('Error updating configuration');
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <Card className="w-full bg-slate-900 border-slate-700">
        <CardContent className="p-6">
          <div className="text-center text-slate-400">Loading automated trading...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Main Control Panel */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-2xl text-emerald-400">🤖 Automated Trading</CardTitle>
              <CardDescription className="text-slate-400">
                Automatically execute trades from generated signals
              </CardDescription>
            </div>
            <div className="flex items-center gap-3">
              <Label htmlFor="auto-trading-toggle" className="text-slate-300 font-semibold">
                {status?.is_enabled ? 'Enabled' : 'Disabled'}
              </Label>
              <Switch
                id="auto-trading-toggle"
                checked={status?.is_enabled || false}
                onCheckedChange={toggleAutomatedTrading}
                disabled={updating}
                className="data-[state=checked]:bg-emerald-600"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Status Indicator */}
          <div className="mb-6">
            {status?.is_enabled ? (
              <div className="bg-emerald-500/10 border border-emerald-500 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div>
                  <div>
                    <p className="text-emerald-400 font-semibold">Automated Trading Active</p>
                    <p className="text-sm text-slate-400">
                      All signals meeting criteria will be automatically executed
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-slate-500"></div>
                  <div>
                    <p className="text-slate-300 font-semibold">Automated Trading Disabled</p>
                    <p className="text-sm text-slate-400">
                      Signals will be generated but not automatically executed
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Statistics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400 mb-1">Total Trades</p>
              <p className="text-2xl font-bold text-white">{status?.total_trades || 0}</p>
            </div>
            
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400 mb-1">Win Rate</p>
              <p className="text-2xl font-bold text-emerald-400">
                {status?.win_rate ? `${status.win_rate.toFixed(1)}%` : '0%'}
              </p>
              {status?.win_rate && <Progress value={status.win_rate} className="mt-2 h-2" />}
            </div>
            
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400 mb-1">Active Orders</p>
              <p className="text-2xl font-bold text-blue-400">{status?.active_orders || 0}</p>
            </div>
            
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400 mb-1">Total Profit</p>
              <p className="text-2xl font-bold text-amber-400">
                ${status?.total_profit ? status.total_profit.toFixed(2) : '0.00'}
              </p>
            </div>
          </div>

          {/* Configuration */}
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader>
              <CardTitle className="text-lg text-white">⚙️ Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Default Stake */}
                <div>
                  <Label className="text-slate-300 mb-2 block">Default Stake ($)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={config.default_stake}
                    onChange={(e) => setConfig({...config, default_stake: parseFloat(e.target.value)})}
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                  <p className="text-xs text-slate-500 mt-1">Base stake amount per trade</p>
                </div>

                {/* Max Concurrent Trades */}
                <div>
                  <Label className="text-slate-300 mb-2 block">Max Concurrent Trades</Label>
                  <Input
                    type="number"
                    min="1"
                    max="10"
                    value={config.max_concurrent_trades}
                    onChange={(e) => setConfig({...config, max_concurrent_trades: parseInt(e.target.value)})}
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                  <p className="text-xs text-slate-500 mt-1">Maximum trades at once</p>
                </div>

                {/* Min Confidence */}
                <div>
                  <Label className="text-slate-300 mb-2 block">Min Confidence (%)</Label>
                  <Input
                    type="number"
                    min="50"
                    max="100"
                    step="5"
                    value={config.min_confidence}
                    onChange={(e) => setConfig({...config, min_confidence: parseFloat(e.target.value)})}
                    className="bg-slate-900 border-slate-700 text-white"
                  />
                  <p className="text-xs text-slate-500 mt-1">Minimum signal confidence to execute</p>
                </div>

                {/* Money Management Toggle */}
                <div className="flex items-center justify-between bg-slate-900 rounded-lg p-4">
                  <div>
                    <Label className="text-slate-300 font-semibold">Kelly Formula</Label>
                    <p className="text-xs text-slate-500">Dynamic stake calculation</p>
                  </div>
                  <Switch
                    checked={config.use_money_management}
                    onCheckedChange={(checked) => setConfig({...config, use_money_management: checked})}
                    className="data-[state=checked]:bg-emerald-600"
                  />
                </div>
              </div>

              {/* Risk Rules Toggle */}
              <div className="flex items-center justify-between bg-slate-900 rounded-lg p-4">
                <div>
                  <Label className="text-slate-300 font-semibold">Risk Management Rules</Label>
                  <p className="text-xs text-slate-500">6 protective schemes (time limits, concentration, etc.)</p>
                </div>
                <Switch
                  checked={config.use_risk_rules}
                  onCheckedChange={(checked) => setConfig({...config, use_risk_rules: checked})}
                  className="data-[state=checked]:bg-emerald-600"
                />
              </div>

              {/* Save Button */}
              <Button
                onClick={updateConfiguration}
                disabled={updating}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {updating ? '⏳ Updating...' : '💾 Save Configuration'}
              </Button>
            </CardContent>
          </Card>
        </CardContent>
      </Card>

      {/* Tabs for Orders and History */}
      <Card className="bg-slate-900 border-slate-700">
        <CardContent className="p-6">
          <Tabs defaultValue="active" className="w-full">
            <TabsList className="grid w-full grid-cols-2 bg-slate-800">
              <TabsTrigger value="active" className="data-[state=active]:bg-slate-700">
                📊 Active Orders ({status?.active_orders || 0})
              </TabsTrigger>
              <TabsTrigger value="history" className="data-[state=active]:bg-slate-700">
                📜 Trade History
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="active" className="mt-4">
              <ActiveOrdersTable />
            </TabsContent>
            
            <TabsContent value="history" className="mt-4">
              <TradeHistoryTable />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Risk Management Info */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <CardTitle className="text-lg text-white">⚠️ Active Risk Management Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span className="text-slate-300">
                <strong>Fixed Percentage:</strong> Max 5% of balance per trade
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span className="text-slate-300">
                <strong>Time Filter:</strong> Max 3 trades per 5 minutes
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span className="text-slate-300">
                <strong>Asset Concentration:</strong> Max 2 trades per asset
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span className="text-slate-300">
                <strong>Daily Limit:</strong> Max 100 trades per day
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span className="text-slate-300">
                <strong>Correlation Check:</strong> Avoid correlated assets
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-emerald-400">✓</span>
              <span className="text-slate-300">
                <strong>Drawdown Protection:</strong> Reduce stakes during losses
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AutomatedTradingPanel;