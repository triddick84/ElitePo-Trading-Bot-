import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { RefreshCw, Wifi, WifiOff, Send, Copy, Check, ArrowUpDown, BarChart3, Zap } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const IntegrationsPage = () => {
  const [mt5Status, setMt5Status] = useState(null);
  const [mt5Account, setMt5Account] = useState(null);
  const [tvStats, setTvStats] = useState(null);
  const [tvHistory, setTvHistory] = useState([]);
  const [copied, setCopied] = useState('');
  const [loading, setLoading] = useState({});

  // MT5 form
  const [mt5Login, setMt5Login] = useState('');
  const [mt5Password, setMt5Password] = useState('');
  const [mt5Server, setMt5Server] = useState('');

  // TV test
  const [tvTestSymbol, setTvTestSymbol] = useState('EURUSD');
  const [tvTestAction, setTvTestAction] = useState('buy');
  const [tvTestResult, setTvTestResult] = useState(null);

  const webhookUrl = `${API}/api/tradingview/webhook`;

  const fetchAll = useCallback(async () => {
    try {
      const [mt5Res, tvStatsRes, tvHistRes] = await Promise.all([
        axios.get(`${API}/api/mt5/status`).catch(() => null),
        axios.get(`${API}/api/tradingview/stats`).catch(() => null),
        axios.get(`${API}/api/tradingview/history?limit=10`).catch(() => null),
      ]);
      if (mt5Res?.data?.success) setMt5Status(mt5Res.data.status);
      if (tvStatsRes?.data?.success) setTvStats(tvStatsRes.data.stats);
      if (tvHistRes?.data?.success) setTvHistory(tvHistRes.data.alerts || []);

      // Fetch account if connected
      if (mt5Res?.data?.status?.connected) {
        const acctRes = await axios.get(`${API}/api/mt5/account`).catch(() => null);
        if (acctRes?.data?.success) setMt5Account(acctRes.data.account);
      }
    } catch (e) { /* ignore */ }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(''), 2000);
  };

  const connectMT5 = async () => {
    setLoading(p => ({ ...p, mt5Connect: true }));
    try {
      const params = new URLSearchParams();
      if (mt5Login) params.append('login', mt5Login);
      if (mt5Password) params.append('password', mt5Password);
      if (mt5Server) params.append('server', mt5Server);
      const res = await axios.post(`${API}/api/mt5/connect?${params.toString()}`);
      if (res.data.success || res.data.status?.connected) {
        toast.success('MT5 connected successfully');
        setMt5Status(res.data.status);
        fetchAll();
      } else {
        toast.error(res.data.error || 'Connection failed');
      }
    } catch (e) {
      toast.error('MT5 connection error');
    }
    setLoading(p => ({ ...p, mt5Connect: false }));
  };

  const disconnectMT5 = async () => {
    setLoading(p => ({ ...p, mt5Disconnect: true }));
    try {
      await axios.post(`${API}/api/mt5/disconnect`);
      toast.success('MT5 disconnected');
      setMt5Status(null);
      setMt5Account(null);
      fetchAll();
    } catch (e) {
      toast.error('Disconnect error');
    }
    setLoading(p => ({ ...p, mt5Disconnect: false }));
  };

  const testTVWebhook = async () => {
    setLoading(p => ({ ...p, tvTest: true }));
    setTvTestResult(null);
    try {
      const res = await axios.post(`${API}/api/tradingview/webhook`, {
        action: tvTestAction,
        symbol: tvTestSymbol,
        price: 1.0850,
        destination: 'pocket_option',
        passphrase: 'gpt-signal',
      });
      setTvTestResult(res.data);
      if (res.data.success) {
        toast.success(`Webhook test: ${res.data.alert?.execution_status}`);
        fetchAll();
      }
    } catch (e) {
      toast.error('Webhook test failed');
      setTvTestResult({ success: false, error: e.message });
    }
    setLoading(p => ({ ...p, tvTest: false }));
  };

  const isConnected = mt5Status?.connected;

  const pineScript = `//@version=5
strategy("GPT Signal Bot Alerts", overlay=true)

longCondition = ta.crossover(ta.sma(close, 14), ta.sma(close, 28))
shortCondition = ta.crossunder(ta.sma(close, 14), ta.sma(close, 28))

if (longCondition)
    strategy.entry("Long", strategy.long)
    alert('{"action":"BUY","symbol":"'+syminfo.ticker+'","price":'+str.tostring(close)+',"destination":"pocket_option","passphrase":"gpt-signal"}', alert.freq_once_per_bar)

if (shortCondition)
    strategy.entry("Short", strategy.short)
    alert('{"action":"SELL","symbol":"'+syminfo.ticker+'","price":'+str.tostring(close)+',"destination":"pocket_option","passphrase":"gpt-signal"}', alert.freq_once_per_bar)`;

  const webhookJson = `{
  "action": "BUY",
  "symbol": "EURUSD",
  "price": 1.0850,
  "stop_loss": 1.0800,
  "take_profit": 1.0900,
  "destination": "pocket_option",
  "passphrase": "gpt-signal"
}`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">Platform Integrations</h1>
          <p className="text-slate-400">Connect with MetaTrader 4/5 and TradingView</p>
        </div>

        <Tabs defaultValue="metatrader" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 bg-slate-800">
            <TabsTrigger value="metatrader" className="data-[state=active]:bg-purple-600">MetaTrader 4/5</TabsTrigger>
            <TabsTrigger value="tradingview" className="data-[state=active]:bg-purple-600">TradingView</TabsTrigger>
            <TabsTrigger value="api" className="data-[state=active]:bg-purple-600">API Reference</TabsTrigger>
          </TabsList>

          {/* ==================== METATRADER TAB ==================== */}
          <TabsContent value="metatrader" className="space-y-6">
            {/* MT5 Live Connection */}
            <Card className="bg-slate-800/50 border-slate-700" data-testid="mt5-connection-card">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-white flex items-center gap-2">
                      <ArrowUpDown className="w-5 h-5 text-green-400" />
                      MetaTrader 5 Connection
                    </CardTitle>
                    <CardDescription>Connect directly to MT5 for live trade execution</CardDescription>
                  </div>
                  <Badge data-testid="mt5-status-badge" className={isConnected ? 'bg-emerald-600' : 'bg-slate-600'}>
                    {isConnected ? <><Wifi className="w-3 h-3 mr-1" /> Connected</> : <><WifiOff className="w-3 h-3 mr-1" /> Disconnected</>}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {!isConnected ? (
                  <div className="grid md:grid-cols-3 gap-3">
                    <div>
                      <Label className="text-slate-400 text-xs">MT5 Login (Account #)</Label>
                      <Input data-testid="mt5-login-input" value={mt5Login} onChange={e => setMt5Login(e.target.value)} placeholder="12345678" className="bg-slate-900 border-slate-700 text-white" />
                    </div>
                    <div>
                      <Label className="text-slate-400 text-xs">Password</Label>
                      <Input data-testid="mt5-password-input" type="password" value={mt5Password} onChange={e => setMt5Password(e.target.value)} placeholder="••••••" className="bg-slate-900 border-slate-700 text-white" />
                    </div>
                    <div>
                      <Label className="text-slate-400 text-xs">Server</Label>
                      <Input data-testid="mt5-server-input" value={mt5Server} onChange={e => setMt5Server(e.target.value)} placeholder="MetaQuotes-Demo" className="bg-slate-900 border-slate-700 text-white" />
                    </div>
                  </div>
                ) : null}

                <div className="flex gap-3">
                  {!isConnected ? (
                    <Button data-testid="mt5-connect-btn" onClick={connectMT5} disabled={loading.mt5Connect} className="bg-emerald-600 hover:bg-emerald-700">
                      {loading.mt5Connect ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Wifi className="w-4 h-4 mr-2" />}
                      Connect MT5
                    </Button>
                  ) : (
                    <Button data-testid="mt5-disconnect-btn" onClick={disconnectMT5} disabled={loading.mt5Disconnect} variant="destructive">
                      <WifiOff className="w-4 h-4 mr-2" /> Disconnect
                    </Button>
                  )}
                  <Button variant="outline" className="border-slate-600" onClick={fetchAll}>
                    <RefreshCw className="w-4 h-4 mr-2" /> Refresh
                  </Button>
                </div>

                {/* Account Info */}
                {isConnected && mt5Account && (
                  <div data-testid="mt5-account-info" className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                    <div className="bg-slate-900 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">Balance</div>
                      <div className="text-lg font-bold text-emerald-400">${mt5Account.balance?.toLocaleString()}</div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">Equity</div>
                      <div className="text-lg font-bold text-sky-400">${mt5Account.equity?.toLocaleString()}</div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">Profit</div>
                      <div className={`text-lg font-bold ${mt5Account.profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>${mt5Account.profit?.toFixed(2)}</div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">Leverage</div>
                      <div className="text-lg font-bold text-purple-400">1:{mt5Account.leverage}</div>
                    </div>
                  </div>
                )}

                {isConnected && mt5Status && (
                  <div className="text-xs text-slate-500 flex gap-4">
                    <span>Server: {mt5Status.server}</span>
                    <span>Login: {mt5Status.login}</span>
                    <span>MT5 Native: {mt5Status.mt5_available ? 'Yes' : 'Simulated'}</span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* MT4 EA Download */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-blue-400" />
                  MetaTrader 4 Expert Advisor
                </CardTitle>
                <CardDescription>Download and install the EA to receive signals in MT4</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Features</h3>
                    <ul className="text-slate-300 text-sm space-y-1.5">
                      <li className="flex items-center gap-2"><Check className="w-3 h-3 text-emerald-400" /> Auto-receives signals from GPT Signal Bot</li>
                      <li className="flex items-center gap-2"><Check className="w-3 h-3 text-emerald-400" /> Configurable lot size, SL, TP</li>
                      <li className="flex items-center gap-2"><Check className="w-3 h-3 text-emerald-400" /> Magic number for trade identification</li>
                      <li className="flex items-center gap-2"><Check className="w-3 h-3 text-emerald-400" /> Auto-trade or alert-only mode</li>
                    </ul>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Installation</h3>
                    <ol className="text-slate-300 text-sm space-y-1.5 list-decimal list-inside">
                      <li>Download the EA file below</li>
                      <li>Copy to MT4/Experts folder</li>
                      <li>Restart MT4 or refresh Navigator</li>
                      <li>Drag EA onto a chart</li>
                      <li>Add API URL to allowed URLs</li>
                      <li>Enable Auto Trading</li>
                    </ol>
                  </div>
                </div>
                <div className="flex gap-3">
                  <a href="/downloads/GPT_Signal_Bot_EA_MT4.mq4" download>
                    <Button className="bg-blue-600 hover:bg-blue-700">Download MT4 EA (.mq4)</Button>
                  </a>
                  <Button variant="outline" className="border-slate-600" onClick={() => copyToClipboard(`${API}/api`, 'mt4-api')}>
                    {copied === 'mt4-api' ? <><Check className="w-4 h-4 mr-1" /> Copied</> : <><Copy className="w-4 h-4 mr-1" /> Copy API URL</>}
                  </Button>
                </div>
                <div className="bg-amber-900/30 border border-amber-600/50 rounded-lg p-3">
                  <p className="text-amber-200 text-sm">
                    <strong>Important:</strong> In MT4, go to Tools → Options → Expert Advisors and add
                    <code className="bg-slate-800 px-1.5 py-0.5 rounded mx-1 text-xs">{API?.replace('/api', '')}</code>
                    to the allowed URLs list.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* MT5 EA Download */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-green-400" />
                  MetaTrader 5 Expert Advisor
                </CardTitle>
                <CardDescription>Download and install the EA for MT5 signal execution</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Features</h3>
                    <ul className="text-slate-300 text-sm space-y-1.5">
                      <li className="flex items-center gap-2"><Check className="w-3 h-3 text-emerald-400" /> Native MT5 Trade library integration</li>
                      <li className="flex items-center gap-2"><Check className="w-3 h-3 text-emerald-400" /> Supports all MT5 order filling types</li>
                      <li className="flex items-center gap-2"><Check className="w-3 h-3 text-emerald-400" /> Auto symbol normalization</li>
                      <li className="flex items-center gap-2"><Check className="w-3 h-3 text-emerald-400" /> Detailed trade logging</li>
                    </ul>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Installation</h3>
                    <ol className="text-slate-300 text-sm space-y-1.5 list-decimal list-inside">
                      <li>Download the EA file below</li>
                      <li>Copy to MT5/Experts folder</li>
                      <li>Compile in MetaEditor</li>
                      <li>Drag EA onto a chart</li>
                      <li>Configure WebRequest URLs</li>
                      <li>Enable Algo Trading</li>
                    </ol>
                  </div>
                </div>
                <div className="flex gap-3">
                  <a href="/downloads/GPT_Signal_Bot_EA_MT5.mq5" download>
                    <Button className="bg-green-600 hover:bg-green-700">Download MT5 EA (.mq5)</Button>
                  </a>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ==================== TRADINGVIEW TAB ==================== */}
          <TabsContent value="tradingview" className="space-y-6">
            {/* Webhook URL + Test */}
            <Card className="bg-slate-800/50 border-slate-700" data-testid="tv-webhook-card">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Zap className="w-5 h-5 text-purple-400" />
                  TradingView Webhook
                </CardTitle>
                <CardDescription>Receive alerts from TradingView strategies and route to MT5 or Pocket Option</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Webhook URL */}
                <div>
                  <Label className="text-slate-400 text-xs mb-1 block">Your Webhook URL</Label>
                  <div className="flex gap-2">
                    <code data-testid="tv-webhook-url" className="flex-1 bg-slate-900 text-purple-400 p-3 rounded text-sm border border-slate-700 overflow-x-auto">{webhookUrl}</code>
                    <Button onClick={() => copyToClipboard(webhookUrl, 'webhook')} className="bg-purple-600 hover:bg-purple-700">
                      {copied === 'webhook' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </Button>
                  </div>
                </div>

                {/* Live Test */}
                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                  <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                    <Send className="w-4 h-4 text-cyan-400" /> Test Webhook
                  </h3>
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div>
                      <Label className="text-slate-400 text-xs">Symbol</Label>
                      <Input data-testid="tv-test-symbol" value={tvTestSymbol} onChange={e => setTvTestSymbol(e.target.value)} className="bg-slate-800 border-slate-700 text-white" />
                    </div>
                    <div>
                      <Label className="text-slate-400 text-xs">Action</Label>
                      <select data-testid="tv-test-action" value={tvTestAction} onChange={e => setTvTestAction(e.target.value)} className="w-full h-9 bg-slate-800 border border-slate-700 text-white rounded-md px-3 text-sm">
                        <option value="buy">BUY / CALL</option>
                        <option value="sell">SELL / PUT</option>
                      </select>
                    </div>
                    <div className="flex items-end">
                      <Button data-testid="tv-test-send-btn" onClick={testTVWebhook} disabled={loading.tvTest} className="bg-cyan-600 hover:bg-cyan-700 w-full">
                        {loading.tvTest ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
                        Send Test
                      </Button>
                    </div>
                  </div>
                  {tvTestResult && (
                    <div data-testid="tv-test-result" className={`p-3 rounded text-sm ${tvTestResult.success ? 'bg-emerald-900/30 border border-emerald-500/30 text-emerald-300' : 'bg-red-900/30 border border-red-500/30 text-red-300'}`}>
                      {tvTestResult.success ? (
                        <>Alert ID: {tvTestResult.alert?.alert_id} | Status: {tvTestResult.alert?.execution_status} | Symbol: {tvTestResult.alert?.symbol}</>
                      ) : (
                        <>Error: {tvTestResult.error || 'Test failed'}</>
                      )}
                    </div>
                  )}
                </div>

                {/* Stats */}
                {tvStats && (
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-slate-900 rounded-lg p-3 text-center border border-slate-700">
                      <div className="text-2xl font-bold text-purple-400">{tvStats.total_alerts}</div>
                      <div className="text-xs text-slate-400">Total Alerts</div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-3 text-center border border-slate-700">
                      <div className="text-2xl font-bold text-emerald-400">{tvStats.valid_alerts}</div>
                      <div className="text-xs text-slate-400">Valid</div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-3 text-center border border-slate-700">
                      <div className="text-2xl font-bold text-cyan-400">{tvStats.executed_alerts}</div>
                      <div className="text-xs text-slate-400">Executed</div>
                    </div>
                  </div>
                )}

                {/* Alert History */}
                {tvHistory.length > 0 && (
                  <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                    <h3 className="text-white font-medium mb-2">Recent Alerts</h3>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {tvHistory.map((a, i) => (
                        <div key={i} className="flex items-center justify-between text-xs bg-slate-800 rounded px-3 py-2">
                          <span className="text-slate-300">{a.symbol}</span>
                          <Badge className={a.action?.toLowerCase().includes('buy') || a.action?.toLowerCase().includes('call') ? 'bg-emerald-600' : 'bg-red-600'}>{a.action}</Badge>
                          <span className="text-slate-500">{a.execution_status}</span>
                          <span className="text-slate-600">{new Date(a.timestamp).toLocaleTimeString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Setup + Pine Script */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Setup Instructions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <ol className="text-slate-300 text-sm space-y-2 list-decimal list-inside">
                  <li>Open TradingView and go to your chart</li>
                  <li>Add your strategy or indicator</li>
                  <li>Click "Alert" button (clock icon) or press Alt+A</li>
                  <li>Set condition to your strategy</li>
                  <li>Check "Webhook URL" and paste: <code className="bg-slate-800 px-1 rounded text-purple-400">{webhookUrl}</code></li>
                  <li>In "Message", use the JSON format below</li>
                  <li>Create alert — signals will flow to Pocket Option or MT5</li>
                </ol>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="text-white font-medium text-sm">Alert JSON Format</h3>
                    <Button size="sm" variant="outline" className="border-slate-600 h-7 text-xs" onClick={() => copyToClipboard(webhookJson, 'json')}>
                      {copied === 'json' ? 'Copied' : 'Copy'}
                    </Button>
                  </div>
                  <pre className="bg-slate-900 text-green-400 p-3 rounded text-xs overflow-x-auto border border-slate-700">{webhookJson}</pre>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="text-white font-medium text-sm">Pine Script Template</h3>
                    <Button size="sm" variant="outline" className="border-slate-600 h-7 text-xs" onClick={() => copyToClipboard(pineScript, 'pine')}>
                      {copied === 'pine' ? 'Copied' : 'Copy'}
                    </Button>
                  </div>
                  <pre className="bg-slate-900 text-blue-400 p-3 rounded text-xs overflow-x-auto max-h-48 border border-slate-700">{pineScript}</pre>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ==================== API REFERENCE TAB ==================== */}
          <TabsContent value="api" className="space-y-6">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">API Endpoints Reference</CardTitle>
                <CardDescription>Direct API access for custom integrations</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  { title: 'Signal Endpoints', endpoints: [
                    { method: 'GET', path: '/api/signals/scan-markets?assets=EURUSD_OTC', desc: 'Scan markets for signals' },
                    { method: 'POST', path: '/api/signals/iq720-ensemble', desc: 'IQ-720 Advanced Ensemble signal' },
                    { method: 'GET', path: '/api/signals/iq720-market-regime', desc: 'Market regime detection' },
                    { method: 'POST', path: '/api/signals/iq720-kelly', desc: 'Kelly Criterion position sizing' },
                    { method: 'POST', path: '/api/signals/keltner-macd-5s', desc: 'Keltner-MACD 5s strategy' },
                  ]},
                  { title: 'TradingView Endpoints', endpoints: [
                    { method: 'POST', path: '/api/tradingview/webhook', desc: 'Receive TradingView alerts' },
                    { method: 'GET', path: '/api/tradingview/history', desc: 'Alert history' },
                    { method: 'GET', path: '/api/tradingview/stats', desc: 'Alert statistics' },
                    { method: 'GET', path: '/api/tradingview/pine-script', desc: 'Pine Script template' },
                  ]},
                  { title: 'MetaTrader Endpoints', endpoints: [
                    { method: 'GET', path: '/api/mt5/status', desc: 'MT5 connection status' },
                    { method: 'POST', path: '/api/mt5/connect', desc: 'Connect to MT5' },
                    { method: 'POST', path: '/api/mt5/disconnect', desc: 'Disconnect MT5' },
                    { method: 'GET', path: '/api/mt5/account', desc: 'MT5 account info' },
                    { method: 'POST', path: '/api/mt5/order', desc: 'Execute MT5 order' },
                    { method: 'POST', path: '/api/mt4/trade-report', desc: 'Receive MT4 EA trade reports' },
                  ]},
                ].map(section => (
                  <div key={section.title} className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                    <h3 className="text-white font-medium mb-3">{section.title}</h3>
                    <div className="space-y-2 text-sm">
                      {section.endpoints.map((ep, i) => (
                        <div key={i} className="flex items-start gap-3">
                          <Badge className={ep.method === 'GET' ? 'bg-emerald-600' : 'bg-blue-600'}>{ep.method}</Badge>
                          <div>
                            <code className="text-purple-400">{ep.path}</code>
                            <p className="text-slate-400 text-xs mt-0.5">{ep.desc}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
                <div className="bg-purple-900/30 border border-purple-600/50 rounded-lg p-3">
                  <p className="text-purple-200 text-sm">
                    <strong>Base URL:</strong> <code className="bg-slate-800 px-1.5 py-0.5 rounded ml-1 text-xs">{API}</code>
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default IntegrationsPage;
