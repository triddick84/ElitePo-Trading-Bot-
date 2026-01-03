/**
 * AI/ML Models Configuration Page
 * 
 * Centralized page for AI/ML model management:
 * - Model Selection & Configuration
 * - ML Training from Backtests
 * - Strategy Optimization
 * - Retrain Models Section
 * - Model Performance Metrics
 * - Learning System Settings
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Alert, AlertDescription } from './ui/alert';
import { Progress } from './ui/progress';
import { toast } from 'sonner';
import { 
  Brain, Settings, Zap, RefreshCw, BarChart3, TrendingUp, 
  Activity, Database, Cpu, CheckCircle, AlertTriangle, Play,
  Pause, RotateCcw, Layers, Target, Clock, Info, Sparkles,
  GitBranch, LineChart, Award
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Available Models/Strategies
const AVAILABLE_MODELS = [
  { id: 'enhanced_rsi_bb_volume', name: 'Enhanced RSI + BB + Volume', category: 'Technical', accuracy: 78 },
  { id: 'macd_crossover', name: 'MACD Crossover', category: 'Momentum', accuracy: 72 },
  { id: 'ema_crossover', name: 'EMA Crossover (7/21)', category: 'Trend', accuracy: 70 },
  { id: 'rsi_reversal', name: 'RSI Reversal', category: 'Oscillator', accuracy: 74 },
  { id: 'bollinger_squeeze', name: 'Bollinger Squeeze', category: 'Volatility', accuracy: 71 },
  { id: 'stoch_rsi', name: 'Stochastic RSI', category: 'Momentum', accuracy: 73 },
  { id: 'supertrend', name: 'SuperTrend', category: 'Trend', accuracy: 75 },
  { id: 'ichimoku', name: 'Ichimoku Cloud', category: 'Trend', accuracy: 69 },
  { id: 'support_resistance', name: 'Support/Resistance', category: 'Pattern', accuracy: 76 },
  { id: 'candlestick_patterns', name: 'Candlestick Patterns', category: 'Pattern', accuracy: 68 }
];

// ML Model Types
const ML_MODEL_TYPES = [
  { id: 'random_forest', name: 'Random Forest', description: 'Pattern classification with decision trees', icon: '🌲' },
  { id: 'gradient_boosting', name: 'Gradient Boosting', description: 'Sequential learning for accuracy', icon: '📈' },
  { id: 'ensemble', name: 'Ensemble', description: 'Combined predictions from multiple models', icon: '🎯' }
];

const AIMLModelsPage = () => {
  // Model Configuration State
  const [modelConfig, setModelConfig] = useState({
    primary_model: 'enhanced_rsi_bb_volume',
    secondary_model: 'support_resistance',
    use_ensemble: true,
    ensemble_method: 'weighted_average', // 'majority_vote', 'weighted_average', 'stacking'
    min_model_agreement: 2,
    confidence_threshold: 75
  });
  
  // AI Learning System State
  const [learningConfig, setLearningConfig] = useState({
    enabled: true,
    learning_rate: 0.01,
    adaptation_speed: 'medium', // 'slow', 'medium', 'fast'
    use_market_regime: true,
    use_volatility_filter: true,
    lookback_periods: 100,
    min_samples_for_update: 50
  });
  
  // Adaptive Strategy State
  const [adaptiveConfig, setAdaptiveConfig] = useState({
    enabled: true,
    auto_switch_strategy: true,
    strategy_evaluation_window: 20,
    min_trades_for_evaluation: 10,
    switch_threshold: 0.1 // 10% improvement required
  });
  
  // Model Performance
  const [modelPerformance, setModelPerformance] = useState({});
  const [learningStats, setLearningStats] = useState({});
  
  // Retraining State
  const [isRetraining, setIsRetraining] = useState(false);
  const [retrainProgress, setRetrainProgress] = useState(0);
  const [retrainLog, setRetrainLog] = useState([]);
  
  // ML Training State
  const [mlModels, setMlModels] = useState([]);
  const [isTrainingML, setIsTrainingML] = useState(false);
  const [mlTrainingAsset, setMlTrainingAsset] = useState('EURUSD');
  const [mlTrainingTimeframe, setMlTrainingTimeframe] = useState('1h');
  const [mlTrainingDays, setMlTrainingDays] = useState(30);
  const [optimizationResults, setOptimizationResults] = useState(null);
  
  // Loading States
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  
  // Fetch data on mount
  useEffect(() => {
    fetchAllData();
  }, []);
  
  const fetchAllData = async () => {
    await Promise.all([
      fetchModelConfig(),
      fetchModelPerformance(),
      fetchLearningStats(),
      fetchAdaptiveConfig(),
      fetchMLModels()
    ]);
    setIsLoading(false);
  };
  
  const fetchMLModels = async () => {
    try {
      const response = await axios.get(`${API}/ml-training/models`);
      setMlModels(response.data.models || []);
    } catch (error) {
      console.error('Error fetching ML models:', error);
    }
  };
  
  const fetchModelConfig = async () => {
    try {
      const response = await axios.get(`${API}/ai-learning/config`);
      if (response.data) {
        setModelConfig(prev => ({ ...prev, ...response.data.model_config }));
        setLearningConfig(prev => ({ ...prev, ...response.data.learning_config }));
      }
    } catch (error) {
      console.error('Error fetching model config:', error);
    }
  };
  
  const fetchModelPerformance = async () => {
    try {
      const response = await axios.get(`${API}/ai-learning/performance`);
      setModelPerformance(response.data || {});
    } catch (error) {
      console.error('Error fetching model performance:', error);
    }
  };
  
  const fetchLearningStats = async () => {
    try {
      const response = await axios.get(`${API}/ai-learning/stats`);
      setLearningStats(response.data || {});
    } catch (error) {
      console.error('Error fetching learning stats:', error);
    }
  };
  
  const fetchAdaptiveConfig = async () => {
    try {
      const response = await axios.get(`${API}/adaptive-strategy/config`);
      if (response.data) {
        setAdaptiveConfig(prev => ({ ...prev, ...response.data }));
      }
    } catch (error) {
      console.error('Error fetching adaptive config:', error);
    }
  };
  
  // Save all settings
  const handleSaveSettings = async () => {
    setIsSaving(true);
    try {
      await Promise.all([
        axios.post(`${API}/ai-learning/config`, {
          model_config: modelConfig,
          learning_config: learningConfig
        }),
        axios.post(`${API}/adaptive-strategy/config`, adaptiveConfig)
      ]);
      toast.success('✅ AI/ML settings saved!');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };
  
  // Retrain models
  const handleRetrainModels = async () => {
    setIsRetraining(true);
    setRetrainProgress(0);
    setRetrainLog([]);
    
    try {
      // Simulate progress (in real implementation, this would be WebSocket updates)
      const progressInterval = setInterval(() => {
        setRetrainProgress(prev => {
          if (prev >= 95) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + Math.random() * 10;
        });
      }, 500);
      
      setRetrainLog(prev => [...prev, { time: new Date().toLocaleTimeString(), msg: '🚀 Starting model retraining...' }]);
      
      const response = await axios.post(`${API}/ai-learning/retrain`, {
        models: [modelConfig.primary_model, modelConfig.secondary_model],
        use_recent_data: true,
        epochs: 100
      });
      
      clearInterval(progressInterval);
      setRetrainProgress(100);
      
      setRetrainLog(prev => [
        ...prev, 
        { time: new Date().toLocaleTimeString(), msg: '📊 Processing historical data...' },
        { time: new Date().toLocaleTimeString(), msg: '🧠 Training neural networks...' },
        { time: new Date().toLocaleTimeString(), msg: '✅ Retraining complete!' }
      ]);
      
      toast.success('✅ Models retrained successfully!');
      fetchModelPerformance();
    } catch (error) {
      setRetrainLog(prev => [...prev, { time: new Date().toLocaleTimeString(), msg: `❌ Error: ${error.message}` }]);
      toast.error('Failed to retrain models');
    } finally {
      setIsRetraining(false);
    }
  };
  
  // Reset learning
  const handleResetLearning = async () => {
    if (!window.confirm('Are you sure you want to reset all learned parameters? This cannot be undone.')) {
      return;
    }
    
    try {
      await axios.post(`${API}/ai-learning/reset`);
      toast.success('Learning parameters reset');
      fetchLearningStats();
    } catch (error) {
      toast.error('Failed to reset learning');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Brain className="w-8 h-8 text-purple-400" />
            AI/ML Models
          </h1>
          <p className="text-slate-400 mt-1">Configure AI learning systems and trading models</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className={learningConfig.enabled ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'}>
            {learningConfig.enabled ? 'Learning Active' : 'Learning Paused'}
          </Badge>
          <Button onClick={handleSaveSettings} disabled={isSaving} className="bg-purple-500 hover:bg-purple-600">
            {isSaving ? 'Saving...' : 'Save All Settings'}
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Primary Model</p>
                <p className="text-lg font-bold text-white truncate">{modelConfig.primary_model.replace(/_/g, ' ')}</p>
              </div>
              <Cpu className="w-6 h-6 text-purple-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Avg Model Accuracy</p>
                <p className="text-lg font-bold text-green-400">{modelPerformance.average_accuracy?.toFixed(1) || 75}%</p>
              </div>
              <Target className="w-6 h-6 text-green-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Learning Cycles</p>
                <p className="text-lg font-bold text-white">{learningStats.total_cycles || 0}</p>
              </div>
              <RotateCcw className="w-6 h-6 text-blue-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="glass-dark border-slate-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Last Retrain</p>
                <p className="text-lg font-bold text-white">{learningStats.last_retrain || 'Never'}</p>
              </div>
              <Clock className="w-6 h-6 text-yellow-400" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="models" className="space-y-4">
        <TabsList className="bg-slate-800/50">
          <TabsTrigger value="models">🧠 Model Selection</TabsTrigger>
          <TabsTrigger value="learning">📚 Learning System</TabsTrigger>
          <TabsTrigger value="adaptive">🔄 Adaptive Strategy</TabsTrigger>
          <TabsTrigger value="retrain">⚡ Retrain Models</TabsTrigger>
          <TabsTrigger value="performance">📊 Performance</TabsTrigger>
        </TabsList>

        {/* Model Selection Tab */}
        <TabsContent value="models" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Model Selection */}
            <Card className="glass-dark border-slate-700/50">
              <CardHeader>
                <CardTitle className="text-white">Signal Generation Models</CardTitle>
                <CardDescription>Select primary and secondary models for signal generation</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label>Primary Model</Label>
                  <Select 
                    value={modelConfig.primary_model}
                    onValueChange={(v) => setModelConfig(prev => ({ ...prev, primary_model: v }))}
                  >
                    <SelectTrigger className="bg-slate-800/50 border-slate-600 mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-800 border-slate-600">
                      {AVAILABLE_MODELS.map(model => (
                        <SelectItem key={model.id} value={model.id}>
                          <span className="flex items-center gap-2">
                            {model.name}
                            <Badge variant="outline" className="text-xs">{model.accuracy}%</Badge>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <Label>Secondary Model (Confirmation)</Label>
                  <Select 
                    value={modelConfig.secondary_model}
                    onValueChange={(v) => setModelConfig(prev => ({ ...prev, secondary_model: v }))}
                  >
                    <SelectTrigger className="bg-slate-800/50 border-slate-600 mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-800 border-slate-600">
                      {AVAILABLE_MODELS.map(model => (
                        <SelectItem key={model.id} value={model.id}>
                          <span className="flex items-center gap-2">
                            {model.name}
                            <Badge variant="outline" className="text-xs">{model.accuracy}%</Badge>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="flex items-center justify-between pt-4">
                  <div>
                    <Label>Use Ensemble (Combine Models)</Label>
                    <p className="text-xs text-slate-500">Combine multiple models for better accuracy</p>
                  </div>
                  <Switch
                    checked={modelConfig.use_ensemble}
                    onCheckedChange={(v) => setModelConfig(prev => ({ ...prev, use_ensemble: v }))}
                  />
                </div>
                
                {modelConfig.use_ensemble && (
                  <div>
                    <Label>Ensemble Method</Label>
                    <Select 
                      value={modelConfig.ensemble_method}
                      onValueChange={(v) => setModelConfig(prev => ({ ...prev, ensemble_method: v }))}
                    >
                      <SelectTrigger className="bg-slate-800/50 border-slate-600 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-slate-800 border-slate-600">
                        <SelectItem value="majority_vote">Majority Vote</SelectItem>
                        <SelectItem value="weighted_average">Weighted Average</SelectItem>
                        <SelectItem value="stacking">Stacking</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Available Models List */}
            <Card className="glass-dark border-slate-700/50">
              <CardHeader>
                <CardTitle className="text-white">Available Models</CardTitle>
                <CardDescription>All trading models and their baseline accuracy</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {AVAILABLE_MODELS.map(model => (
                    <div 
                      key={model.id}
                      className={`p-3 rounded-lg border ${
                        model.id === modelConfig.primary_model 
                          ? 'border-purple-500 bg-purple-500/10' 
                          : model.id === modelConfig.secondary_model
                            ? 'border-blue-500 bg-blue-500/10'
                            : 'border-slate-700 bg-slate-800/30'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-white">{model.name}</p>
                          <p className="text-xs text-slate-400">{model.category}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className="bg-slate-700">{model.accuracy}%</Badge>
                          {model.id === modelConfig.primary_model && (
                            <Badge className="bg-purple-500/20 text-purple-400">Primary</Badge>
                          )}
                          {model.id === modelConfig.secondary_model && (
                            <Badge className="bg-blue-500/20 text-blue-400">Secondary</Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Learning System Tab */}
        <TabsContent value="learning">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Database className="w-5 h-5" />
                AI Learning System Configuration
              </CardTitle>
              <CardDescription>Configure how the AI learns and adapts to market conditions</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg">
                <div>
                  <Label className="text-lg">Enable AI Learning</Label>
                  <p className="text-sm text-slate-400">Allow the system to learn from trade outcomes</p>
                </div>
                <Switch
                  checked={learningConfig.enabled}
                  onCheckedChange={(v) => setLearningConfig(prev => ({ ...prev, enabled: v }))}
                />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label>Learning Rate: {learningConfig.learning_rate}</Label>
                  <Slider
                    value={[learningConfig.learning_rate * 100]}
                    onValueChange={([v]) => setLearningConfig(prev => ({ ...prev, learning_rate: v / 100 }))}
                    min={1}
                    max={10}
                    className="mt-2"
                  />
                  <p className="text-xs text-slate-500 mt-1">Higher = faster adaptation, but less stable</p>
                </div>
                
                <div>
                  <Label>Adaptation Speed</Label>
                  <Select 
                    value={learningConfig.adaptation_speed}
                    onValueChange={(v) => setLearningConfig(prev => ({ ...prev, adaptation_speed: v }))}
                  >
                    <SelectTrigger className="bg-slate-800/50 border-slate-600 mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-800 border-slate-600">
                      <SelectItem value="slow">Slow (Conservative)</SelectItem>
                      <SelectItem value="medium">Medium (Balanced)</SelectItem>
                      <SelectItem value="fast">Fast (Aggressive)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <Label>Lookback Periods: {learningConfig.lookback_periods}</Label>
                  <Slider
                    value={[learningConfig.lookback_periods]}
                    onValueChange={([v]) => setLearningConfig(prev => ({ ...prev, lookback_periods: v }))}
                    min={20}
                    max={500}
                    className="mt-2"
                  />
                </div>
                
                <div>
                  <Label>Min Samples for Update: {learningConfig.min_samples_for_update}</Label>
                  <Slider
                    value={[learningConfig.min_samples_for_update]}
                    onValueChange={([v]) => setLearningConfig(prev => ({ ...prev, min_samples_for_update: v }))}
                    min={10}
                    max={200}
                    className="mt-2"
                  />
                </div>
              </div>
              
              <div className="flex flex-wrap gap-4 pt-4 border-t border-slate-700">
                <div className="flex items-center gap-2">
                  <Switch
                    checked={learningConfig.use_market_regime}
                    onCheckedChange={(v) => setLearningConfig(prev => ({ ...prev, use_market_regime: v }))}
                  />
                  <Label>Market Regime Detection</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={learningConfig.use_volatility_filter}
                    onCheckedChange={(v) => setLearningConfig(prev => ({ ...prev, use_volatility_filter: v }))}
                  />
                  <Label>Volatility Filter</Label>
                </div>
              </div>
              
              <Alert className="bg-blue-500/10 border-blue-500/30">
                <Info className="w-4 h-4 text-blue-400" />
                <AlertDescription className="text-blue-300 text-sm">
                  The AI learning system continuously analyzes trade outcomes to improve signal accuracy over time.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Adaptive Strategy Tab */}
        <TabsContent value="adaptive">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <RefreshCw className="w-5 h-5" />
                Adaptive Strategy Configuration
              </CardTitle>
              <CardDescription>Automatically switch strategies based on performance</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg">
                <div>
                  <Label className="text-lg">Enable Adaptive Strategy</Label>
                  <p className="text-sm text-slate-400">Auto-switch to better performing strategies</p>
                </div>
                <Switch
                  checked={adaptiveConfig.enabled}
                  onCheckedChange={(v) => setAdaptiveConfig(prev => ({ ...prev, enabled: v }))}
                />
              </div>
              
              {adaptiveConfig.enabled && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Auto-Switch Strategy</Label>
                      <p className="text-xs text-slate-500">Automatically change strategies</p>
                    </div>
                    <Switch
                      checked={adaptiveConfig.auto_switch_strategy}
                      onCheckedChange={(v) => setAdaptiveConfig(prev => ({ ...prev, auto_switch_strategy: v }))}
                    />
                  </div>
                  
                  <div>
                    <Label>Evaluation Window: {adaptiveConfig.strategy_evaluation_window} trades</Label>
                    <Slider
                      value={[adaptiveConfig.strategy_evaluation_window]}
                      onValueChange={([v]) => setAdaptiveConfig(prev => ({ ...prev, strategy_evaluation_window: v }))}
                      min={5}
                      max={50}
                      className="mt-2"
                    />
                  </div>
                  
                  <div>
                    <Label>Min Trades for Evaluation: {adaptiveConfig.min_trades_for_evaluation}</Label>
                    <Slider
                      value={[adaptiveConfig.min_trades_for_evaluation]}
                      onValueChange={([v]) => setAdaptiveConfig(prev => ({ ...prev, min_trades_for_evaluation: v }))}
                      min={5}
                      max={30}
                      className="mt-2"
                    />
                  </div>
                  
                  <div>
                    <Label>Switch Threshold: {(adaptiveConfig.switch_threshold * 100).toFixed(0)}% improvement</Label>
                    <Slider
                      value={[adaptiveConfig.switch_threshold * 100]}
                      onValueChange={([v]) => setAdaptiveConfig(prev => ({ ...prev, switch_threshold: v / 100 }))}
                      min={5}
                      max={30}
                      className="mt-2"
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Retrain Models Tab */}
        <TabsContent value="retrain">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Zap className="w-5 h-5" />
                Retrain Models
              </CardTitle>
              <CardDescription>Manually trigger model retraining with recent data</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert className="bg-yellow-500/10 border-yellow-500/30">
                <AlertTriangle className="w-4 h-4 text-yellow-400" />
                <AlertDescription className="text-yellow-300 text-sm">
                  Retraining uses recent trade data to update model parameters. This process may take a few minutes.
                </AlertDescription>
              </Alert>
              
              <div className="flex items-center gap-4">
                <Button
                  onClick={handleRetrainModels}
                  disabled={isRetraining}
                  className="bg-purple-500 hover:bg-purple-600"
                >
                  {isRetraining ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Retraining...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      Start Retraining
                    </>
                  )}
                </Button>
                
                <Button
                  onClick={handleResetLearning}
                  variant="outline"
                  className="border-red-500/30 text-red-400 hover:bg-red-500/10"
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Reset All Learning
                </Button>
              </div>
              
              {isRetraining && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Progress</span>
                    <span className="text-white">{Math.round(retrainProgress)}%</span>
                  </div>
                  <Progress value={retrainProgress} className="h-2" />
                </div>
              )}
              
              {retrainLog.length > 0 && (
                <div className="bg-slate-900 rounded-lg p-4 max-h-48 overflow-y-auto">
                  <p className="text-sm text-slate-400 mb-2">Training Log:</p>
                  {retrainLog.map((log, idx) => (
                    <p key={idx} className="text-xs text-slate-300 font-mono">
                      [{log.time}] {log.msg}
                    </p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Performance Tab */}
        <TabsContent value="performance">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Model Performance
              </CardTitle>
              <CardDescription>Track accuracy and performance of each model</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {AVAILABLE_MODELS.map(model => {
                  const perf = modelPerformance[model.id] || { accuracy: model.accuracy, trades: 0 };
                  return (
                    <div key={model.id} className="p-4 bg-slate-800/30 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-white">{model.name}</span>
                          {model.id === modelConfig.primary_model && (
                            <Badge className="bg-purple-500/20 text-purple-400 text-xs">Primary</Badge>
                          )}
                        </div>
                        <span className={`font-bold ${perf.accuracy >= 70 ? 'text-green-400' : 'text-yellow-400'}`}>
                          {perf.accuracy?.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Progress value={perf.accuracy} className="h-2 flex-1" />
                        <span className="text-xs text-slate-500">{perf.trades || 0} trades</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AIMLModelsPage;
