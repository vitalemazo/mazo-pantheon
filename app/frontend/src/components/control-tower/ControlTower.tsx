/**
 * Control Tower
 * 
 * Unified command center for AI-powered autonomous trading.
 * Merges AI Hedge Fund + Command Center into a single "source of truth" page.
 * 
 * Key sections:
 * 1. Mission Console - Autopilot controls, run/dry-run, cycle history
 * 2. Quick Stats - Portfolio metrics at a glance
 * 3. Universe View - Positions + Watchlist + Rotation candidates unified
 * 4. Agent Consensus - Signal summary with Round Table links
 * 5. Status Widgets - Scheduler, guardrails, small account mode
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '@/lib/api-config';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  useControlTowerData,
  useIntelligenceData,
  dataHydrationService,
  type Position,
} from '@/services/data-hydration-service';
import { useTabsContext } from '@/contexts/tabs-context';
import { TabService } from '@/services/tab-service';
import { toast } from 'sonner';
import { 
  Play, 
  TrendingUp,
  TrendingDown,
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
  Lock,
  Clock,
  History,
  DollarSign,
  Award,
  AlertTriangle,
  Rocket,
  ExternalLink,
  Layers,
  TrendingUp as TrendUp,
  Settings,
  Info,
} from 'lucide-react';
import { InfoTooltip, TOOLTIP_CONTENT, WithTooltip, getScheduleDescription } from '@/components/ui/info-tooltip';
import { formatShares } from '@/lib/utils';
import useSWR from 'swr';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const fetcher = (url: string) => fetch(url).then(res => res.json());

// Risk presets - max positions scale with account size
const RISK_PRESETS = {
  conservative: { maxPositions: 5, stopLossPercent: 3, takeProfitPercent: 6, budgetPercent: 15 },
  balanced: { maxPositions: 10, stopLossPercent: 5, takeProfitPercent: 10, budgetPercent: 25 },
  aggressive: { maxPositions: 15, stopLossPercent: 8, takeProfitPercent: 15, budgetPercent: 40 },
  diversified: { maxPositions: 25, stopLossPercent: 5, takeProfitPercent: 12, budgetPercent: 50 },
};

interface TradingConfig {
  budgetPercent: number;
  riskLevel: 'conservative' | 'balanced' | 'aggressive' | 'diversified';
  maxPositions: number;
  stopLossPercent: number;
  takeProfitPercent: number;
}

function formatCurrency(value: number): string {
  const sign = value >= 0 ? '' : '-';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function ControlTower() {
  const { openTab } = useTabsContext();
  
  // Use Control Tower slice data
  const { 
    performance, 
    scheduler, 
    metrics,
    trades,
    recentWorkflows,
    automatedStatus,
    isAutonomousEnabled,
    tradingConfig,
    setAutonomousEnabled,
    setTradingConfig,
    addAIActivity,
    isRefreshing,
  } = useControlTowerData();

  // Intelligence panel actions for workflow progress
  const {
    addAgentActivity,
    setLiveWorkflowProgress,
    updateWorkflowProgress,
  } = useIntelligenceData();

  // Fetch trading guardrails status
  const { data: guardrailsData } = useSWR(
    `${API_BASE_URL}/monitoring/trading/guardrails`,
    fetcher,
    { refreshInterval: 30000 }
  );

  // Fetch small account mode status
  const { data: smallAccountData } = useSWR(
    `${API_BASE_URL}/trading/small-account-mode`,
    fetcher,
    { refreshInterval: 30000 }
  );

  // State for Danelfin ticker selection (use first position or latest workflow ticker)
  const [danelfinTicker, setDanelfinTicker] = useState<string>('');

  // Get latest ticker from positions or workflows
  useEffect(() => {
    if (!danelfinTicker) {
      // Try to get from positions first
      if (performance?.positions && performance.positions.length > 0) {
        setDanelfinTicker(performance.positions[0].ticker);
      } else if (recentWorkflows && recentWorkflows.length > 0) {
        // Try to get from recent workflows
        const firstTicker = recentWorkflows[0]?.tickers?.[0];
        if (firstTicker) {
          setDanelfinTicker(firstTicker);
        }
      }
    }
  }, [performance?.positions, recentWorkflows, danelfinTicker]);

  // Fetch Danelfin scores for selected ticker
  const { data: danelfinData, isLoading: danelfinLoading } = useSWR(
    danelfinTicker ? `${API_BASE_URL}/ai/danelfin/score/${danelfinTicker}` : null,
    fetcher,
    { refreshInterval: 300000 } // Refresh every 5 minutes (scores don't change often)
  );

  // Fetch watchlist
  const { data: watchlistData } = useSWR(
    `${API_BASE_URL}/trading/watchlist`,
    fetcher,
    { refreshInterval: 60000 }
  );

  // Fetch user's saved risk settings from backend
  const { data: userSettings, mutate: mutateUserSettings } = useSWR(
    `${API_BASE_URL}/system/user/risk-settings`,
    fetcher,
    { revalidateOnFocus: false }
  );

  // Local UI state
  const [isStarting, setIsStarting] = useState(false);
  const [showMergeNotice, setShowMergeNotice] = useState(true);
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  // Map store config to component config format, preferring saved settings
  const savedSettings = userSettings?.settings;
  const config: TradingConfig = {
    budgetPercent: savedSettings?.budget_percent ?? tradingConfig?.budgetPercent ?? 25,
    riskLevel: (savedSettings?.risk_level ?? tradingConfig?.riskLevel ?? 'balanced') as TradingConfig['riskLevel'],
    maxPositions: savedSettings?.max_positions ?? tradingConfig?.maxPositions ?? 5,
    stopLossPercent: savedSettings?.stop_loss_percent ?? tradingConfig?.stopLossPercent ?? 5,
    takeProfitPercent: savedSettings?.take_profit_percent ?? tradingConfig?.takeProfitPercent ?? 10,
  };
  
  const setConfig = (updater: TradingConfig | ((prev: TradingConfig) => TradingConfig)) => {
    if (typeof updater === 'function') {
      setTradingConfig(updater(config));
    } else {
      setTradingConfig(updater);
    }
  };

  // Save settings to backend
  const saveSettingsToBackend = async (newConfig: TradingConfig) => {
    setIsSavingSettings(true);
    try {
      const response = await fetch(`${API_BASE_URL}/system/user/risk-settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          risk_level: newConfig.riskLevel,
          max_positions: newConfig.maxPositions,
          stop_loss_percent: newConfig.stopLossPercent,
          take_profit_percent: newConfig.takeProfitPercent,
          budget_percent: newConfig.budgetPercent,
        }),
      });
      
      if (response.ok) {
        await mutateUserSettings();
        toast.success(`Risk settings saved: ${newConfig.riskLevel}`);
      } else {
        toast.error('Failed to save settings');
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast.error('Failed to save settings');
    } finally {
      setIsSavingSettings(false);
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
        await dataHydrationService.backgroundRefresh();
      }
    } catch (error) {
      toast.error('Failed to toggle autonomous mode');
    } finally {
      setIsStarting(false);
    }
  };

  // Run one AI cycle manually
  const runManualCycle = async (dryRun: boolean = false) => {
    setIsStarting(true);
    const workflowId = `cycle_${Date.now()}`;

    setLiveWorkflowProgress({
      workflowId,
      status: 'running',
      startedAt: new Date().toISOString(),
      agentsTotal: 18,
      agentsComplete: 0,
      agentStatuses: {},
      signals: {},
    });

    addAgentActivity({
      timestamp: new Date().toISOString(),
      type: 'workflow_start',
      message: dryRun ? 'Starting Dry Run Cycle' : 'Starting AI Trading Cycle',
    });

    try {
      const response = await fetch(`${API_BASE_URL}/trading/automated/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          execute_trades: !dryRun,
          dry_run: dryRun,
        }),
      });

      const result = await response.json();

      if (result.success !== false) {
        updateWorkflowProgress({
          status: 'complete',
          completedAt: new Date().toISOString(),
          agentsComplete: 18,
        });

        toast.success(
          dryRun 
            ? `Dry run complete: ${result.result?.signals_found || 0} signals found`
            : `Cycle complete: ${result.result?.trades_executed || 0} trades executed`
        );
        await dataHydrationService.backgroundRefresh();
      } else {
        throw new Error(result.error || 'Cycle failed');
      }
    } catch (error: any) {
      updateWorkflowProgress({ status: 'error' });
      toast.error(`Cycle failed: ${error.message}`);
    } finally {
      setIsStarting(false);
    }
  };

  // Handle risk level change - update local state AND save to backend
  const handleRiskChange = async (level: TradingConfig['riskLevel']) => {
    const preset = RISK_PRESETS[level];
    const newConfig = {
      ...config,
      riskLevel: level,
      ...preset,
    };
    
    // Update local state immediately
    setConfig(newConfig);
    
    // Save to backend (async)
    await saveSettingsToBackend(newConfig);
  };

  // Handle manual refresh
  const handleRefresh = async () => {
    await dataHydrationService.backgroundRefresh();
  };

  // Open Round Table (optionally with a specific workflow ID)
  const openRoundTable = (workflowId?: string) => {
    const tabData = TabService.createRoundTableTab(workflowId);
    openTab(tabData);
  };

  // Get latest workflow ID for CTAs
  const latestWorkflowId = recentWorkflows?.[0]?.workflow_id || recentWorkflows?.[0]?.id;

  // Positions from performance data
  const positions = performance?.positions || [];
  const watchlist = watchlistData?.items || [];

  return (
    <TooltipProvider>
      <div className="h-full overflow-auto bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <div className="max-w-7xl mx-auto p-6 space-y-6">
          
          {/* Merge Notice Banner */}
          {showMergeNotice && (
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Info className="w-5 h-5 text-blue-400" />
                <div>
                  <span className="text-blue-300 font-medium">New! Control Tower</span>
                  <span className="text-blue-200/70 ml-2">
                    merges AI Hedge Fund + Command Center into a unified experience.
                  </span>
                </div>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setShowMergeNotice(false)}
                className="text-blue-400 hover:text-blue-300"
              >
                Dismiss
              </Button>
            </div>
          )}

          {/* Mission Console Header */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-900/50 via-purple-900/50 to-blue-900/50 border border-indigo-500/30 p-6">
            <div className="absolute inset-0 bg-grid-white/5" />
            <div className="relative">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-xl bg-indigo-500/20 border border-indigo-500/50">
                    <Rocket className="w-8 h-8 text-indigo-400" />
                  </div>
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <h1 className="text-3xl font-bold text-white">Control Tower</h1>
                      {isAutonomousEnabled && (
                        <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/50 animate-pulse">
                          <Sparkles className="w-3 h-3 mr-1" />
                          AUTOPILOT
                        </Badge>
                      )}
                      {smallAccountData?.small_account_mode?.active && (
                        <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/50">
                          <Zap className="w-3 h-3 mr-1" />
                          SMALL ACCOUNT
                        </Badge>
                      )}
                    </div>
                    <p className="text-slate-400">
                      Unified command center • 18 AI analysts • Autonomous execution
                    </p>
                  </div>
                </div>
                
                {/* Autopilot Toggle */}
                <div className={`p-4 rounded-xl border-2 transition-all duration-300 ${
                  isAutonomousEnabled 
                    ? 'bg-emerald-500/10 border-emerald-500/50' 
                    : 'bg-slate-800/50 border-slate-600'
                }`}>
                  <div className="flex items-center gap-4">
                    <Switch
                      checked={isAutonomousEnabled}
                      onCheckedChange={toggleAutonomous}
                      disabled={isStarting}
                      className="scale-125"
                    />
                    <div className="text-left">
                      <div className="text-white font-semibold flex items-center gap-2">
                        {isAutonomousEnabled ? 'Autopilot ON' : 'Autopilot OFF'}
                        <InfoTooltip content={TOOLTIP_CONTENT.autonomousMode} side="bottom" />
                      </div>
                      <div className="text-sm text-slate-400">
                        {isAutonomousEnabled ? 'AI team is trading' : 'Click to enable'}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Quick Action Buttons */}
              <div className="flex items-center gap-3 mt-4">
                <Button
                  onClick={() => runManualCycle(false)}
                  disabled={isStarting}
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Run AI Cycle
                </Button>
                <Button
                  onClick={() => runManualCycle(true)}
                  disabled={isStarting}
                  variant="outline"
                  className="border-slate-600"
                >
                  <Eye className="w-4 h-4 mr-2" />
                  Dry Run
                </Button>
                <Button
                  onClick={() => openRoundTable(latestWorkflowId)}
                  variant="outline"
                  className="border-indigo-500/50 text-indigo-400 hover:bg-indigo-500/10"
                >
                  <Layers className="w-4 h-4 mr-2" />
                  View Round Table
                  <ExternalLink className="w-3 h-3 ml-2" />
                </Button>
                <div className="flex-1" />
                <Button
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                  variant="ghost"
                  size="sm"
                  className="text-slate-400"
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            </div>
          </div>

          {/* Quick Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <DollarSign className="w-3 h-3" />
                  Equity
                  <InfoTooltip content={TOOLTIP_CONTENT.totalEquity} />
                </div>
                <div className="text-xl font-bold text-white">
                  {formatCurrency(performance?.equity || 0)}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  {(performance?.total_unrealized_pnl || 0) >= 0 ? (
                    <TrendingUp className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <TrendingDown className="w-3 h-3 text-red-400" />
                  )}
                  Unrealized P&L
                </div>
                <div className={`text-xl font-bold ${(performance?.total_unrealized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {formatCurrency(performance?.total_unrealized_pnl || 0)}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <Activity className="w-3 h-3" />
                  Positions
                </div>
                <div className="text-xl font-bold text-white">
                  {performance?.positions_count || 0}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <History className="w-3 h-3" />
                  Total Trades
                </div>
                <div className="text-xl font-bold text-cyan-400">
                  {metrics?.total_trades || 0}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <Award className="w-3 h-3" />
                  Win Rate
                </div>
                <div className="text-xl font-bold text-purple-400">
                  {metrics?.win_rate != null ? `${metrics.win_rate}%` : 'N/A'}
                </div>
              </CardContent>
            </Card>

            {/* Guardrails Badge */}
            <Card className={`border ${
              guardrailsData?.pdt_status?.can_day_trade 
                ? 'bg-slate-800/50 border-slate-700' 
                : 'bg-amber-500/10 border-amber-500/50'
            }`}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <Shield className="w-3 h-3" />
                  PDT Status
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xl font-bold ${
                    guardrailsData?.pdt_status?.can_day_trade ? 'text-white' : 'text-amber-400'
                  }`}>
                    {guardrailsData?.pdt_status?.daytrade_count || 0}/3
                  </span>
                  {!guardrailsData?.pdt_status?.can_day_trade && (
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Main Content - Tabs */}
          <Tabs defaultValue="universe" className="space-y-4">
            <TabsList className="bg-slate-800 border border-slate-700">
              <TabsTrigger value="universe" className="data-[state=active]:bg-slate-700">
                <Layers className="w-4 h-4 mr-2" />
                Universe
              </TabsTrigger>
              <TabsTrigger value="budget" className="data-[state=active]:bg-slate-700">
                <Target className="w-4 h-4 mr-2" />
                Budget & Risk
              </TabsTrigger>
              <TabsTrigger value="history" className="data-[state=active]:bg-slate-700">
                <History className="w-4 h-4 mr-2" />
                Cycle History
              </TabsTrigger>
              <TabsTrigger value="agents" className="data-[state=active]:bg-slate-700">
                <Users className="w-4 h-4 mr-2" />
                AI Team
              </TabsTrigger>
            </TabsList>

            {/* Universe Tab - Positions + Watchlist */}
            <TabsContent value="universe" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Open Positions */}
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-white text-lg">
                      <BarChart3 className="w-5 h-5 text-emerald-400" />
                      Open Positions
                      <Badge variant="outline" className="ml-2">{positions.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {positions.length === 0 ? (
                      <div className="text-center py-8 text-slate-500">
                        <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p>No open positions</p>
                        <p className="text-xs mt-1">Run an AI cycle to find opportunities</p>
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {positions.map((pos: Position) => (
                          <div 
                            key={pos.ticker}
                            className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 hover:bg-slate-900/70 transition-colors"
                          >
                            <div>
                              <div className="font-medium text-white">{pos.ticker}</div>
                              <div className="text-xs text-slate-400">
                                {formatShares(pos.qty)} @ {pos.avg_entry_price ? formatCurrency(pos.avg_entry_price) : 'N/A'}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className={`font-medium ${pos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                {formatCurrency(pos.unrealized_pnl)}
                              </div>
                              <div className={`text-xs ${pos.unrealized_pnl_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                {formatPercent(pos.unrealized_pnl_pct)}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Watchlist */}
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-white text-lg">
                      <Eye className="w-5 h-5 text-blue-400" />
                      Watchlist
                      <Badge variant="outline" className="ml-2">{watchlist.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {watchlist.length === 0 ? (
                      <div className="text-center py-8 text-slate-500">
                        <Eye className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p>No items in watchlist</p>
                        <p className="text-xs mt-1">Add tickers to track opportunities</p>
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {watchlist.slice(0, 10).map((item: any) => (
                          <div 
                            key={item.ticker}
                            className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 hover:bg-slate-900/70 transition-colors"
                          >
                            <div>
                              <div className="font-medium text-white">{item.ticker}</div>
                              <div className="text-xs text-slate-400">{item.reason || 'Watching'}</div>
                            </div>
                            <Badge className={
                              item.status === 'watching' ? 'bg-blue-500/20 text-blue-400' :
                              item.status === 'triggered' ? 'bg-emerald-500/20 text-emerald-400' :
                              'bg-slate-500/20 text-slate-400'
                            }>
                              {item.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Scheduler Status */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-white text-lg">
                    <Clock className="w-5 h-5 text-orange-400" />
                    Scheduled Tasks
                    <Badge className={scheduler?.is_running ? 'bg-emerald-600' : 'bg-slate-600'}>
                      {scheduler?.is_running ? 'RUNNING' : 'STOPPED'}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {scheduler?.scheduled_tasks?.map((task: any) => (
                      <div key={task.id} className="p-3 rounded-lg bg-slate-900/50">
                        <div className="font-medium text-white">{task.name}</div>
                        <div className="text-xs text-slate-400 mt-1">
                          {task.next_run 
                            ? `Next: ${new Date(task.next_run).toLocaleTimeString()}`
                            : 'Not scheduled'
                          }
                        </div>
                        <div className="text-xs text-slate-500 mt-1">
                          {getScheduleDescription(task.trigger)}
                        </div>
                      </div>
                    )) || (
                      <div className="col-span-3 text-center py-4 text-slate-500">
                        No scheduled tasks. Enable autopilot to start.
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Budget & Risk Tab */}
            <TabsContent value="budget" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Portfolio Overview */}
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-white">
                      <Wallet className="w-5 h-5 text-blue-400" />
                      Portfolio
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
                        <div className="text-sm text-slate-400">Cash</div>
                        <div className="text-lg font-semibold text-emerald-400">
                          {formatCurrency(cashAvailable)}
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-slate-400">Buying Power</div>
                        <div className="text-lg font-semibold text-blue-400">
                          {formatCurrency(performance?.buying_power || 0)}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Budget Allocation */}
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-white">
                      <Target className="w-5 h-5 text-purple-400" />
                      AI Budget
                      <InfoTooltip content={TOOLTIP_CONTENT.budgetAllocation} />
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm text-slate-400">Allocation</span>
                        <span className="text-xl font-bold text-purple-400">{config.budgetPercent}%</span>
                      </div>
                      <Slider
                        value={[config.budgetPercent]}
                        onValueChange={(value) => setConfig(prev => ({ ...prev, budgetPercent: value[0] }))}
                        onValueCommit={(value) => {
                          // Save to backend when user finishes dragging
                          const newConfig = { ...config, budgetPercent: value[0] };
                          saveSettingsToBackend(newConfig);
                        }}
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
                    </div>
                    {isAutonomousEnabled && (
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <Lock className="w-3 h-3" />
                        Pause trading to adjust
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Risk Level */}
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-white">
                      <Shield className="w-5 h-5 text-orange-400" />
                      Risk Level
                      <InfoTooltip content={TOOLTIP_CONTENT.riskLevel} />
                      {isSavingSettings && (
                        <RefreshCw className="w-4 h-4 text-slate-400 animate-spin ml-2" />
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-4 gap-2">
                      {(['conservative', 'balanced', 'aggressive', 'diversified'] as const).map((level) => (
                        <Button
                          key={level}
                          variant={config.riskLevel === level ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => handleRiskChange(level)}
                          disabled={isAutonomousEnabled || isSavingSettings}
                          className={config.riskLevel === level
                            ? level === 'conservative' ? 'bg-blue-600 hover:bg-blue-700'
                            : level === 'balanced' ? 'bg-purple-600 hover:bg-purple-700'
                            : level === 'aggressive' ? 'bg-red-600 hover:bg-red-700'
                            : 'bg-emerald-600 hover:bg-emerald-700'
                            : 'border-slate-600 hover:border-slate-500'
                          }
                        >
                          {level === 'diversified' ? 'Diversified' : level.charAt(0).toUpperCase() + level.slice(1)}
                        </Button>
                      ))}
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Max Positions</span>
                        <span className="text-white">{config.maxPositions}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Stop Loss</span>
                        <span className="text-red-400">{config.stopLossPercent}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Take Profit</span>
                        <span className="text-emerald-400">{config.takeProfitPercent}%</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Cycle History Tab */}
            <TabsContent value="history" className="space-y-4">
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <History className="w-5 h-5 text-cyan-400" />
                    Recent Cycles
                  </CardTitle>
                  <CardDescription>
                    Last 10 automated trading cycles
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {(!recentWorkflows || recentWorkflows.length === 0) ? (
                    <div className="text-center py-8 text-slate-500">
                      <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>No cycle history yet</p>
                      <p className="text-xs mt-1">Run an AI cycle to see history</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {recentWorkflows.slice(0, 10).map((workflow: any) => (
                        <div 
                          key={workflow.id}
                          className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 hover:bg-slate-900/70 transition-colors cursor-pointer group"
                          onClick={() => openRoundTable(workflow.workflow_id || workflow.id)}
                        >
                          <div className="flex items-center gap-3">
                            <div className={`w-2 h-2 rounded-full ${
                              workflow.status === 'complete' ? 'bg-emerald-400' :
                              workflow.status === 'running' ? 'bg-blue-400 animate-pulse' :
                              workflow.status === 'error' ? 'bg-red-400' :
                              'bg-slate-400'
                            }`} />
                            <div>
                              <div className="font-medium text-white">
                                {workflow.workflow_type || 'Trading Cycle'}
                              </div>
                              <div className="text-xs text-slate-400">
                                {new Date(workflow.started_at).toLocaleString()}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            {workflow.trades_executed !== undefined && (
                              <Badge className="bg-emerald-500/20 text-emerald-400">
                                {workflow.trades_executed} trades
                              </Badge>
                            )}
                            <span className="text-xs text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity">
                              View in Round Table
                            </span>
                            <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-indigo-400" />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Recent Trades */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Zap className="w-5 h-5 text-amber-400" />
                    Recent Trades
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {(!trades || trades.length === 0) ? (
                    <div className="text-center py-8 text-slate-500">
                      <Zap className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>No recent trades</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {trades.slice(0, 10).map((trade: any) => (
                        <div 
                          key={trade.id}
                          className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50"
                        >
                          <div className="flex items-center gap-3">
                            <Badge className={
                              trade.action === 'buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                            }>
                              {trade.action?.toUpperCase()}
                            </Badge>
                            <div>
                              <div className="font-medium text-white">{trade.ticker}</div>
                              <div className="text-xs text-slate-400">
                                {formatShares(trade.quantity)} @ {formatCurrency(trade.entry_price || 0)}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            {trade.realized_pnl != null && (
                              <div className={`font-medium ${trade.realized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                {formatCurrency(trade.realized_pnl)}
                              </div>
                            )}
                            <div className="text-xs text-slate-400">
                              {trade.status}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* AI Team Tab */}
            <TabsContent value="agents" className="space-y-4">
              {/* Danelfin AI Scores Card */}
              <Card className="bg-gradient-to-br from-purple-900/30 to-indigo-900/30 border-purple-500/30">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between text-white">
                    <div className="flex items-center gap-2">
                      <Zap className="w-5 h-5 text-yellow-400" />
                      Danelfin AI Scores
                    </div>
                    {danelfinData?.success && (
                      <Badge className={
                        danelfinData.ai_score >= 8 ? 'bg-green-500/20 text-green-400 border-green-500/30' :
                        danelfinData.ai_score >= 6 ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' :
                        danelfinData.ai_score >= 4 ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' :
                        'bg-red-500/20 text-red-400 border-red-500/30'
                      }>
                        {danelfinData.signal?.replace('_', ' ').toUpperCase()}
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription className="flex items-center gap-2">
                    External AI validation for your trades
                    {performance?.positions && performance.positions.length > 0 && (
                      <select
                        value={danelfinTicker}
                        onChange={(e) => setDanelfinTicker(e.target.value)}
                        className="ml-2 bg-slate-700 border-slate-600 rounded px-2 py-1 text-xs text-white"
                      >
                        {performance.positions.map((pos: Position) => (
                          <option key={pos.ticker} value={pos.ticker}>{pos.ticker}</option>
                        ))}
                      </select>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!danelfinTicker ? (
                    <div className="text-center py-6 text-slate-500">
                      <Zap className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">No positions to analyze</p>
                      <p className="text-xs mt-1">Add positions to see Danelfin AI scores</p>
                    </div>
                  ) : danelfinLoading ? (
                    <div className="text-center py-6 text-slate-400">
                      <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin" />
                      <p className="text-sm">Loading Danelfin scores...</p>
                    </div>
                  ) : danelfinData?.success ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-sm mb-4">
                        <span className="text-slate-400">Ticker: <span className="text-white font-bold">{danelfinData.ticker}</span></span>
                        <span className="text-xs text-slate-500">Updated: {danelfinData.date}</span>
                      </div>
                      
                      {/* Score Grid */}
                      <div className="grid grid-cols-5 gap-2">
                        {[
                          { label: 'AI Score', value: danelfinData.ai_score, key: 'ai_score', color: 'purple' },
                          { label: 'Technical', value: danelfinData.technical, key: 'technical', color: 'blue' },
                          { label: 'Fundamental', value: danelfinData.fundamental, key: 'fundamental', color: 'green' },
                          { label: 'Sentiment', value: danelfinData.sentiment, key: 'sentiment', color: 'yellow' },
                          { label: 'Low Risk', value: danelfinData.low_risk, key: 'low_risk', color: 'cyan' },
                        ].map((score) => (
                          <div
                            key={score.key}
                            className={`text-center p-2 rounded-lg ${
                              danelfinData.highest_category === score.key
                                ? `bg-${score.color}-500/30 border border-${score.color}-500/50 ring-1 ring-${score.color}-400`
                                : 'bg-slate-700/50'
                            }`}
                          >
                            <div className={`text-2xl font-bold ${
                              score.value >= 8 ? 'text-green-400' :
                              score.value >= 6 ? 'text-blue-400' :
                              score.value >= 4 ? 'text-yellow-400' :
                              'text-red-400'
                            }`}>
                              {score.value}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">{score.label}</div>
                            {danelfinData.highest_category === score.key && (
                              <Badge className="mt-1 text-[10px] bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                                Highest
                              </Badge>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Track Record */}
                      {(danelfinData.buy_track_record !== null || danelfinData.sell_track_record !== null) && (
                        <div className="flex items-center justify-center gap-4 mt-3 pt-3 border-t border-slate-700">
                          {danelfinData.buy_track_record && (
                            <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                              <CheckCircle className="w-3 h-3 mr-1" /> Buy Track Record
                            </Badge>
                          )}
                          {danelfinData.sell_track_record && (
                            <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                              <AlertCircle className="w-3 h-3 mr-1" /> Sell Track Record
                            </Badge>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-6 text-slate-500">
                      <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">{danelfinData?.error || 'Danelfin not configured'}</p>
                      <p className="text-xs mt-1">Add your API key in Settings → API Keys</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* AI Team Performance Card */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Users className="w-5 h-5 text-purple-400" />
                    AI Team Performance
                  </CardTitle>
                  <CardDescription>
                    18 specialized analysts working together.{' '}
                    {latestWorkflowId && (
                      <Button 
                        variant="link" 
                        className="text-indigo-400 p-0 h-auto"
                        onClick={() => openRoundTable(latestWorkflowId)}
                      >
                        View latest analysis in Round Table →
                      </Button>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-8 text-slate-500">
                    <Brain className="w-10 h-10 mx-auto mb-3 opacity-50" />
                    <p className="text-base">Agent performance tracked in Round Table</p>
                    <p className="text-sm mt-2">
                      Run an AI cycle to see agent signals and consensus
                    </p>
                    <Button 
                      className="mt-4 border-indigo-500/50 text-indigo-400 hover:bg-indigo-500/10"
                      variant="outline"
                      onClick={() => openRoundTable(latestWorkflowId)}
                    >
                      <Layers className="w-4 h-4 mr-2" />
                      Open Round Table
                      <ExternalLink className="w-3 h-3 ml-2" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

        </div>
      </div>
    </TooltipProvider>
  );
}
