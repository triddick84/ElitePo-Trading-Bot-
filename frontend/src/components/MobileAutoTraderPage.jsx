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
              <p className="mb-4">Click the button below to install the auto-trader userscript:</p>
              <a href={userscriptUrl} target="_blank" rel="noopener noreferrer">
                <Button className="bg-purple-600 hover:bg-purple-700 mr-2 mb-2">
                  📜 Install Auto-Trader Script
                </Button>
              </a>
              <p className="text-sm text-slate-400 mt-2">
                Or copy this URL and paste in Tampermonkey → Add New Script:
              </p>
              <div className="flex items-center gap-2 mt-2">
                <code className="bg-slate-900 px-3 py-2 rounded text-xs flex-1 overflow-x-auto">
                  {userscriptUrl}
                </code>
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={() => copyToClipboard(userscriptUrl)}
                  className="border-slate-600"
                >
                  {copied ? '✓' : '📋'}
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
            <CardTitle className="text-white">📱 What You'll See</CardTitle>
            <CardDescription>The auto-trader control panel appears on Pocket Option</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-gradient-to-br from-slate-900 to-purple-900/50 border-2 border-purple-600 rounded-xl p-4 max-w-xs">
              <div className="flex justify-between items-center border-b border-purple-600 pb-2 mb-3">
                <span className="text-purple-400 font-bold text-sm">🤖 GPT Signal Bot</span>
                <span className="text-slate-400">−</span>
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Status:</span>
                  <span className="text-green-400">● Connected</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Trades:</span>
                  <span className="text-white">12</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Win/Loss:</span>
                  <span><span className="text-green-400">9</span> / <span className="text-red-400">3</span></span>
                </div>
              </div>
              <button className="w-full mt-3 py-2 bg-green-600 text-white text-sm font-bold rounded-lg">
                🟢 AUTO-TRADE ON
              </button>
              <div className="bg-slate-800 rounded-lg p-2 mt-3 text-xs">
                <div className="text-green-400 font-bold">📈 CALL (UP)</div>
                <div className="text-slate-400">EURUSD | 92% confidence</div>
              </div>
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
