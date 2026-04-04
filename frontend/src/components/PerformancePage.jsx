import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import SignalStatistics from './SignalStatistics';
import BacktestingPage from './BacktestingPage';
import AnalyticsDashboard from './AnalyticsDashboard';

const PerformancePage = () => {
  const [activeTab, setActiveTab] = useState('statistics');

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <span className="text-purple-400">Performance Center</span>
          </h1>
          <p className="text-slate-400 text-sm">Track signal accuracy, run backtests, and analyze ML model performance</p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3 bg-slate-800/50 max-w-lg">
          <TabsTrigger value="statistics" className="data-[state=active]:bg-purple-600" data-testid="tab-statistics">
            Statistics
          </TabsTrigger>
          <TabsTrigger value="backtest" className="data-[state=active]:bg-purple-600" data-testid="tab-backtest">
            Backtesting
          </TabsTrigger>
          <TabsTrigger value="analytics" className="data-[state=active]:bg-purple-600" data-testid="tab-analytics">
            Analytics
          </TabsTrigger>
        </TabsList>

        <TabsContent value="statistics" className="mt-6">
          <SignalStatistics />
        </TabsContent>

        <TabsContent value="backtest" className="mt-6">
          <BacktestingPage />
        </TabsContent>

        <TabsContent value="analytics" className="mt-6">
          <AnalyticsDashboard />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default PerformancePage;
