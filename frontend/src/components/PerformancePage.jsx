import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import SignalStatistics from './SignalStatistics';
import BacktestingPage from './BacktestingPage';

const PerformancePage = () => {
  const [activeTab, setActiveTab] = useState('statistics');

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">📈 Performance Center</h1>
          <p className="text-slate-400">Track signal accuracy, view history, and run backtests</p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 bg-slate-800/50 max-w-md">
          <TabsTrigger value="statistics" className="data-[state=active]:bg-purple-600">
            📊 Statistics
          </TabsTrigger>
          <TabsTrigger value="backtest" className="data-[state=active]:bg-purple-600">
            🧪 Backtesting
          </TabsTrigger>
        </TabsList>

        <TabsContent value="statistics" className="mt-6">
          <SignalStatistics />
        </TabsContent>

        <TabsContent value="backtest" className="mt-6">
          <BacktestingPage />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default PerformancePage;
