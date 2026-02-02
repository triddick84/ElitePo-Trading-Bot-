import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

const SettingsPage = () => {
  const [activeTab, setActiveTab] = useState('general');
  const [settings, setSettings] = useState({
    // General settings
    defaultTimeframe: '1m',
    defaultAsset: 'EURUSD_otc',
    soundEnabled: true,
    notificationsEnabled: true,
    
    // Signal settings
    minimumConfidence: 70,
    signalCooldown: 30,
    
    // API Keys (display only - masked)
    telegramBotToken: '',
    telegramChatId: '',
  });
  
  const [integrationStatus, setIntegrationStatus] = useState({
    telegram: false,
    alphaVantage: false,
  });
  
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchSettings();
    checkIntegrations();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/settings`);
      if (response.data) {
        setSettings(prev => ({ ...prev, ...response.data }));
      }
    } catch (error) {
      console.log('Using default settings');
    }
  };

  const checkIntegrations = async () => {
    try {
      const telegramRes = await axios.get(`${API}/telegram-bot/status`);
      setIntegrationStatus(prev => ({
        ...prev,
        telegram: telegramRes.data?.status?.bot_token_configured || false
      }));
    } catch (error) {
      console.log('Could not check integrations');
    }
  };

  const saveSettings = async () => {
    setIsLoading(true);
    try {
      await axios.post(`${API}/settings`, settings);
      toast.success('Settings saved successfully!');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setIsLoading(false);
    }
  };

  const testTelegram = async () => {
    try {
      const response = await axios.post(`${API}/telegram-bot/send`, {
        message: '🧪 Test message from GPT Signal Bot settings!'
      });
      if (response.data?.success) {
        toast.success('Test message sent to Telegram!');
      } else {
        toast.error('Failed to send test message');
      }
    } catch (error) {
      toast.error('Telegram test failed');
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">⚙️ Settings</h1>
          <p className="text-slate-400">Configure your trading bot preferences and integrations</p>
        </div>
        <Button 
          onClick={saveSettings} 
          disabled={isLoading}
          className="bg-purple-600 hover:bg-purple-700"
        >
          {isLoading ? 'Saving...' : '💾 Save Settings'}
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3 bg-slate-800/50 max-w-lg">
          <TabsTrigger value="general" className="data-[state=active]:bg-purple-600">
            ⚙️ General
          </TabsTrigger>
          <TabsTrigger value="signals" className="data-[state=active]:bg-purple-600">
            📊 Signals
          </TabsTrigger>
          <TabsTrigger value="integrations" className="data-[state=active]:bg-purple-600">
            🔌 Integrations
          </TabsTrigger>
        </TabsList>

        {/* General Settings */}
        <TabsContent value="general" className="mt-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">Default Trading Settings</CardTitle>
                <CardDescription>Configure default values for signal generation</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Default Timeframe</Label>
                  <select 
                    className="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
                    value={settings.defaultTimeframe}
                    onChange={(e) => setSettings({...settings, defaultTimeframe: e.target.value})}
                  >
                    <option value="15s">15 Seconds</option>
                    <option value="30s">30 Seconds</option>
                    <option value="1m">1 Minute</option>
                    <option value="5m">5 Minutes</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>Default Asset</Label>
                  <select 
                    className="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
                    value={settings.defaultAsset}
                    onChange={(e) => setSettings({...settings, defaultAsset: e.target.value})}
                  >
                    <option value="EURUSD_otc">EUR/USD (OTC)</option>
                    <option value="GBPUSD_otc">GBP/USD (OTC)</option>
                    <option value="BTCUSD_otc">BTC/USD (OTC)</option>
                    <option value="EURUSD_regular">EUR/USD (Regular)</option>
                  </select>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">Notifications</CardTitle>
                <CardDescription>Configure notification preferences</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Sound Alerts</Label>
                    <p className="text-xs text-slate-400">Play sound on new signals</p>
                  </div>
                  <Switch 
                    checked={settings.soundEnabled}
                    onCheckedChange={(checked) => setSettings({...settings, soundEnabled: checked})}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Browser Notifications</Label>
                    <p className="text-xs text-slate-400">Show desktop notifications</p>
                  </div>
                  <Switch 
                    checked={settings.notificationsEnabled}
                    onCheckedChange={(checked) => setSettings({...settings, notificationsEnabled: checked})}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Signal Settings */}
        <TabsContent value="signals" className="mt-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">Signal Quality</CardTitle>
                <CardDescription>Set minimum thresholds for signals</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Minimum Confidence (%)</Label>
                  <div className="flex items-center gap-4">
                    <Input 
                      type="range"
                      min="50"
                      max="95"
                      value={settings.minimumConfidence}
                      onChange={(e) => setSettings({...settings, minimumConfidence: parseInt(e.target.value)})}
                      className="flex-1"
                    />
                    <span className="text-purple-400 font-bold w-12">{settings.minimumConfidence}%</span>
                  </div>
                  <p className="text-xs text-slate-400">Signals below this confidence will be filtered out</p>
                </div>
                <div className="space-y-2">
                  <Label>Signal Cooldown (seconds)</Label>
                  <Input 
                    type="number"
                    min="10"
                    max="300"
                    value={settings.signalCooldown}
                    onChange={(e) => setSettings({...settings, signalCooldown: parseInt(e.target.value)})}
                    className="bg-slate-800 border-slate-600"
                  />
                  <p className="text-xs text-slate-400">Minimum time between signals for same asset</p>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">Signal Filters</CardTitle>
                <CardDescription>Filter signals based on market conditions</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-slate-800/50 rounded-lg">
                  <p className="text-slate-300 text-sm">
                    💡 <strong>Tip:</strong> Higher confidence thresholds mean fewer but more accurate signals.
                    For manual trading, we recommend 70-80% minimum confidence.
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setSettings({...settings, minimumConfidence: 60})}
                    className={settings.minimumConfidence === 60 ? 'bg-purple-600 border-purple-600' : ''}
                  >
                    60% (More)
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setSettings({...settings, minimumConfidence: 75})}
                    className={settings.minimumConfidence === 75 ? 'bg-purple-600 border-purple-600' : ''}
                  >
                    75% (Balanced)
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setSettings({...settings, minimumConfidence: 85})}
                    className={settings.minimumConfidence === 85 ? 'bg-purple-600 border-purple-600' : ''}
                  >
                    85% (Quality)
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Integrations */}
        <TabsContent value="integrations" className="mt-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg flex items-center gap-2">
                  📱 Telegram Bot
                  <Badge className={integrationStatus.telegram ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                    {integrationStatus.telegram ? '✅ Connected' : '❌ Not Configured'}
                  </Badge>
                </CardTitle>
                <CardDescription>Send trading signals to Telegram</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Bot Token</Label>
                  <Input 
                    type="password"
                    placeholder="Enter Telegram bot token"
                    value={settings.telegramBotToken}
                    onChange={(e) => setSettings({...settings, telegramBotToken: e.target.value})}
                    className="bg-slate-800 border-slate-600"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Chat ID</Label>
                  <Input 
                    type="text"
                    placeholder="Enter chat ID"
                    value={settings.telegramChatId}
                    onChange={(e) => setSettings({...settings, telegramChatId: e.target.value})}
                    className="bg-slate-800 border-slate-600"
                  />
                </div>
                <Button onClick={testTelegram} variant="outline" className="w-full">
                  🧪 Send Test Message
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">📡 Data Sources</CardTitle>
                <CardDescription>Market data providers</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                  <div className="flex items-center gap-2">
                    <span className="text-green-400">✅</span>
                    <span className="text-green-400 font-medium">Real Market Data Active</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">Using live data from multiple sources</p>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                    <span className="text-slate-300">Yahoo Finance</span>
                    <Badge className="bg-green-500/20 text-green-400">Active</Badge>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                    <span className="text-slate-300">Alpha Vantage</span>
                    <Badge className="bg-yellow-500/20 text-yellow-400">Backup</Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default SettingsPage;
