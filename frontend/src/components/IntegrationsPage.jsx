import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

const API = process.env.REACT_APP_BACKEND_URL;

const IntegrationsPage = () => {
  const [tradingViewStatus, setTradingViewStatus] = useState(null);
  const [mt5Status, setMt5Status] = useState(null);
  const [pineScript, setPineScript] = useState('');
  const [copied, setCopied] = useState('');

  const webhookUrl = `${API}/api/tradingview/webhook`;

  useEffect(() => {
    fetchStatuses();
  }, []);

  const fetchStatuses = async () => {
    try {
      const [tvRes, mt5Res] = await Promise.all([
        fetch(`${API}/api/tradingview/status`).then(r => r.json()).catch(() => null),
        fetch(`${API}/api/mt5/status`).then(r => r.json()).catch(() => null)
      ]);
      setTradingViewStatus(tvRes);
      setMt5Status(mt5Res);
    } catch (e) {
      console.error('Error fetching statuses:', e);
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(''), 2000);
  };

  const tradingViewPineScript = `
//@version=5
strategy("GPT Signal Bot Alerts", overlay=true)

// Your strategy logic here
longCondition = ta.crossover(ta.sma(close, 14), ta.sma(close, 28))
shortCondition = ta.crossunder(ta.sma(close, 14), ta.sma(close, 28))

if (longCondition)
    strategy.entry("Long", strategy.long)
    alert('{"action": "BUY", "symbol": "' + syminfo.ticker + '", "price": ' + str.tostring(close) + ', "timestamp": "' + str.tostring(timenow) + '"}', alert.freq_once_per_bar)

if (shortCondition)
    strategy.entry("Short", strategy.short)
    alert('{"action": "SELL", "symbol": "' + syminfo.ticker + '", "price": ' + str.tostring(close) + ', "timestamp": "' + str.tostring(timenow) + '"}', alert.freq_once_per_bar)
`.trim();

  const webhookJsonFormat = `{
  "action": "BUY",
  "symbol": "EURUSD",
  "price": 1.0850,
  "stop_loss": 1.0800,
  "take_profit": 1.0900,
  "lot_size": 0.01,
  "comment": "TradingView Alert"
}`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
            Platform Integrations
          </h1>
          <p className="text-slate-400">
            Connect GPT Signal Bot with MetaTrader 4, MetaTrader 5, and TradingView
          </p>
        </div>

        <Tabs defaultValue="metatrader" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 bg-slate-800">
            <TabsTrigger value="metatrader" className="data-[state=active]:bg-purple-600">
              MetaTrader 4/5
            </TabsTrigger>
            <TabsTrigger value="tradingview" className="data-[state=active]:bg-purple-600">
              TradingView
            </TabsTrigger>
            <TabsTrigger value="api" className="data-[state=active]:bg-purple-600">
              API Reference
            </TabsTrigger>
          </TabsList>

          {/* MetaTrader Tab */}
          <TabsContent value="metatrader" className="space-y-6">
            {/* MT4 Section */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-3">
                  <span className="text-2xl">📊</span>
                  MetaTrader 4 Expert Advisor
                </CardTitle>
                <CardDescription>
                  Download and install the EA to receive signals directly in MT4
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Features</h3>
                    <ul className="text-slate-300 text-sm space-y-2">
                      <li>✅ Auto-receives signals from GPT Signal Bot</li>
                      <li>✅ Configurable lot size, SL, TP</li>
                      <li>✅ Magic number for trade identification</li>
                      <li>✅ Auto-trade or alert-only mode</li>
                      <li>✅ Reports trades back to server</li>
                    </ul>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Installation</h3>
                    <ol className="text-slate-300 text-sm space-y-2 list-decimal list-inside">
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
                    <Button className="bg-blue-600 hover:bg-blue-700">
                      📥 Download MT4 EA (.mq4)
                    </Button>
                  </a>
                  <Button 
                    variant="outline" 
                    className="border-slate-600"
                    onClick={() => copyToClipboard(API, 'mt4-api')}
                  >
                    {copied === 'mt4-api' ? '✓ Copied!' : '📋 Copy API URL'}
                  </Button>
                </div>

                <div className="bg-yellow-900/30 border border-yellow-600 rounded-lg p-4">
                  <p className="text-yellow-200 text-sm">
                    <strong>Important:</strong> In MT4, go to Tools → Options → Expert Advisors and add 
                    <code className="bg-slate-800 px-2 py-1 rounded mx-1">{API?.replace('/api', '')}</code>
                    to the list of allowed URLs.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* MT5 Section */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-3">
                  <span className="text-2xl">📈</span>
                  MetaTrader 5 Expert Advisor
                </CardTitle>
                <CardDescription>
                  Download and install the EA to receive signals directly in MT5
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Features</h3>
                    <ul className="text-slate-300 text-sm space-y-2">
                      <li>✅ Native MT5 Trade library integration</li>
                      <li>✅ Supports all MT5 order filling types</li>
                      <li>✅ Auto symbol normalization</li>
                      <li>✅ Configurable parameters</li>
                      <li>✅ Detailed trade logging</li>
                    </ul>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Installation</h3>
                    <ol className="text-slate-300 text-sm space-y-2 list-decimal list-inside">
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
                    <Button className="bg-green-600 hover:bg-green-700">
                      📥 Download MT5 EA (.mq5)
                    </Button>
                  </a>
                  <Button 
                    variant="outline" 
                    className="border-slate-600"
                    onClick={() => copyToClipboard(API, 'mt5-api')}
                  >
                    {copied === 'mt5-api' ? '✓ Copied!' : '📋 Copy API URL'}
                  </Button>
                </div>

                {mt5Status && (
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-2">Connection Status</h3>
                    <div className="flex items-center gap-2">
                      <span className={`w-3 h-3 rounded-full ${mt5Status.connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
                      <span className="text-slate-300">{mt5Status.connected ? 'Connected' : 'Not Connected'}</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* TradingView Tab */}
          <TabsContent value="tradingview" className="space-y-6">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-3">
                  <span className="text-2xl">📺</span>
                  TradingView Webhook Integration
                </CardTitle>
                <CardDescription>
                  Receive alerts from TradingView strategies and indicators
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Webhook URL */}
                <div className="bg-slate-900 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Your Webhook URL</h3>
                  <div className="flex gap-2">
                    <code className="flex-1 bg-slate-800 text-purple-400 p-3 rounded text-sm overflow-x-auto">
                      {webhookUrl}
                    </code>
                    <Button 
                      onClick={() => copyToClipboard(webhookUrl, 'webhook')}
                      className="bg-purple-600 hover:bg-purple-700"
                    >
                      {copied === 'webhook' ? '✓ Copied!' : 'Copy'}
                    </Button>
                  </div>
                </div>

                {/* Setup Steps */}
                <div className="bg-slate-900 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Setup Instructions</h3>
                  <ol className="text-slate-300 text-sm space-y-3 list-decimal list-inside">
                    <li>Open TradingView and go to your chart</li>
                    <li>Add your strategy or indicator</li>
                    <li>Click "Alert" button (clock icon) or press Alt+A</li>
                    <li>Set condition to your strategy</li>
                    <li>Check "Webhook URL" and paste the URL above</li>
                    <li>In "Message", use the JSON format below</li>
                    <li>Create alert</li>
                  </ol>
                </div>

                {/* JSON Format */}
                <div className="bg-slate-900 rounded-lg p-4">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-white font-medium">Alert Message Format (JSON)</h3>
                    <Button 
                      size="sm"
                      variant="outline"
                      className="border-slate-600"
                      onClick={() => copyToClipboard(webhookJsonFormat, 'json')}
                    >
                      {copied === 'json' ? '✓ Copied!' : 'Copy'}
                    </Button>
                  </div>
                  <pre className="bg-slate-800 text-green-400 p-4 rounded text-sm overflow-x-auto">
                    {webhookJsonFormat}
                  </pre>
                </div>

                {/* Pine Script Template */}
                <div className="bg-slate-900 rounded-lg p-4">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-white font-medium">Sample Pine Script</h3>
                    <Button 
                      size="sm"
                      variant="outline"
                      className="border-slate-600"
                      onClick={() => copyToClipboard(tradingViewPineScript, 'pine')}
                    >
                      {copied === 'pine' ? '✓ Copied!' : 'Copy'}
                    </Button>
                  </div>
                  <pre className="bg-slate-800 text-blue-400 p-4 rounded text-sm overflow-x-auto max-h-64">
                    {tradingViewPineScript}
                  </pre>
                </div>

                {tradingViewStatus && (
                  <div className="bg-slate-900 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-2">Recent Activity</h3>
                    <p className="text-slate-400 text-sm">
                      Total alerts received: {tradingViewStatus.total_alerts || 0}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* API Reference Tab */}
          <TabsContent value="api" className="space-y-6">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">API Endpoints Reference</CardTitle>
                <CardDescription>
                  Direct API access for custom integrations
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Signals Endpoints */}
                <div className="bg-slate-900 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Signal Endpoints</h3>
                  <div className="space-y-3 text-sm">
                    <div className="flex items-start gap-3">
                      <Badge className="bg-green-600">GET</Badge>
                      <div>
                        <code className="text-purple-400">/api/signals/latest</code>
                        <p className="text-slate-400 mt-1">Get the latest trading signal</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Badge className="bg-green-600">GET</Badge>
                      <div>
                        <code className="text-purple-400">/api/signals/scan-markets?assets=EURUSD_OTC</code>
                        <p className="text-slate-400 mt-1">Scan markets for signals</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Badge className="bg-blue-600">POST</Badge>
                      <div>
                        <code className="text-purple-400">/api/tampermonkey/force-generate?timeframe=1m</code>
                        <p className="text-slate-400 mt-1">Force generate a signal</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* TradingView Endpoints */}
                <div className="bg-slate-900 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">TradingView Endpoints</h3>
                  <div className="space-y-3 text-sm">
                    <div className="flex items-start gap-3">
                      <Badge className="bg-blue-600">POST</Badge>
                      <div>
                        <code className="text-purple-400">/api/tradingview/webhook</code>
                        <p className="text-slate-400 mt-1">Receive TradingView alerts</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Badge className="bg-green-600">GET</Badge>
                      <div>
                        <code className="text-purple-400">/api/tradingview/history</code>
                        <p className="text-slate-400 mt-1">Get alert history</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* MT4/MT5 Endpoints */}
                <div className="bg-slate-900 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">MetaTrader Endpoints</h3>
                  <div className="space-y-3 text-sm">
                    <div className="flex items-start gap-3">
                      <Badge className="bg-green-600">GET</Badge>
                      <div>
                        <code className="text-purple-400">/api/mt5/status</code>
                        <p className="text-slate-400 mt-1">Get MT5 connection status</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Badge className="bg-blue-600">POST</Badge>
                      <div>
                        <code className="text-purple-400">/api/mt5/order</code>
                        <p className="text-slate-400 mt-1">Execute an order via MT5</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <Badge className="bg-blue-600">POST</Badge>
                      <div>
                        <code className="text-purple-400">/api/mt4/trade-report</code>
                        <p className="text-slate-400 mt-1">Receive trade reports from MT4 EA</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Base URL */}
                <div className="bg-purple-900/30 border border-purple-600 rounded-lg p-4">
                  <p className="text-purple-200 text-sm">
                    <strong>Base URL:</strong> 
                    <code className="bg-slate-800 px-2 py-1 rounded ml-2">{API}</code>
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
