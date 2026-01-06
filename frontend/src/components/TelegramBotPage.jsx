import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import { 
  MessageSquare, Send, Bot, Play, Square, Settings, 
  TrendingUp, History, BarChart3, DollarSign, Wifi, WifiOff 
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const TelegramBotPage = () => {
  const [status, setStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState({ signals: [], trades: [] });
  const [loading, setLoading] = useState(true);
  const [testMessage, setTestMessage] = useState('');
  const [tradeAmount, setTradeAmount] = useState(1);

  useEffect(() => {
    fetchStatus();
    fetchStats();
    fetchHistory();
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/telegram/status`);
      const data = await response.json();
      if (data.success !== false) {
        setStatus(data.status || data);
      }
    } catch (error) {
      console.error('Error fetching status:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/telegram/stats`);
      const data = await response.json();
      if (data.success) {
        setStats(data.stats);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchHistory = async () => {
    try {
      const response = await fetch(`${API_URL}/api/telegram/history?limit=20`);
      const data = await response.json();
      if (data.success) {
        setHistory({ signals: data.signals || [], trades: data.trades || [] });
      }
    } catch (error) {
      console.error('Error fetching history:', error);
    }
  };

  const startBot = async () => {
    try {
      const response = await fetch(`${API_URL}/api/telegram/start`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        toast.success('Telegram bot started!');
        fetchStatus();
      } else {
        toast.error(data.message || 'Failed to start bot');
      }
    } catch (error) {
      toast.error('Error starting bot');
    }
  };

  const stopBot = async () => {
    try {
      const response = await fetch(`${API_URL}/api/telegram/stop`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        toast.success('Telegram bot stopped');
        fetchStatus();
      }
    } catch (error) {
      toast.error('Error stopping bot');
    }
  };

  const updateSettings = async (settings) => {
    try {
      const response = await fetch(`${API_URL}/api/telegram/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      const data = await response.json();
      if (data.success) {
        toast.success('Settings updated');
        fetchStatus();
      }
    } catch (error) {
      toast.error('Error updating settings');
    }
  };

  const sendTestMessage = async () => {
    if (!testMessage.trim()) {
      toast.error('Enter a message');
      return;
    }
    try {
      const response = await fetch(`${API_URL}/api/telegram/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: testMessage })
      });
      const data = await response.json();
      if (data.success) {
        toast.success('Message sent to Telegram!');
        setTestMessage('');
      } else {
        toast.error(data.error || 'Failed to send');
      }
    } catch (error) {
      toast.error('Error sending message');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Bot className="w-8 h-8 text-blue-400" />
          Telegram Bot
        </h1>
        <Badge 
          variant="outline" 
          className={status?.is_running ? 'border-green-500 text-green-400' : 'border-red-500 text-red-400'}
        >
          {status?.is_running ? <Wifi className="w-4 h-4 mr-1" /> : <WifiOff className="w-4 h-4 mr-1" />}
          {status?.is_running ? 'Online' : 'Offline'}
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Stats Cards */}
        <Card className="bg-slate-900/80 border-slate-700">
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-400" />
              <span className="text-slate-400">Win Rate</span>
            </div>
            <p className="text-2xl font-bold text-white mt-2">
              {stats?.win_rate?.toFixed(1) || 0}%
            </p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900/80 border-slate-700">
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-400" />
              <span className="text-slate-400">Total Trades</span>
            </div>
            <p className="text-2xl font-bold text-white mt-2">
              {stats?.total_trades || 0}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900/80 border-slate-700">
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-purple-400" />
              <span className="text-slate-400">Signals Sent</span>
            </div>
            <p className="text-2xl font-bold text-white mt-2">
              {stats?.total_signals || 0}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900/80 border-slate-700">
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-yellow-400" />
              <span className="text-slate-400">Total P/L</span>
            </div>
            <p className={`text-2xl font-bold mt-2 ${(stats?.total_profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${stats?.total_profit?.toFixed(2) || '0.00'}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Bot Controls */}
        <Card className="bg-slate-900/80 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Bot Controls
            </CardTitle>
            <CardDescription>Manage your Telegram trading bot</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Button 
                onClick={startBot} 
                disabled={status?.is_running}
                className="flex-1 bg-green-600 hover:bg-green-700"
              >
                <Play className="w-4 h-4 mr-2" />
                Start Bot
              </Button>
              <Button 
                onClick={stopBot} 
                disabled={!status?.is_running}
                variant="destructive"
                className="flex-1"
              >
                <Square className="w-4 h-4 mr-2" />
                Stop Bot
              </Button>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-slate-300">Auto-Trading</Label>
                <Switch
                  checked={status?.auto_trading_enabled || false}
                  onCheckedChange={(checked) => updateSettings({ auto_trading_enabled: checked })}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label className="text-slate-300">Demo Mode</Label>
                <Switch
                  checked={status?.demo_mode !== false}
                  onCheckedChange={(checked) => updateSettings({ demo_mode: checked })}
                />
              </div>

              <div className="space-y-2">
                <Label className="text-slate-300">Trade Amount ($)</Label>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    min="1"
                    max="1000"
                    value={tradeAmount}
                    onChange={(e) => setTradeAmount(e.target.value)}
                    className="bg-slate-800 border-slate-600"
                  />
                  <Button 
                    onClick={() => updateSettings({ trade_amount: parseFloat(tradeAmount) })}
                    variant="outline"
                  >
                    Set
                  </Button>
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-700">
              <p className="text-xs text-slate-400 mb-2">Chat ID: {status?.default_chat_id || 'Not set'}</p>
            </div>
          </CardContent>
        </Card>

        {/* Send Test Message */}
        <Card className="bg-slate-900/80 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Send className="w-5 h-5" />
              Send Message
            </CardTitle>
            <CardDescription>Send a test message to your Telegram</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="text-slate-300">Message</Label>
              <textarea
                value={testMessage}
                onChange={(e) => setTestMessage(e.target.value)}
                placeholder="Enter your message..."
                className="w-full h-32 p-3 bg-slate-800 border border-slate-600 rounded-md text-white placeholder-slate-400 resize-none"
              />
            </div>
            <Button 
              onClick={sendTestMessage}
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              <Send className="w-4 h-4 mr-2" />
              Send to Telegram
            </Button>

            <div className="pt-4 border-t border-slate-700">
              <h4 className="text-sm font-medium text-slate-300 mb-2">Available Commands</h4>
              <div className="text-xs text-slate-400 space-y-1">
                <p><code className="bg-slate-800 px-1 rounded">/start</code> - Welcome message</p>
                <p><code className="bg-slate-800 px-1 rounded">/help</code> - Show all commands</p>
                <p><code className="bg-slate-800 px-1 rounded">/status</code> - Bot status</p>
                <p><code className="bg-slate-800 px-1 rounded">/enable</code> - Enable auto-trading</p>
                <p><code className="bg-slate-800 px-1 rounded">/disable</code> - Disable auto-trading</p>
                <p><code className="bg-slate-800 px-1 rounded">/signal</code> - Force generate signal</p>
                <p><code className="bg-slate-800 px-1 rounded">/stats</code> - Trading statistics</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card className="bg-slate-900/80 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <History className="w-5 h-5" />
            Recent Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {history.trades.length === 0 && history.signals.length === 0 ? (
            <p className="text-slate-400 text-center py-8">No activity yet. Start the bot to begin receiving signals!</p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {history.trades.map((trade, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 bg-slate-800 rounded">
                  <div className="flex items-center gap-2">
                    <span className={trade.status === 'won' ? 'text-green-400' : trade.status === 'lost' ? 'text-red-400' : 'text-yellow-400'}>
                      {trade.status === 'won' ? '✅' : trade.status === 'lost' ? '❌' : '⏳'}
                    </span>
                    <span className="text-white">{trade.direction} {trade.symbol}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-slate-400">${trade.amount}</span>
                    {trade.profit !== 0 && (
                      <span className={`ml-2 ${trade.profit > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {trade.profit > 0 ? '+' : ''}{trade.profit?.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default TelegramBotPage;
