import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import TampermonkeyControlPanel from './TampermonkeyControlPanel';

const API = process.env.REACT_APP_BACKEND_URL;

const MobileAutoTraderPage = () => {
  const [copied, setCopied] = useState(false);
  const [showSetup, setShowSetup] = useState(false);

  const userscriptUrl = `${API.replace('/api', '')}/pocket-option-auto-trader.user.js`;
  const modularScriptUrl = `${API.replace('/api', '')}/pocket-option-auto-trader-modular.user.js`;

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
            📱 Mobile Auto-Trader
          </h1>
          <p className="text-slate-400">
            Run automated trading on your Android phone using your residential IP
          </p>
          <Badge className="mt-2 bg-green-600">Bypasses Cloud IP Block</Badge>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6">
          <Button
            onClick={() => setShowSetup(false)}
            className={!showSetup ? 'bg-purple-600' : 'bg-slate-700'}
          >
            🎮 Control Panel
          </Button>
          <Button
            onClick={() => setShowSetup(true)}
            className={showSetup ? 'bg-purple-600' : 'bg-slate-700'}
          >
            📖 Setup Guide
          </Button>
        </div>

        {/* Control Panel or Setup Guide */}
        {!showSetup ? (
          <TampermonkeyControlPanel />
        ) : (
          <>
            {/* Why This Works */}
        <Card className="bg-slate-800/50 border-slate-700 mb-6">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              ✅ Why This Works
            </CardTitle>
          </CardHeader>
          <CardContent className="text-slate-300">
            <p className="mb-4">
              Pocket Option blocks cloud/datacenter IPs, but <strong>your phone uses a residential IP</strong> from your mobile carrier or WiFi. By running the auto-trader on your phone:
            </p>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li>Trades execute from <strong>your IP address</strong> (not blocked)</li>
              <li>Signals come from our cloud server (analysis & strategy)</li>
              <li>Your phone clicks the buttons automatically</li>
              <li>Works 24/7 while your phone is on and browser is open</li>
            </ul>
          </CardContent>
        </Card>

        {/* Step by Step Guide */}
        <div className="space-y-4">
          {/* Step 1 */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white">
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-purple-600 mr-3">1</span>
                Install Firefox Nightly
              </CardTitle>
            </CardHeader>
            <CardContent className="text-slate-300">
              <p className="mb-4">Download Firefox Nightly from the Google Play Store. It's a Firefox browser that supports userscript extensions like Tampermonkey.</p>
              <a 
                href="https://play.google.com/store/apps/details?id=org.mozilla.fenix" 
                target="_blank" 
                rel="noopener noreferrer"
              >
                <Button className="bg-orange-600 hover:bg-orange-700">
                  📥 Download Firefox Nightly
                </Button>
              </a>
            </CardContent>
          </Card>

          {/* Step 2 */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white">
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-purple-600 mr-3">2</span>
                Install Tampermonkey Extension
              </CardTitle>
            </CardHeader>
            <CardContent className="text-slate-300">
              <ol className="list-decimal list-inside space-y-2 mb-4">
                <li>Open Firefox Nightly</li>
                <li>Go to about:addons (type in address bar)</li>
                <li>Tap the gear icon → "Install Add-on From File"</li>
                <li>Or visit the Firefox Add-ons site and search for "Tampermonkey"</li>
              </ol>
              <a 
                href="https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/" 
                target="_blank" 
                rel="noopener noreferrer"
              >
                <Button variant="outline" className="border-purple-500 text-purple-400">
                  🔧 Get Tampermonkey for Firefox
                </Button>
              </a>
            </CardContent>
          </Card>

          {/* Step 3 */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white">
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-purple-600 mr-3">3</span>
                Install Auto-Trader Script
              </CardTitle>
            </CardHeader>
            <CardContent className="text-slate-300">
              <p className="mb-4">Install the recommended modular script below. The legacy monolithic version is kept only for emergency rollback.</p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                <div className="p-3 bg-slate-900/60 rounded-lg border border-indigo-500/40 ring-1 ring-indigo-500/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className="bg-indigo-600 text-white text-xs">Modular v8.9.0</Badge>
                    <Badge className="bg-emerald-700 text-white text-[10px]">RECOMMENDED</Badge>
                  </div>
                  <p className="text-xs text-slate-400 mb-2">Webpack-bundled modular build — 7 strategies + <strong className="text-purple-300">21-Second Reversal</strong>, clean architecture, active maintenance</p>
                  <a href={modularScriptUrl} target="_blank" rel="noopener noreferrer">
                    <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 w-full" data-testid="tm-install-modular-btn">
                      Install Modular Script
                    </Button>
                  </a>
                </div>
                <div className="p-3 bg-slate-900/40 rounded-lg border border-slate-700/60 opacity-70">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className="bg-slate-600 text-slate-200 text-xs">Legacy v8.8.1</Badge>
                    <Badge className="bg-amber-700/80 text-white text-[10px]">DEPRECATED</Badge>
                  </div>
                  <p className="text-xs text-slate-500 mb-2">Monolithic script — retained for rollback only. No new features.</p>
                  <a href={userscriptUrl} target="_blank" rel="noopener noreferrer">
                    <Button size="sm" variant="outline" className="border-slate-600 text-slate-400 hover:text-slate-200 w-full" data-testid="tm-install-legacy-btn">
                      Install Legacy (Rollback)
                    </Button>
                  </a>
                </div>
              </div>

              <p className="text-sm text-slate-400">
                Or copy the recommended URL and paste in Tampermonkey → Add New Script:
              </p>
              <div className="flex items-center gap-2 mt-2">
                <code className="bg-slate-900 px-3 py-2 rounded text-xs flex-1 overflow-x-auto">
                  {modularScriptUrl}
                </code>
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={() => copyToClipboard(modularScriptUrl)}
                  className="border-slate-600"
                  data-testid="tm-copy-modular-url-btn"
                >
                  {copied ? 'OK' : 'Copy'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Step 4 */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white">
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-purple-600 mr-3">4</span>
                Enable Desktop Mode & Login to Pocket Option
              </CardTitle>
            </CardHeader>
            <CardContent className="text-slate-300">
              <ol className="list-decimal list-inside space-y-2">
                <li>In Kiwi Browser, go to <strong>pocketoption.com</strong></li>
                <li>Tap the 3 dots menu (⋮) → Check <strong>"Desktop site"</strong></li>
                <li>Login to your Pocket Option account</li>
                <li>Navigate to the trading page</li>
                <li>You should see the <strong>"GPT Signal Bot"</strong> control panel in the top-right corner</li>
              </ol>
            </CardContent>
          </Card>

          {/* Step 5 */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white">
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-purple-600 mr-3">5</span>
                Start Auto-Trading!
              </CardTitle>
            </CardHeader>
            <CardContent className="text-slate-300">
              <ol className="list-decimal list-inside space-y-2 mb-4">
                <li>Make sure <strong>"AUTO-TRADE ON"</strong> is green in the control panel</li>
                <li>Set your trade amount on Pocket Option</li>
                <li>Generate signals from this app (Dashboard → Generate Signal)</li>
                <li>The script will automatically click CALL/PUT when a signal arrives!</li>
              </ol>
              <div className="bg-yellow-900/30 border border-yellow-600 rounded-lg p-4 mt-4">
                <p className="text-yellow-400 font-medium">⚠️ Important Tips:</p>
                <ul className="text-sm text-yellow-200 mt-2 space-y-1">
                  <li>• Keep Kiwi Browser open and screen on (use caffeine app)</li>
                  <li>• Disable battery optimization for Kiwi Browser</li>
                  <li>• Make sure you're on the trading chart page</li>
                  <li>• Start with DEMO mode to test everything works</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Control Panel Preview */}
        <Card className="bg-slate-800/50 border-slate-700 mt-6">
          <CardHeader>
            <CardTitle className="text-white">📱 Panel Preview (v8.8.0)</CardTitle>
            <CardDescription>The auto-trader control panel on Pocket Option</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-gradient-to-br from-slate-900 to-purple-900/50 border-2 border-purple-600 rounded-xl p-4 max-w-xs">
              <div className="flex justify-between items-center border-b border-purple-600 pb-2 mb-3">
                <span className="text-purple-400 font-bold text-sm">Elite PO Trading Bot</span>
                <span className="text-slate-400">−</span>
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Status:</span>
                  <span className="text-green-400">Connected</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Win/Loss:</span>
                  <span><span className="text-green-400">9</span> / <span className="text-red-400">3</span></span>
                </div>
              </div>
              <div className="flex gap-1 mt-2">
                <button className="flex-1 py-1.5 bg-slate-700 text-white text-[10px] font-bold rounded">AUTO</button>
                <button className="flex-1 py-1.5 bg-blue-600 text-white text-[10px] font-bold rounded">SCAN</button>
                <button className="flex-1 py-1.5 bg-purple-600 text-white text-[10px] font-bold rounded">GO</button>
              </div>
              <div className="flex gap-1 mt-1">
                <button className="flex-1 py-1.5 bg-sky-600 text-white text-[10px] font-bold rounded">CYCLE</button>
                <button className="flex-1 py-1.5 bg-cyan-600 text-white text-[10px] font-bold rounded">KC-5s</button>
                <button className="flex-1 py-1.5 bg-indigo-600 text-white text-[10px] font-bold rounded">LOG</button>
              </div>
              <div className="bg-slate-800 rounded-lg p-2 mt-2 text-xs">
                <div className="text-green-400 font-bold">CALL (UP)</div>
                <div className="text-slate-400">EUR/USD OTC | 78% [IQ-720]</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Strategies Available */}
        <Card className="bg-slate-800/50 border-slate-700 mt-6" data-testid="tm-strategies-card">
          <CardHeader>
            <CardTitle className="text-white">Local Signal Strategies (v8.9.0)</CardTitle>
            <CardDescription>These strategies run locally on the Pocket Option page using scraped OTC prices — no backend needed</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                { name: '⭐⭐⭐ 21-Second Reversal', desc: 'Fires OPPOSITE 5s trade at 21s-left on 1m candle. Wick-ignored body direction. 1-candle cooldown. Enable via "21S" button in TM panel.', badge: '1m→5s exp', color: 'bg-purple-600' },
                { name: 'General Multi-Indicator', desc: 'RSI-2/14, MACD, Stochastic, Bollinger, EMA alignment, ADX, Candlestick patterns', badge: 'Primary', color: 'bg-purple-600' },
                { name: 'Keltner-MACD 5s', desc: 'Keltner Channel (EMA20, ATR60, x4) + MACD (13/24/11) crossover for 5-second scalps', badge: '5s', color: 'bg-cyan-600' },
                { name: 'IQ-720 Ensemble', desc: '8 weighted sub-strategies + market regime detection + session awareness + confidence calibration', badge: 'Advanced', color: 'bg-indigo-600' },
                { name: 'Holly Crossover', desc: 'EMA(12) x WMA(23) reversal crossover with support/resistance confirmation', badge: '5s/15s/30s', color: 'bg-emerald-600' },
                { name: 'Golden One Moment', desc: 'RSI(2) + Stochastic(4,3,3) mean reversion from oversold/overbought zones', badge: '30s', color: 'bg-amber-600' },
                { name: 'Momentum Buster', desc: 'Momentum period 3 — green/red bars with confirmation signals', badge: '15s', color: 'bg-orange-600' },
              ].map(s => (
                <div key={s.name} className="p-3 bg-slate-900/60 rounded-lg border border-slate-700/50">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-white">{s.name}</span>
                    <Badge className={`text-[10px] ${s.color} text-white`}>{s.badge}</Badge>
                  </div>
                  <p className="text-xs text-slate-400">{s.desc}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 p-3 bg-blue-900/20 border border-blue-600/30 rounded-lg">
              <p className="text-xs text-blue-300">
                <strong>Signal Priority Chain:</strong> General → Keltner-MACD → IQ-720 Ensemble → Holly Crossover → Golden One Moment → Momentum Buster. 
                If all local strategies fail, the GO button falls back to backend API (scan-markets → force-generate).
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Troubleshooting */}
        <Card className="bg-slate-800/50 border-slate-700 mt-6">
          <CardHeader>
            <CardTitle className="text-white">🔧 Troubleshooting</CardTitle>
          </CardHeader>
          <CardContent className="text-slate-300">
            <div className="space-y-4">
              <div>
                <p className="font-medium text-white">Panel not showing?</p>
                <p className="text-sm text-slate-400">Make sure Tampermonkey is enabled and the script is active. Check the Tampermonkey icon for any errors.</p>
              </div>
              <div>
                <p className="font-medium text-white">Trades not executing?</p>
                <p className="text-sm text-slate-400">Make sure you're on the trading chart page (not homepage). The script needs to find the CALL/PUT buttons.</p>
              </div>
              <div>
                <p className="font-medium text-white">Screen turning off?</p>
                <p className="text-sm text-slate-400">Install a "Caffeine" or "Keep Screen On" app from Play Store. Also disable battery optimization for Kiwi Browser.</p>
              </div>
            </div>
          </CardContent>
        </Card>
          </>
        )}
      </div>
    </div>
  );
};

export default MobileAutoTraderPage;
