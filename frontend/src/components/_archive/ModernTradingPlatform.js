import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { 
  Settings, BarChart3, TrendingUp, Zap, Radio, 
  Brain, Target, Activity, PieChart, Wifi 
} from 'lucide-react';

// Import page components (we'll create these)
import SignalParametersPage from './pages/SignalParametersPage';
import LiveAnalysisPage from './pages/LiveAnalysisPage';
import PortfolioStatsPage from './pages/PortfolioStatsPage';
import PlatformIntegrationsPage from './pages/PlatformIntegrationsPage';
import BotSettingsPage from './pages/BotSettingsPage';

const ModernTradingPlatform = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [botStatus, setBotStatus] = useState({ is_running: false });
  const [activeSignals, setActiveSignals] = useState([]);
  const [performance, setPerformance] = useState({
    totalSignals: 0,
    winRate: 0,
    accuracy: 0,
    profit: 0
  });

  // Navigation items for the modern platform
  const navigationItems = [
    {
      id: 'parameters',
      path: '/platform/parameters',
      icon: Target,
      label: 'Signal Parameters',
      description: 'Configure markets, timeframes & generation settings',
      gradient: 'from-blue-500 to-cyan-500'
    },
    {
      id: 'analysis',
      path: '/platform/analysis',
      icon: Activity,
      label: 'Live Analysis',
      description: 'Real-time charts, indicators & AI predictions',
      gradient: 'from-green-500 to-emerald-500'
    },
    {
      id: 'portfolio',
      path: '/platform/portfolio',
      icon: PieChart,
      label: 'Portfolio Stats',
      description: 'Performance tracking & signal accuracy',
      gradient: 'from-purple-500 to-pink-500'
    },
    {
      id: 'integrations',
      path: '/platform/integrations',
      icon: Wifi,
      label: 'Integrations',
      description: 'Platform connections & alert services',
      gradient: 'from-orange-500 to-red-500'
    },
    {
      id: 'settings',
      path: '/platform/settings',
      icon: Settings,
      label: 'Bot Settings',
      description: 'Algorithm configuration & fine-tuning',
      gradient: 'from-indigo-500 to-purple-500'
    }
  ];

  useEffect(() => {
    // Fetch initial data
    fetchBotStatus();
    fetchActiveSignals();
    fetchPerformanceStats();

    // Set up intervals for real-time updates
    const statusInterval = setInterval(fetchBotStatus, 5000);
    const signalsInterval = setInterval(fetchActiveSignals, 3000);
    const performanceInterval = setInterval(fetchPerformanceStats, 10000);

    return () => {
      clearInterval(statusInterval);
      clearInterval(signalsInterval);
      clearInterval(performanceInterval);
    };
  }, []);

  const fetchBotStatus = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/bot/status`);
      if (response.ok) {
        const status = await response.json();
        setBotStatus(status);
      }
    } catch (error) {
      console.error('Error fetching bot status:', error);
    }
  };

  const fetchActiveSignals = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/signals/live`);
      if (response.ok) {
        const signals = await response.json();
        setActiveSignals(signals.slice(0, 10)); // Keep last 10 signals
      }
    } catch (error) {
      console.error('Error fetching active signals:', error);
    }
  };

  const fetchPerformanceStats = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/signals/performance`);
      if (response.ok) {
        const stats = await response.json();
        setPerformance(stats);
      }
    } catch (error) {
      console.error('Error fetching performance stats:', error);
    }
  };

  const getCurrentPageId = () => {
    const path = location.pathname;
    return navigationItems.find(item => item.path === path)?.id || 'parameters';
  };

  const currentPageId = getCurrentPageId();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Modern Header */}
      <div className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-xl">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Platform Branding */}
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-xl flex items-center justify-center">
                  <Brain className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-white">AI Signal Pro</h1>
                  <p className="text-xs text-slate-400">Pocket Option Trading Platform</p>
                </div>
              </div>
            </div>

            {/* Real-time Status Indicators */}
            <div className="flex items-center space-x-6">
              {/* Bot Status */}
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${botStatus.is_running ? 'bg-green-500' : 'bg-red-500'} animate-pulse`}></div>
                <span className="text-sm text-slate-300">
                  Bot {botStatus.is_running ? 'Active' : 'Stopped'}
                </span>
              </div>

              {/* Active Signals */}
              <div className="flex items-center space-x-2">
                <Radio className="w-4 h-4 text-cyan-400" />
                <span className="text-sm text-slate-300">
                  {activeSignals.length} Active
                </span>
              </div>

              {/* Win Rate */}
              <div className="flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <span className="text-sm text-slate-300">
                  {performance.winRate.toFixed(1)}% Win Rate
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-700/30 bg-slate-800/50">
        <div className="px-6">
          <nav className="flex space-x-8 overflow-x-auto">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPageId === item.id;
              
              return (
                <button
                  key={item.id}
                  onClick={() => navigate(item.path)}
                  className={`
                    flex items-center space-x-3 px-4 py-4 border-b-2 transition-all duration-200 whitespace-nowrap
                    ${isActive 
                      ? 'border-cyan-500 text-cyan-400' 
                      : 'border-transparent text-slate-400 hover:text-slate-300 hover:border-slate-500'}
                  `}
                >
                  <Icon className="w-5 h-5" />
                  <div className="text-left">
                    <div className="font-semibold text-sm">{item.label}</div>
                    <div className="text-xs opacity-75 hidden sm:block">{item.description}</div>
                  </div>
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1">
        <Routes>
          <Route 
            path="/platform/parameters" 
            element={
              <SignalParametersPage 
                botStatus={botStatus}
                onBotStatusChange={setBotStatus}
              />
            } 
          />
          <Route 
            path="/platform/analysis" 
            element={
              <LiveAnalysisPage 
                botStatus={botStatus}
                activeSignals={activeSignals}
                setActiveSignals={setActiveSignals}
              />
            } 
          />
          <Route 
            path="/platform/portfolio" 
            element={
              <PortfolioStatsPage 
                performance={performance}
                activeSignals={activeSignals}
              />
            } 
          />
          <Route 
            path="/platform/integrations" 
            element={
              <PlatformIntegrationsPage 
                botStatus={botStatus}
              />
            } 
          />
          <Route 
            path="/platform/settings" 
            element={
              <BotSettingsPage 
                botStatus={botStatus}
                onBotStatusChange={setBotStatus}
              />
            } 
          />
          {/* Default redirect to parameters */}
          <Route path="/platform/*" element={<SignalParametersPage botStatus={botStatus} onBotStatusChange={setBotStatus} />} />
        </Routes>
      </div>

      {/* Global Status Bar */}
      <div className="border-t border-slate-700/30 bg-slate-900/80 backdrop-blur-xl">
        <div className="px-6 py-2">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-4">
              <span className="text-slate-400">
                Connected to Pocket Option • Chicago Timezone
              </span>
              {botStatus.current_asset && (
                <span className="text-cyan-400">
                  Current: {botStatus.current_asset}
                </span>
              )}
            </div>
            
            <div className="flex items-center space-x-4">
              <span className="text-slate-400">
                Last Update: {new Date().toLocaleTimeString()}
              </span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-green-400">Live Data</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ModernTradingPlatform;