/**
 * Autonomous Trading Hub
 * 
 * Single pane of glass for AI-powered autonomous trading.
 * The user only needs to:
 * 1. Set their budget allocation
 * 2. Enable autonomous mode
 * 
 * The AI team (Mazo + 18 Agents + PM) handles everything else:
 * - Market scanning
 * - Signal generation
 * - Research validation
 * - Trade execution
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE_URL } from '@/lib/api-config';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { 
  useHydratedData, 
  dataHydrationService,
  type Position,
} from '@/services/data-hydration-service';
import { toast } from 'sonner';
import { 
  Play, 
  TrendingUp,
  Activity,
  Brain,
  Shield,
  Zap,
  CheckCircle,
  AlertCircle,
  Users,
  BarChart3,
  Wallet,
  Target,
  RefreshCw,
  ChevronRight,
  Bot,
  Sparkles,
  Eye,
  Lock
} from 'lucide-react';

// Types
interface AIActivity {
  id: string;
  timestamp: Date;
  type: 'scan' | 'analyze' | 'decide' | 'execute' | 'monitor';
  message: string;
  ticker?: string;
  status: 'running' | 'complete' | 'error';
  details?: any;
}

interface TradingConfig {
  budgetPercent: number;  // % of portfolio to use
  riskLevel: 'conservative' | 'balanced' | 'aggressive';
  maxPositions: number;
  stopLossPercent: number;
  takeProfitPercent: number;
}

const DEFAULT_CONFIG: TradingConfig = {
  budgetPercent: 25,
  riskLevel: 'balanced',
  maxPositions: 5,
  stopLossPercent: 5,
  takeProfitPercent: 10,
};

const RISK_PRESETS = {
  conservative: { maxPositions: 3, stopLossPercent: 3, takeProfitPercent: 6, budgetPercent: 15 },
  balanced: { maxPositions: 5, stopLossPercent: 5, takeProfitPercent: 10, budgetPercent: 25 },
  aggressive: { maxPositions: 8, stopLossPercent: 8, takeProfitPercent: 20, budgetPercent: 40 },
};

function formatCurrency(value: number): string {
  const sign = value >= 0 ? '' : '-';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function AutonomousTradingHub() {
  // Use hydrated data from shared store
  // Use unified global store - state persists across all tabs
  const { 
    performance, 
    scheduler, 
    metrics,
    recentWorkflows,
    automatedStatus,
    // AI Hedge Fund persisted state from global store
    isAutonomousEnabled,
    aiActivities: activities,
    tradingConfig,
    activeOperations,
    // Actions
    setAutonomousEnabled,
    addAIActivity,
    setTradingConfig,
    startOperation,
    endOperation,
  } = useHydratedData();

  // Local UI state only
  const [isStarting, setIsStarting] = useState(false);
  
  // Map store config to component config format
  const config: TradingConfig = {
    budgetPercent: tradingConfig.budgetPercent,
    riskLevel: tradingConfig.riskLevel,
    maxPositions: tradingConfig.maxPositions,
    stopLossPercent: tradingConfig.stopLossPercent,
  };
  
  const setConfig = (updater: TradingConfig | ((prev: TradingConfig) => TradingConfig)) => {
    if (typeof updater === 'function') {
      setTradingConfig(updater(config));
    } else {
      setTradingConfig(updater);
    }
  };

  // Calculate budget in dollars
  const portfolioValue = performance?.equity || 0;
  const allocatedBudget = (portfolioValue * config.budgetPercent) / 100;
  const cashAvailable = performance?.cash || 0;
  const effectiveBudget = Math.min(allocatedBudget, cashAvailable);

  // Sync with scheduler status from store
  useEffect(() => {
    if (scheduler?.is_running !== undefined) {
      setAutonomousEnabled(scheduler.is_running);
    }
  }, [scheduler?.is_running, setAutonomousEnabled]);

  // Helper to add activity using store action
  const addActivity = useCallback((activity: Omit<AIActivity, 'id' | 'timestamp'>) => {
    addAIActivity(activity);
  }, [addAIActivity]);

  // Handle risk level change
  const handleRiskChange = (level: TradingConfig['riskLevel']) => {
    const preset = RISK_PRESETS[level];
    setConfig(prev => ({
      ...prev,
      riskLevel: level,
      ...preset,
    }));
  };

  // Toggle autonomous mode
  const toggleAutonomous = async () => {
    setIsStarting(true);
    
    try {
      const response = await fetch(`${API_BASE_URL}/trading/scheduler/${isAutonomousEnabled ? 'stop' : 'start'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          budget_percent: config.budgetPercent,
          risk_level: config.riskLevel,
          max_positions: config.maxPositions,
        }),
      });
      
      if (response.ok) {
        setAutonomousEnabled(!isAutonomousEnabled);
        toast.success(
          isAutonomousEnabled 
            ? 'Autonomous trading paused' 
            : 'Autonomous trading enabled! The AI team is now managing your portfolio.',
          { duration: 4000 }
        );
        
        // Add activity
        addActivity({
          type: isAutonomousEnabled ? 'monitor' : 'scan',
          message: isAutonomousEnabled 
            ? 'Autonomous mode paused by user'
            : `Autonomous mode activated with ${formatCurrency(effectiveBudget)} budget`,
          status: 'complete',
        });
        
        // Refresh data
        await dataHydrationService.backgroundRefresh();
      }
    } catch (error) {
      toast.error('Failed to toggle autonomous mode');
    } finally {
      setIsStarting(false);
    }
  };

  // Run one AI cycle manually
  const runManualCycle = async () => {
    setIsStarting(true);
    
    addActivity({
      type: 'scan',
      message: 'Starting manual AI trading cycle...',
      status: 'running',
    });
    
    try {
      const response = await fetch(`${API_BASE_URL}/trading/automated/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          execute_trades: true,
          dry_run: false,
        }),
      });
      
      const result = await response.json();
      
      if (result.success !== false) {
        addActivity({
          type: 'execute',
          message: `Cycle complete: ${result.trades_executed || 0} trades executed`,
          status: 'complete',
          details: result,
        });
        
        toast.success(`AI cycle complete! ${result.trades_executed || 0} trades executed.`);
        await dataHydrationService.backgroundRefresh();
      } else {
        throw new Error(result.error || 'Cycle failed');
      }
    } catch (error: any) {
      addActivity({
        type: 'execute',
        message: `Cycle failed: ${error.message}`,
        status: 'error',
      });
      toast.error(`Cycle failed: ${error.message}`);
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="h-full overflow-auto bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        
        {/* Hero Header */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-purple-900/50 via-indigo-900/50 to-blue-900/50 border border-purple-500/30 p-8">
          <div className="absolute inset-0 bg-grid-white/5" />
          <div className="relative">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 rounded-xl bg-purple-500/20 border border-purple-500/50">
                    <Bot className="w-8 h-8 text-purple-400" />
                  </div>
                  <h1 className="text-4xl font-bold text-white">
                    AI Hedge Fund
                  </h1>
                  {isAutonomousEnabled && (
                    <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/50 animate-pulse">
                      <Sparkles className="w-3 h-3 mr-1" />
                      LIVE
                    </Badge>
                  )}
                </div>
                <p className="text-slate-300 text-lg max-w-2xl">
                  Let the AI team manage your portfolio. 18 world-class analysts + Mazo research + 
                  Portfolio Manager working together to find opportunities and execute trades.
                </p>
              </div>
              
              {/* Main Toggle */}
              <div className="text-center">
                <div className={`p-6 rounded-2xl border-2 transition-all duration-300 ${
                  isAutonomousEnabled 
                    ? 'bg-emerald-500/10 border-emerald-500/50' 
                    : 'bg-slate-800/50 border-slate-600'
                }`}>
                  <div className="flex items-center gap-4">
                    <Switch
                      checked={isAutonomousEnabled}
                      onCheckedChange={toggleAutonomous}
                      disabled={isStarting}
                      className="scale-150"
                    />
                    <div className="text-left">
                      <div className="text-white font-semibold">
                        {isAutonomousEnabled ? 'Autonomous Mode ON' : 'Autonomous Mode OFF'}
                      </div>
                      <div className="text-sm text-slate-400">
                        {isAutonomousEnabled ? 'AI team is actively trading' : 'Click to enable'}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Portfolio & Budget Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Portfolio Overview */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-white">
                <Wallet className="w-5 h-5 text-blue-400" />
                Your Alpaca Portfolio
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="text-sm text-slate-400">Total Equity</div>
                <div className="text-3xl font-bold text-white">
                  {formatCurrency(portfolioValue)}
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-slate-400">Cash Available</div>
                  <div className="text-lg font-semibold text-emerald-400">
                    {formatCurrency(cashAvailable)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-slate-400">Today's P&L</div>
                  <div className={`text-lg font-semibold ${(performance?.total_unrealized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(performance?.total_unrealized_pnl || 0)}
                  </div>
                </div>
              </div>
              
              <div className="pt-2 border-t border-slate-700">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Open Positions</span>
                  <span className="text-white font-medium">{performance?.positions_count || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Budget Allocation */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-white">
                <Target className="w-5 h-5 text-purple-400" />
                AI Trading Budget
              </CardTitle>
              <CardDescription>
                How much can the AI team use for trades?
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-slate-400">Budget Allocation</span>
                  <span className="text-xl font-bold text-purple-400">{config.budgetPercent}%</span>
                </div>
                <Slider
                  value={[config.budgetPercent]}
                  onValueChange={(value) => setConfig(prev => ({ ...prev, budgetPercent: value[0] }))}
                  min={5}
                  max={100}
                  step={5}
                  disabled={isAutonomousEnabled}
                  className="py-2"
                />
              </div>
              
              <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/30">
                <div className="text-sm text-slate-400">Effective Budget</div>
                <div className="text-2xl font-bold text-purple-400">
                  {formatCurrency(effectiveBudget)}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  of {formatCurrency(portfolioValue)} portfolio
                </div>
              </div>
              
              {isAutonomousEnabled && (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Lock className="w-3 h-3" />
                  Pause trading to adjust budget
                </div>
              )}
            </CardContent>
          </Card>

          {/* Risk Level */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-white">
                <Shield className="w-5 h-5 text-cyan-400" />
                Risk Profile
              </CardTitle>
              <CardDescription>
                Choose your risk tolerance
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(['conservative', 'balanced', 'aggressive'] as const).map((level) => (
                <button
                  key={level}
                  onClick={() => !isAutonomousEnabled && handleRiskChange(level)}
                  disabled={isAutonomousEnabled}
                  className={`w-full p-3 rounded-lg border text-left transition-all ${
                    config.riskLevel === level
                      ? level === 'conservative' 
                        ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                        : level === 'balanced'
                        ? 'bg-purple-500/20 border-purple-500/50 text-purple-400'
                        : 'bg-orange-500/20 border-orange-500/50 text-orange-400'
                      : 'bg-slate-700/30 border-slate-600 text-slate-400 hover:border-slate-500'
                  } ${isAutonomousEnabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-medium capitalize">{level}</div>
                      <div className="text-xs opacity-70">
                        {level === 'conservative' && 'Smaller positions, tighter stops'}
                        {level === 'balanced' && 'Moderate risk/reward balance'}
                        {level === 'aggressive' && 'Larger positions, wider stops'}
                      </div>
                    </div>
                    <ChevronRight className={`w-4 h-4 ${config.riskLevel === level ? 'opacity-100' : 'opacity-0'}`} />
                  </div>
                </button>
              ))}
              
              <div className="pt-3 border-t border-slate-700 grid grid-cols-2 gap-2 text-xs text-slate-400">
                <div>Max positions: <span className="text-white">{config.maxPositions}</span></div>
                <div>Stop loss: <span className="text-white">{config.stopLossPercent}%</span></div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* AI Team Status & Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* AI Team */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-white">
                <div className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-indigo-400" />
                  AI Team
                </div>
                <Button
                  onClick={runManualCycle}
                  disabled={isStarting || automatedStatus?.is_running}
                  size="sm"
                  variant="outline"
                  className="border-indigo-500 text-indigo-400 hover:bg-indigo-500/20"
                >
                  {isStarting ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4 mr-2" />
                  )}
                  Run Cycle Now
                </Button>
              </CardTitle>
              <CardDescription>
                Your autonomous trading team
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Team Members */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/30">
                  <div className="flex items-center gap-2 mb-2">
                    <Brain className="w-4 h-4 text-blue-400" />
                    <span className="text-sm font-medium text-white">Mazo</span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Deep research & validation
                  </div>
                </div>
                
                <div className="p-3 rounded-lg bg-gradient-to-br from-purple-500/20 to-purple-600/10 border border-purple-500/30">
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="w-4 h-4 text-purple-400" />
                    <span className="text-sm font-medium text-white">18 Analysts</span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Warren Buffett, Peter Lynch...
                  </div>
                </div>
                
                <div className="p-3 rounded-lg bg-gradient-to-br from-emerald-500/20 to-emerald-600/10 border border-emerald-500/30">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm font-medium text-white">PM</span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Final decisions & execution
                  </div>
                </div>
              </div>
              
              {/* Pipeline Status */}
              <div className="p-4 rounded-lg bg-slate-700/30 border border-slate-600/50">
                <div className="text-sm font-medium text-white mb-3">Trading Pipeline</div>
                <div className="flex items-center justify-between text-xs">
                  {['Scan', 'Research', 'Analyze', 'Decide', 'Execute'].map((step, i) => (
                    <div key={step} className="flex items-center">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        automatedStatus?.is_running
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                          : 'bg-slate-600/50 text-slate-500 border border-slate-500/50'
                      }`}>
                        {i + 1}
                      </div>
                      {i < 4 && (
                        <ChevronRight className={`w-4 h-4 mx-1 ${
                          automatedStatus?.is_running ? 'text-emerald-400/50' : 'text-slate-600'
                        }`} />
                      )}
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-between text-[10px] text-slate-500 mt-1">
                  <span>Market</span>
                  <span>Mazo</span>
                  <span>Agents</span>
                  <span>PM</span>
                  <span>Alpaca</span>
                </div>
              </div>
              
              {/* Last Run Stats */}
              {automatedStatus?.last_result && (
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="p-2 bg-slate-700/30 rounded">
                    <div className="text-lg font-bold text-white">
                      {automatedStatus.last_result.tickers_screened || 0}
                    </div>
                    <div className="text-[10px] text-slate-500">Screened</div>
                  </div>
                  <div className="p-2 bg-slate-700/30 rounded">
                    <div className="text-lg font-bold text-cyan-400">
                      {automatedStatus.last_result.signals_found || 0}
                    </div>
                    <div className="text-[10px] text-slate-500">Signals</div>
                  </div>
                  <div className="p-2 bg-slate-700/30 rounded">
                    <div className="text-lg font-bold text-purple-400">
                      {automatedStatus.last_result.mazo_validated || 0}
                    </div>
                    <div className="text-[10px] text-slate-500">Validated</div>
                  </div>
                  <div className="p-2 bg-slate-700/30 rounded">
                    <div className="text-lg font-bold text-emerald-400">
                      {automatedStatus.last_result.trades_executed || 0}
                    </div>
                    <div className="text-[10px] text-slate-500">Executed</div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Activity Feed */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Activity className="w-5 h-5 text-yellow-400" />
                Live Activity
              </CardTitle>
              <CardDescription>
                Real-time AI team actions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {activities.length === 0 ? (
                  <div className="text-center py-8 text-slate-400">
                    <Activity className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>No activity yet</p>
                    <p className="text-sm mt-1">Enable autonomous mode or run a cycle</p>
                  </div>
                ) : (
                  activities.map((activity) => (
                    <div 
                      key={activity.id}
                      className={`p-3 rounded-lg border ${
                        activity.status === 'running'
                          ? 'bg-blue-500/10 border-blue-500/30'
                          : activity.status === 'error'
                          ? 'bg-red-500/10 border-red-500/30'
                          : 'bg-slate-700/30 border-slate-600/50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`mt-0.5 ${
                          activity.status === 'running' ? 'text-blue-400' :
                          activity.status === 'error' ? 'text-red-400' :
                          'text-emerald-400'
                        }`}>
                          {activity.status === 'running' ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : activity.status === 'error' ? (
                            <AlertCircle className="w-4 h-4" />
                          ) : (
                            <CheckCircle className="w-4 h-4" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            {activity.ticker && (
                              <Badge variant="outline" className="text-xs border-slate-500">
                                {activity.ticker}
                              </Badge>
                            )}
                            <span className="text-sm text-white">{activity.message}</span>
                          </div>
                          <div className="text-xs text-slate-500 mt-1">
                            {activity.timestamp.toLocaleTimeString()}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Current Positions & Performance */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Positions */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <BarChart3 className="w-5 h-5 text-blue-400" />
                Open Positions
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!performance?.positions || performance.positions.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p>No open positions</p>
                  <p className="text-sm mt-1">The AI team will open positions when opportunities arise</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {performance.positions.map((pos: Position) => (
                    <div 
                      key={pos.ticker}
                      className="flex items-center justify-between p-3 bg-slate-700/30 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-bold text-white text-lg">{pos.ticker}</span>
                        <Badge variant="outline" className={pos.side === 'long' ? 'border-emerald-500 text-emerald-400' : 'border-red-500 text-red-400'}>
                          {pos.side.toUpperCase()}
                        </Badge>
                        <span className="text-slate-400 text-sm">{Math.abs(pos.qty)} shares</span>
                      </div>
                      <div className="text-right">
                        <div className={`font-mono font-bold ${pos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {formatCurrency(pos.unrealized_pnl)}
                        </div>
                        <div className="text-xs text-slate-500">
                          {formatPercent(pos.unrealized_pnl_pct)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Performance Metrics */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <TrendingUp className="w-5 h-5 text-emerald-400" />
                AI Performance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-slate-700/30 rounded-lg">
                  <div className="text-sm text-slate-400">Total Trades</div>
                  <div className="text-2xl font-bold text-cyan-400">
                    {metrics?.total_trades || 0}
                  </div>
                </div>
                <div className="p-4 bg-slate-700/30 rounded-lg">
                  <div className="text-sm text-slate-400">Win Rate</div>
                  <div className="text-2xl font-bold text-purple-400">
                    {metrics?.win_rate != null ? `${metrics.win_rate}%` : 'N/A'}
                  </div>
                </div>
                <div className="p-4 bg-slate-700/30 rounded-lg">
                  <div className="text-sm text-slate-400">Total P&L</div>
                  <div className={`text-2xl font-bold ${(metrics?.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(metrics?.total_pnl || 0)}
                  </div>
                </div>
                <div className="p-4 bg-slate-700/30 rounded-lg">
                  <div className="text-sm text-slate-400">AI Runs</div>
                  <div className="text-2xl font-bold text-orange-400">
                    {automatedStatus?.total_runs || 0}
                  </div>
                </div>
              </div>
              
              {/* Recent Decisions */}
              {recentWorkflows.length > 0 && (
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <div className="text-sm font-medium text-white mb-3">Recent AI Decisions</div>
                  <div className="space-y-2">
                    {recentWorkflows.slice(0, 3).map((wf) => (
                      <div key={wf.id} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-white">{wf.tickers.join(', ')}</span>
                          {wf.pmDecision && (
                            <Badge className={
                              wf.pmDecision.action === 'buy' || wf.pmDecision.action === 'cover'
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : wf.pmDecision.action === 'sell' || wf.pmDecision.action === 'short'
                                ? 'bg-red-500/20 text-red-400'
                                : 'bg-slate-500/20 text-slate-400'
                            }>
                              {wf.pmDecision.action.toUpperCase()}
                            </Badge>
                          )}
                        </div>
                        <span className="text-xs text-slate-500">
                          {wf.timestamp.toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Quick Analysis Section */}
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-white">
              <div className="flex items-center gap-2">
                <Eye className="w-5 h-5 text-cyan-400" />
                Quick Analysis
              </div>
              <Badge variant="outline" className="border-slate-500 text-slate-400">
                Manual Mode
              </Badge>
            </CardTitle>
            <CardDescription>
              Run a targeted analysis on specific tickers without waiting for the autonomous cycle
            </CardDescription>
          </CardHeader>
          <CardContent>
            <QuickAnalysisForm 
              onComplete={(result) => {
                addActivity({
                  type: 'analyze',
                  message: `Manual analysis complete for ${result.ticker}`,
                  ticker: result.ticker,
                  status: 'complete',
                  details: result,
                });
              }}
            />
          </CardContent>
        </Card>

      </div>
    </div>
  );
}

// Ticker suggestions from Alpaca
interface TickerSuggestion {
  symbol: string;
  name: string;
  exchange?: string;
}

// Quick Analysis Form Component - uses global store for persistence
function QuickAnalysisForm({ onComplete }: { onComplete: (result: any) => void }) {
  // Use global store for persistence across tab switches
  const { 
    quickAnalysisResult: result, 
    quickAnalysisTicker: storedTicker,
    setQuickAnalysisResult: setResult,
    setQuickAnalysisTicker: setStoredTicker,
    activeOperations,
    startOperation,
    endOperation,
    addAIActivity,
  } = useHydratedData();
  
  // Local ticker for typing (syncs to store on blur)
  const [ticker, setTicker] = useState(storedTicker);
  const [isRunning, setIsRunning] = useState(false);
  
  // Autocomplete state
  const [suggestions, setSuggestions] = useState<TickerSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Check if there's a global analysis running
  const globalAnalysisRunning = Object.values(activeOperations).some(
    op => op.type === 'quickAnalysis'
  );

  // Sync from store when it changes
  useEffect(() => {
    setTicker(storedTicker);
  }, [storedTicker]);

  // Search for ticker suggestions from Alpaca
  const searchTickers = useCallback(async (query: string) => {
    if (query.length < 1) {
      setSuggestions([]);
      return;
    }

    setSearchLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/alpaca/assets?search=${encodeURIComponent(query)}&limit=8`
      );
      if (response.ok) {
        const data = await response.json();
        setSuggestions(data.assets || []);
      }
    } catch (e) {
      console.error('Ticker search failed:', e);
    } finally {
      setSearchLoading(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (ticker.length >= 1 && showSuggestions) {
      debounceRef.current = setTimeout(() => {
        searchTickers(ticker);
      }, 200);
    } else {
      setSuggestions([]);
    }

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [ticker, showSuggestions, searchTickers]);

  const selectTicker = (symbol: string) => {
    setTicker(symbol);
    setShowSuggestions(false);
    setSuggestions([]);
  };

  const runAnalysis = async () => {
    if (!ticker.trim()) {
      toast.error('Please enter a ticker symbol');
      return;
    }

    const operationId = `quickAnalysis_${Date.now()}`;
    setIsRunning(true);
    setResult(null);
    setShowSuggestions(false);
    setStoredTicker(ticker.toUpperCase()); // Save to store
    
    // Track operation globally so it persists across tabs
    startOperation(operationId, 'quickAnalysis', `Analyzing ${ticker.toUpperCase()}...`);

    try {
      // Start the analysis via POST to get the stream
      const response = await fetch(`${API_BASE_URL}/unified-workflow/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers: [ticker.toUpperCase()],
          mode: 'signal', // Use signal mode for quick analysis
          depth: 'quick',
          execute_trades: false,
          dry_run: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Handle SSE stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let finalResult: any = null;

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const eventData = JSON.parse(line.slice(6));
                
                // Look for complete event with results
                if (eventData.type === 'complete' && eventData.data) {
                  const results = eventData.data.results || eventData.data;
                  if (Array.isArray(results) && results.length > 0) {
                    finalResult = results[0];
                  } else if (results.decisions) {
                    // Extract from decisions format
                    const tickerKey = ticker.toUpperCase();
                    const decision = results.decisions[tickerKey];
                    if (decision) {
                      finalResult = {
                        signal: decision.action?.toUpperCase() || 'NEUTRAL',
                        confidence: decision.confidence,
                        reasoning: decision.reasoning,
                        agent_signals: Object.entries(results.analyst_signals?.[tickerKey] || {}).map(
                          ([name, sig]: [string, any]) => ({
                            agent_name: name,
                            signal: sig.signal?.toUpperCase(),
                            confidence: sig.confidence
                          })
                        )
                      };
                    }
                  }
                }
                
                // Also check for hedge_fund_signal in progress events
                if (eventData.type === 'progress' && eventData.data?.hedge_fund_signal) {
                  const sig = eventData.data.hedge_fund_signal;
                  finalResult = {
                    signal: sig.action?.toUpperCase() || sig.signal?.toUpperCase() || 'NEUTRAL',
                    confidence: sig.confidence,
                    reasoning: sig.reasoning,
                    agent_signals: sig.agent_signals
                  };
                }
              } catch {
                // Skip non-JSON lines
              }
            }
          }
        }
      }

      if (finalResult) {
        finalResult.ticker = ticker.toUpperCase();
        finalResult.timestamp = new Date().toISOString();
        setResult(finalResult);
        onComplete({ ticker: ticker.toUpperCase(), ...finalResult });
        toast.success(`Analysis complete for ${ticker.toUpperCase()}`);
        
        // Add to activity log
        addAIActivity({
          type: 'analyze',
          message: `Quick analysis: ${ticker.toUpperCase()} → ${finalResult.signal}`,
          ticker: ticker.toUpperCase(),
          status: 'complete',
          details: finalResult,
        });
      } else {
        const neutralResult = { 
          signal: 'NEUTRAL', 
          message: 'No strong signal detected',
          ticker: ticker.toUpperCase(),
          timestamp: new Date().toISOString()
        };
        setResult(neutralResult);
        toast.info('Analysis complete but no actionable signal found');
      }
    } catch (error: any) {
      console.error('Analysis error:', error);
      toast.error(`Analysis failed: ${error.message}`);
    } finally {
      setIsRunning(false);
      endOperation(operationId);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-3 relative">
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            placeholder="Enter ticker (e.g., AAPL)"
            disabled={isRunning}
            className="w-full px-4 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:border-cyan-500 focus:outline-none"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                runAnalysis();
              } else if (e.key === 'Escape') {
                setShowSuggestions(false);
              }
            }}
          />
          
          {/* Ticker Suggestions Dropdown */}
          {showSuggestions && (suggestions.length > 0 || searchLoading) && (
            <div className="absolute z-50 w-full mt-1 bg-slate-800 border border-slate-600 rounded-lg shadow-lg max-h-64 overflow-auto">
              {searchLoading && (
                <div className="px-3 py-2 text-sm text-slate-400 flex items-center gap-2">
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  Searching...
                </div>
              )}
              {suggestions.map((asset) => (
                <button
                  key={asset.symbol}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectTicker(asset.symbol);
                  }}
                  className="w-full px-3 py-2 text-left hover:bg-slate-700 flex items-center justify-between"
                >
                  <div>
                    <span className="font-medium text-white">{asset.symbol}</span>
                    {asset.exchange && (
                      <span className="ml-2 text-xs text-slate-500">{asset.exchange}</span>
                    )}
                    <div className="text-xs text-slate-400 truncate">{asset.name}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
        
        <Button
          onClick={runAnalysis}
          disabled={isRunning || !ticker.trim()}
          className="bg-cyan-600 hover:bg-cyan-700"
        >
          {isRunning ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Zap className="w-4 h-4 mr-2" />
              Analyze
            </>
          )}
        </Button>
      </div>

      {result && (
        <div className="p-4 bg-slate-700/30 rounded-lg border border-slate-600/50">
          <div className="flex items-center justify-between mb-3">
            <span className="font-bold text-white text-lg">{ticker}</span>
            <Badge className={
              result.signal === 'BULLISH' 
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50'
                : result.signal === 'BEARISH'
                ? 'bg-red-500/20 text-red-400 border-red-500/50'
                : 'bg-slate-500/20 text-slate-400 border-slate-500/50'
            }>
              {result.signal || 'NEUTRAL'}
              {result.confidence && ` (${result.confidence}%)`}
            </Badge>
          </div>
          
          {result.agent_signals && result.agent_signals.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-slate-400 mb-2">Agent Signals:</div>
              <div className="flex flex-wrap gap-1">
                {result.agent_signals.slice(0, 8).map((sig: any, i: number) => (
                  <span 
                    key={i}
                    className={`text-xs px-2 py-0.5 rounded ${
                      sig.signal === 'BULLISH' ? 'bg-emerald-500/20 text-emerald-400' :
                      sig.signal === 'BEARISH' ? 'bg-red-500/20 text-red-400' :
                      'bg-slate-500/20 text-slate-400'
                    }`}
                  >
                    {sig.agent_name?.split(' ')[0] || 'Agent'}: {sig.signal}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {result.reasoning && (
            <div>
              <div className="text-xs text-slate-400 mb-1">Analysis:</div>
              <p className="text-sm text-slate-300">{result.reasoning}</p>
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-slate-500">
        Quick analysis runs in dry-run mode. Enable autonomous trading for live execution.
      </p>
    </div>
  );
}
