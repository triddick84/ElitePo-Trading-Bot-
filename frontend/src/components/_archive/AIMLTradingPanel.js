import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Progress } from './ui/progress';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const AIMLTradingPanel = () => {
  const [status, setStatus] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD_OTC');
  const [loading, setLoading] = useState(false);
  const [predicting, setPredicting] = useState(false);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${BACKEND_URL}/api/ai-ml/status`);
      if (response.data.success) {
        setStatus(response.data);
      }
    } catch (error) {
      console.error('Error loading AI/ML status:', error);
      toast.error('Failed to load AI/ML status');
    } finally {
      setLoading(false);
    }
  };

  const getPrediction = async () => {
    try {
      setPredicting(true);
      const response = await axios.post(
        `${BACKEND_URL}/api/ai-ml/predict?symbol=${selectedSymbol}`
      );
      
      if (response.data.success) {
        setPrediction(response.data);
        toast.success('✅ Prediction generated!');
      } else {
        toast.error('Failed to generate prediction');
      }
    } catch (error) {
      console.error('Error getting prediction:', error);
      toast.error('Error generating prediction');
    } finally {
      setPredicting(false);
    }
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 80) return 'text-emerald-400';
    if (confidence >= 60) return 'text-blue-400';
    if (confidence >= 40) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getDirectionBadge = (direction) => {
    const colors = {
      'UP': 'bg-emerald-500/20 text-emerald-400 border-emerald-500',
      'DOWN': 'bg-red-500/20 text-red-400 border-red-500',
      'HOLD': 'bg-gray-500/20 text-gray-400 border-gray-500'
    };
    
    return (
      <Badge className={colors[direction] || colors['HOLD']}>
        {direction === 'UP' ? '📈 CALL' : direction === 'DOWN' ? '📉 PUT' : '⏸️ HOLD'}
      </Badge>
    );
  };

  if (loading) {
    return (
      <Card className="w-full bg-slate-900 border-slate-700">
        <CardContent className="p-6">
          <div className="text-center text-slate-400">Loading AI/ML Trading System...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* System Status */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <CardTitle className="text-2xl text-emerald-400">🤖 AI/ML Trading System</CardTitle>
          <CardDescription className="text-slate-400">
            Advanced ensemble prediction using LSTM, RandomForest, and LLM models
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status?.models && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* LSTM Model */}
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-white">LSTM Model</h4>
                  {status.models.lstm?.available ? (
                    <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500">Active</Badge>
                  ) : (
                    <Badge className="bg-gray-500/20 text-gray-400 border-gray-500">Offline</Badge>
                  )}
                </div>
                <p className="text-xs text-slate-400 mb-2">{status.models.lstm?.description}</p>
                {status.models.lstm?.trained && (
                  <p className="text-xs text-emerald-400">✓ Model trained</p>
                )}
              </div>

              {/* RandomForest Model */}
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-white">RandomForest</h4>
                  {status.models.random_forest?.available ? (
                    <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500">Active</Badge>
                  ) : (
                    <Badge className="bg-gray-500/20 text-gray-400 border-gray-500">Offline</Badge>
                  )}
                </div>
                <p className="text-xs text-slate-400 mb-2">{status.models.random_forest?.description}</p>
                {status.models.random_forest?.trained && (
                  <p className="text-xs text-emerald-400">✓ Model trained</p>
                )}
              </div>

              {/* Emergent LLM */}
              <div className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-white">Emergent LLM</h4>
                  {status.models.emergent_llm?.available ? (
                    <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500">Active</Badge>
                  ) : (
                    <Badge className="bg-gray-500/20 text-gray-400 border-gray-500">Offline</Badge>
                  )}
                </div>
                <p className="text-xs text-slate-400 mb-2">{status.models.emergent_llm?.description}</p>
                {status.models.emergent_llm?.api_key && (
                  <p className="text-xs text-emerald-400">✓ API configured</p>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Prediction Interface */}
      <Card className="bg-slate-900 border-slate-700">
        <CardHeader>
          <CardTitle className="text-xl text-white">🎯 Get AI Prediction</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <Input
              type="text"
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              placeholder="Enter symbol (e.g., EURUSD_OTC)"
              className="flex-1 bg-slate-800 border-slate-700 text-white"
            />
            <Button
              onClick={getPrediction}
              disabled={predicting}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {predicting ? '⏳ Analyzing...' : '🔮 Predict'}
            </Button>
          </div>

          {prediction && (
            <div className="bg-slate-800 rounded-lg p-6 space-y-4">
              {/* Final Prediction */}
              <div className="border-b border-slate-700 pb-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-semibold text-white">Ensemble Prediction</h3>
                  {getDirectionBadge(prediction.final_direction)}
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Confidence</span>
                    <span className={`text-2xl font-bold ${getConfidenceColor(prediction.final_confidence)}`}>
                      {prediction.final_confidence}%
                    </span>
                  </div>
                  <Progress value={prediction.final_confidence} className="h-3" />
                  
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-slate-400">Models Used</span>
                    <span className="text-white">{prediction.models_used} / 3</span>
                  </div>
                </div>
              </div>

              {/* Individual Model Predictions */}
              {prediction.individual_predictions && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-300 mb-3">Individual Model Predictions</h4>
                  <div className="space-y-2">
                    {Object.entries(prediction.individual_predictions).map(([model, data]) => (
                      <div key={model} className="bg-slate-700/50 rounded p-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-slate-300 capitalize">
                            {model.replace('_', ' ')}
                          </span>
                          {getDirectionBadge(data.direction)}
                        </div>
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-slate-400">Confidence</span>
                          <span className={getConfidenceColor(data.confidence)}>
                            {data.confidence}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Market Analysis */}
              {prediction.market_analysis && (
                <div className="border-t border-slate-700 pt-4">
                  <h4 className="text-sm font-semibold text-slate-300 mb-2">📊 Market Analysis</h4>
                  <div className="text-sm text-slate-400 space-y-1">
                    {prediction.market_analysis.split('\n').map((line, idx) => (
                      <p key={idx}>{line}</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AIMLTradingPanel;