/**
 * Trading Workspace
 * 
 * Unified trading workspace that merges Trading Dashboard + Portfolio Health + Research
 * into a single page with internal tabs.
 * 
 * Tabs:
 * 1. Positions - Open positions with P&L, watchlist
 * 2. Performance - Trading metrics, scheduled tasks, pipeline controls
 * 3. Health - Portfolio health analysis (Mazo AI powered)
 * 4. Research - Embedded Mazo research chat
 */

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useWorkspaceData, dataHydrationService } from '@/services/data-hydration-service';
import { usePortfolioHealth } from '@/contexts/portfolio-health-context';
import { API_BASE_URL } from '@/lib/api-config';
import { toast } from 'sonner';
import { 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  DollarSign,
  PieChart,
  Activity,
  Shield,
  Target,
  Zap,
  BarChart3,
  Clock,
  Play,
  Pause,
  Plus,
  Eye,
  Calendar,
  Award,
  Brain,
  Rocket,
  AlertCircle,
  Settings,
  Search,
  Sparkles,
  Info,
} from 'lucide-react';
import { InfoTooltip, TOOLTIP_CONTENT, WithTooltip, getScheduleDescription } from '@/components/ui/info-tooltip';
import { formatShares } from '@/lib/utils';
import { ResearchTab } from '@/components/panels/bottom/tabs/research-tab';
import { useTabsContext } from '@/contexts/tabs-context';
import { TabService } from '@/services/tab-service';
import { ExternalLink, Layers, Users, ChevronRight } from 'lucide-react';

function formatCurrency(value: number): string {
  const sign = value >= 0 ? '' : '-';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function getGradeColor(grade: string): string {
  if (grade.startsWith('A')) return 'text-emerald-400';
  if (grade.startsWith('B')) return 'text-green-400';
  if (grade.startsWith('C')) return 'text-yellow-400';
  if (grade.startsWith('D')) return 'text-orange-400';
  return 'text-red-400';
}

function getGradeBg(grade: string): string {
  if (grade.startsWith('A')) return 'bg-emerald-500/20 border-emerald-500/50';
  if (grade.startsWith('B')) return 'bg-green-500/20 border-green-500/50';
  if (grade.startsWith('C')) return 'bg-yellow-500/20 border-yellow-500/50';
  if (grade.startsWith('D')) return 'bg-orange-500/20 border-orange-500/50';
  return 'bg-red-500/20 border-red-500/50';
}

function extractGrade(analysis: string): string {
  const gradeMatch = analysis.match(/GRADE:\s*([A-F][+-]?)/i) || 
                     analysis.match(/Grade:\s*([A-F][+-]?)/i) ||
                     analysis.match(/receives a grade of\s*([A-F][+-]?)/i);
  return gradeMatch ? gradeMatch[1] : '?';
}

function extractRiskLevel(analysis: string): string {
  if (analysis.toLowerCase().includes('critical')) return 'CRITICAL';
  if (analysis.toLowerCase().includes('high risk')) return 'HIGH';
  if (analysis.toLowerCase().includes('moderate')) return 'MODERATE';
  if (analysis.toLowerCase().includes('low risk')) return 'LOW';
  return 'UNKNOWN';
}

export function TradingWorkspace() {
  const { openTab } = useTabsContext();

  // Use Workspace slice data
  const {
    performance,
    metrics,
    scheduler,
    automatedStatus,
    recentWorkflows,
    isRefreshing,
    refresh,
  } = useWorkspaceData();

  // Open Round Table (optionally with a specific workflow ID)
  const openRoundTable = (workflowId?: string) => {
    const tabData = TabService.createRoundTableTab(workflowId);
    openTab(tabData);
  };

  // Get latest workflow ID for CTAs
  const latestWorkflowId = recentWorkflows?.[0]?.workflow_id || recentWorkflows?.[0]?.id;

  // Portfolio Health context (still separate - expensive Mazo call)
  const { 
    healthData, 
    loading: healthLoading, 
    error: healthError, 
    lastRefresh: healthLastRefresh, 
    runHealthCheck 
  } = usePortfolioHealth();

  const [showMergeNotice, setShowMergeNotice] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);

  // Fetch watchlist separately 
  const watchlist = automatedStatus?.watchlist || [];

  // Run AI trading cycle
  const runAiTradingCycle = useCallback(async (dryRun: boolean) => {
    setAiLoading(true);
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
      toast.error(`Cycle failed: ${error.message}`);
    } finally {
      setAiLoading(false);
    }
  }, []);

  // Toggle scheduler
  const toggleScheduler = useCallback(async () => {
    try {
      const isRunning = scheduler?.is_running;
      const response = await fetch(`${API_BASE_URL}/trading/scheduler/${isRunning ? 'stop' : 'start'}`, {
        method: 'POST',
      });
      if (response.ok) {
        toast.success(isRunning ? 'Scheduler stopped' : 'Scheduler started');
        await dataHydrationService.backgroundRefresh();
      }
    } catch (error) {
      toast.error('Failed to toggle scheduler');
    }
  }, [scheduler?.is_running]);

  // Refresh data
  const fetchData = useCallback(async () => {
    await dataHydrationService.backgroundRefresh();
  }, []);
  
  const grade = healthData ? extractGrade(healthData.analysis) : '?';
  const riskLevel = healthData ? extractRiskLevel(healthData.analysis) : 'UNKNOWN';

  return (
    <div className="h-full overflow-auto bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        
        {/* Merge Notice Banner */}
        {showMergeNotice && (
          <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Info className="w-5 h-5 text-emerald-400" />
              <div>
                <span className="text-emerald-300 font-medium">Trading Workspace</span>
                <span className="text-emerald-200/70 ml-2">
                  merges Trading Dashboard + Portfolio Health + Research into one place.
                </span>
              </div>
            </div>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setShowMergeNotice(false)}
              className="text-emerald-400 hover:text-emerald-300"
            >
              Dismiss
            </Button>
          </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Trading Workspace
              </h1>
              {scheduler?.is_running && (
                <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/50">
                  <Sparkles className="w-3 h-3 mr-1" />
                  AUTO-TRADING
                </Badge>
              )}
              {healthData && (
                <Badge className={getGradeBg(grade)}>
                  <Shield className="w-3 h-3 mr-1" />
                  Grade: {grade}
                </Badge>
              )}
            </div>
            <p className="text-slate-400 mt-1">
              Positions • Performance • Health Analysis • Research
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button 
              onClick={fetchData} 
              disabled={isRefreshing}
              variant="outline"
              size="sm"
              className="border-slate-600"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Quick Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <Card className="bg-slate-800/50 border-slate-700">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                <DollarSign className="w-3 h-3" />
                Equity
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
                <BarChart3 className="w-3 h-3" />
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
                <Award className="w-3 h-3" />
                Win Rate
              </div>
              <div className="text-xl font-bold text-cyan-400">
                {metrics?.win_rate != null ? `${metrics.win_rate}%` : 'N/A'}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-800/50 border-slate-700">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                <Target className="w-3 h-3" />
                Total P&L
              </div>
              <div className={`text-xl font-bold ${(metrics?.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {formatCurrency(metrics?.total_pnl || 0)}
              </div>
            </CardContent>
          </Card>

          <Card className={`border ${scheduler?.is_running ? 'bg-emerald-500/10 border-emerald-500/50' : 'bg-slate-800/50 border-slate-700'}`}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                <Clock className="w-3 h-3" />
                Scheduler
              </div>
              <Badge className={scheduler?.is_running ? 'bg-emerald-600' : 'bg-slate-600'}>
                {scheduler?.is_running ? 'ACTIVE' : 'STOPPED'}
              </Badge>
            </CardContent>
          </Card>
        </div>

        {/* Error Display - only show health errors since we use global store */}
        {healthError && (
          <Card className="border-red-500/50 bg-red-500/10">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3 text-red-400">
                <XCircle className="w-5 h-5" />
                <span>{healthError}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Main Tabs */}
        <Tabs defaultValue="positions" className="space-y-4">
          <TabsList className="bg-slate-800 border border-slate-700">
            <TabsTrigger value="positions" className="data-[state=active]:bg-slate-700">
              <BarChart3 className="w-4 h-4 mr-2" />
              Positions
            </TabsTrigger>
            <TabsTrigger value="performance" className="data-[state=active]:bg-slate-700">
              <Target className="w-4 h-4 mr-2" />
              Performance
            </TabsTrigger>
            <TabsTrigger value="health" className="data-[state=active]:bg-slate-700">
              <Shield className="w-4 h-4 mr-2" />
              Health
              {healthData && (
                <Badge variant="outline" className={`ml-2 ${getGradeColor(grade)}`}>
                  {grade}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="research" className="data-[state=active]:bg-slate-700">
              <Search className="w-4 h-4 mr-2" />
              Research
            </TabsTrigger>
          </TabsList>

          {/* Positions Tab */}
          <TabsContent value="positions" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Open Positions */}
              <Card className="lg:col-span-2 bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <BarChart3 className="w-5 h-5 text-blue-400" />
                    Open Positions
                    <Badge variant="outline" className="ml-2">{performance?.positions_count || 0}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {isRefreshing && !performance ? (
                    <div className="space-y-3">
                      {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-16 w-full" />
                      ))}
                    </div>
                  ) : !performance?.positions || performance.positions.length === 0 ? (
                    <div className="text-center py-8 text-slate-400">
                      <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No open positions</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {performance.positions.map((pos) => (
                        <div 
                          key={pos.ticker}
                          className="flex items-center justify-between p-4 bg-slate-700/50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <span className="font-bold text-white text-lg">{pos.ticker}</span>
                            <Badge variant="outline" className={pos.side === 'long' ? 'border-emerald-500 text-emerald-400' : 'border-red-500 text-red-400'}>
                              {pos.side.toUpperCase()}
                            </Badge>
                            <span className="text-slate-400">{formatShares(pos.qty)}</span>
                          </div>
                          <div className="text-right">
                            <div className={`font-mono font-bold ${pos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                              {formatCurrency(pos.unrealized_pnl)}
                            </div>
                            <div className="text-sm text-slate-400">
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
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-white">
                      <Eye className="w-5 h-5 text-purple-400" />
                      Watchlist
                      <Badge variant="outline" className="ml-2">{watchlist?.length || 0}</Badge>
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  {!watchlist || watchlist.length === 0 ? (
                    <div className="text-center py-8 text-slate-400">
                      <Eye className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No items in watchlist</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {watchlist.slice(0, 10).map((item) => (
                        <div 
                          key={item.id}
                          className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
                        >
                          <div>
                            <span className="font-semibold text-white">{item.ticker}</span>
                            <div className="text-xs text-slate-400">
                              Target: ${item.entry_target?.toFixed(2) || 'N/A'}
                            </div>
                          </div>
                          <Badge 
                            variant="outline" 
                            className={
                              item.status === 'triggered' 
                                ? 'border-emerald-500 text-emerald-400' 
                                : 'border-slate-500 text-slate-400'
                            }
                          >
                            {item.status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Performance Tab */}
          <TabsContent value="performance" className="space-y-4">
            {/* AI Trading Control Panel */}
            <Card className="bg-gradient-to-r from-purple-900/30 via-indigo-900/30 to-blue-900/30 border-purple-500/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-3 text-white">
                  <Brain className="w-6 h-6 text-purple-400" />
                  AI Trading Pipeline
                  {automatedStatus?.is_running && (
                    <Badge className="bg-purple-600 animate-pulse">RUNNING</Badge>
                  )}
                </CardTitle>
                <CardDescription className="text-slate-300">
                  Strategy Engine → Mazo Validation → AI Analysts → Portfolio Manager → Execution
                  {latestWorkflowId && (
                    <Button 
                      variant="link" 
                      className="text-indigo-400 p-0 h-auto ml-2"
                      onClick={() => openRoundTable(latestWorkflowId)}
                    >
                      View latest cycle in Round Table →
                    </Button>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {/* Alpaca Setup Warning */}
                {automatedStatus && automatedStatus.success === false && automatedStatus.requires_setup?.alpaca && (
                  <div className="mb-4 p-3 rounded-lg bg-amber-900/30 border border-amber-600/50 flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm text-amber-200 font-medium">
                        Alpaca API credentials required
                      </p>
                      <p className="text-xs text-amber-300/80 mt-1">
                        {automatedStatus.message || 'Set ALPACA_API_KEY and ALPACA_SECRET_KEY in Settings.'}
                      </p>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Controls */}
                  <div className="space-y-3">
                    <div className="flex gap-2">
                      <Button
                        onClick={() => runAiTradingCycle(false)}
                        disabled={aiLoading || automatedStatus?.is_running || automatedStatus?.success === false}
                        className="bg-purple-600 hover:bg-purple-700"
                      >
                        {aiLoading ? (
                          <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <Rocket className="w-4 h-4 mr-2" />
                        )}
                        Run AI Cycle
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => runAiTradingCycle(true)}
                        disabled={aiLoading || automatedStatus?.is_running || automatedStatus?.success === false}
                        className="border-purple-500 text-purple-400 hover:bg-purple-500/20"
                      >
                        <Eye className="w-4 h-4 mr-2" />
                        Dry Run
                      </Button>
                      {latestWorkflowId && (
                        <Button
                          variant="outline"
                          onClick={() => openRoundTable(latestWorkflowId)}
                          className="border-indigo-500/50 text-indigo-400 hover:bg-indigo-500/10"
                        >
                          <Layers className="w-4 h-4 mr-2" />
                          Round Table
                        </Button>
                      )}
                    </div>
                    <p className="text-xs text-slate-400">
                      Full cycle: Screen → Validate → Analyze → Decide → Execute
                    </p>
                  </div>
                  
                  {/* Last Run Stats - use latest_cycle or fall back to last_result */}
                  {(() => {
                    const cycle = automatedStatus?.latest_cycle || automatedStatus?.last_result;
                    return (
                      <div className="grid grid-cols-5 gap-2 text-center">
                        <div className="p-2 bg-slate-700/50 rounded-lg">
                          <div className="text-lg font-bold text-white">
                            {cycle?.tickers_screened || 0}
                          </div>
                          <div className="text-xs text-slate-400">Screened</div>
                        </div>
                        <div className="p-2 bg-slate-700/50 rounded-lg">
                          <div className="text-lg font-bold text-cyan-400">
                            {cycle?.signals_found || 0}
                          </div>
                          <div className="text-xs text-slate-400">Signals</div>
                        </div>
                        <div className="p-2 bg-slate-700/50 rounded-lg">
                          <div className="text-lg font-bold text-purple-400">
                            {cycle?.mazo_validated || 0}
                          </div>
                          <div className="text-xs text-slate-400">Validated</div>
                        </div>
                        <div className="p-2 bg-slate-700/50 rounded-lg">
                          <div className="text-lg font-bold text-yellow-400">
                            {cycle?.trades_analyzed || 0}
                          </div>
                          <div className="text-xs text-slate-400">Analyzed</div>
                        </div>
                        <div className="p-2 bg-slate-700/50 rounded-lg">
                          <div className="text-lg font-bold text-emerald-400">
                            {cycle?.trades_executed || 0}
                          </div>
                          <div className="text-xs text-slate-400">Executed</div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Trading Metrics */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Target className="w-5 h-5 text-cyan-400" />
                    Trading Metrics
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {metrics?.has_data === false ? (
                    <div className="p-4 rounded-lg bg-amber-900/20 border border-amber-600/30">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="text-sm text-amber-200 font-medium">No trading data yet</p>
                          <p className="text-xs text-amber-300/70 mt-1">
                            Run an AI trading cycle to see performance metrics.
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 bg-slate-700/50 rounded-lg">
                        <div className="text-slate-400 text-sm">Total P&L</div>
                        <div className={`text-xl font-bold ${(metrics?.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {formatCurrency(metrics?.total_pnl || 0)}
                        </div>
                      </div>
                      <div className="p-3 bg-slate-700/50 rounded-lg">
                        <div className="text-slate-400 text-sm">Avg Return</div>
                        <div className={`text-xl font-bold ${(metrics?.average_return_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {metrics?.average_return_pct != null ? `${metrics.average_return_pct}%` : 'N/A'}
                        </div>
                      </div>
                      <div className="p-3 bg-slate-700/50 rounded-lg">
                        <div className="text-slate-400 text-sm">Profit Factor</div>
                        <div className="text-xl font-bold text-cyan-400">
                          {metrics?.profit_factor != null ? metrics.profit_factor : 'N/A'}
                        </div>
                      </div>
                      <div className="p-3 bg-slate-700/50 rounded-lg">
                        <div className="text-slate-400 text-sm">Avg Hold Time</div>
                        <div className="text-xl font-bold text-purple-400">
                          {metrics?.average_holding_hours != null ? `${metrics.average_holding_hours}h` : 'N/A'}
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Scheduler */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-white">
                      <Calendar className="w-5 h-5 text-orange-400" />
                      Scheduled Tasks
                      <Badge className={scheduler?.is_running ? 'bg-emerald-600' : 'bg-slate-600'}>
                        {scheduler?.is_running ? 'ACTIVE' : 'STOPPED'}
                      </Badge>
                    </CardTitle>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={toggleScheduler}
                      className={scheduler?.is_running ? 'border-red-500 text-red-400' : 'border-emerald-500 text-emerald-400'}
                    >
                      {scheduler?.is_running ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {!scheduler?.scheduled_tasks || scheduler.scheduled_tasks.length === 0 ? (
                    <div className="text-center py-4 text-slate-400">
                      <Calendar className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>No scheduled tasks</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {scheduler.scheduled_tasks.slice(0, 6).map((task) => (
                        <div 
                          key={task.id}
                          className="flex items-center justify-between p-2 bg-slate-700/50 rounded-lg text-sm"
                        >
                          <span className="text-white truncate">{task.name}</span>
                          <span className="text-cyan-400 text-xs">
                            {task.next_run ? new Date(task.next_run).toLocaleTimeString() : 'N/A'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Health Tab */}
          <TabsContent value="health" className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-white">Portfolio Health Analysis</h2>
                <p className="text-slate-400 text-sm">Powered by Mazo AI</p>
              </div>
              <Button 
                onClick={runHealthCheck} 
                disabled={healthLoading}
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${healthLoading ? 'animate-spin' : ''}`} />
                {healthLoading ? 'Analyzing...' : 'Run Health Check'}
              </Button>
            </div>

            {healthError && (
              <Card className="border-red-500/50 bg-red-500/10">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3 text-red-400">
                    <XCircle className="w-5 h-5" />
                    <span>{healthError}</span>
                  </div>
                </CardContent>
              </Card>
            )}

            {!healthData && !healthLoading && (
              <Card className="bg-slate-800/50 border-slate-700">
                <CardContent className="py-16 text-center">
                  <Shield className="w-16 h-16 mx-auto mb-4 text-slate-500" />
                  <h3 className="text-xl font-semibold text-white mb-2">No Health Check Data Yet</h3>
                  <p className="text-slate-400 mb-6 max-w-md mx-auto">
                    Click "Run Health Check" to get a comprehensive analysis of your portfolio 
                    powered by Mazo AI.
                  </p>
                  <Button 
                    onClick={runHealthCheck}
                    className="bg-gradient-to-r from-blue-600 to-purple-600"
                  >
                    <Zap className="w-4 h-4 mr-2" />
                    Run Health Check Now
                  </Button>
                </CardContent>
              </Card>
            )}

            {healthLoading && !healthData && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <Card key={i} className="bg-slate-800/50 border-slate-700">
                    <CardHeader><Skeleton className="h-4 w-24" /></CardHeader>
                    <CardContent><Skeleton className="h-8 w-32" /></CardContent>
                  </Card>
                ))}
              </div>
            )}

            {healthData && (
              <>
                {/* Health Overview Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className={`${getGradeBg(grade)} border`}>
                    <CardHeader className="pb-2">
                      <CardDescription className="text-slate-300 flex items-center gap-2">
                        <Shield className="w-4 h-4" />
                        Health Grade
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className={`text-5xl font-black ${getGradeColor(grade)}`}>
                        {grade}
                      </div>
                      <Badge 
                        variant="outline" 
                        className={`mt-2 ${
                          riskLevel === 'CRITICAL' ? 'border-red-500 text-red-400' :
                          riskLevel === 'HIGH' ? 'border-orange-500 text-orange-400' :
                          riskLevel === 'MODERATE' ? 'border-yellow-500 text-yellow-400' :
                          'border-green-500 text-green-400'
                        }`}
                      >
                        {riskLevel} RISK
                      </Badge>
                    </CardContent>
                  </Card>

                  <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader className="pb-2">
                      <CardDescription className="text-slate-400 flex items-center gap-2">
                        <DollarSign className="w-4 h-4" />
                        Total Equity
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold text-white">
                        {formatCurrency(healthData.portfolio.equity)}
                      </div>
                      <div className="text-sm text-slate-400 mt-1">
                        Buying Power: {formatCurrency(healthData.portfolio.buying_power)}
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader className="pb-2">
                      <CardDescription className="text-slate-400 flex items-center gap-2">
                        <PieChart className="w-4 h-4" />
                        Available Cash
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold text-emerald-400">
                        {formatCurrency(healthData.portfolio.cash)}
                      </div>
                      <div className="text-sm text-slate-400 mt-1">
                        {((healthData.portfolio.cash / healthData.portfolio.equity) * 100).toFixed(1)}% of equity
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader className="pb-2">
                      <CardDescription className="text-slate-400 flex items-center gap-2">
                        <Target className="w-4 h-4" />
                        Confidence
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold text-purple-400">
                        {((healthData.confidence || 0) * 100).toFixed(0)}%
                      </div>
                      <div className="text-sm text-slate-400 mt-1">
                        Analysis in {(healthData.execution_time_ms / 1000).toFixed(1)}s
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* AI Analysis Summary */}
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-white">
                      <Brain className="w-5 h-5 text-purple-400" />
                      AI Analysis
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="prose prose-invert prose-sm max-w-none">
                      <pre className="whitespace-pre-wrap text-slate-300 text-sm bg-slate-900/50 p-4 rounded-lg overflow-auto max-h-64">
                        {healthData.analysis}
                      </pre>
                    </div>
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>

          {/* Research Tab */}
          <TabsContent value="research" className="space-y-4">
            <Card className="bg-slate-800/50 border-slate-700 h-[600px]">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-white">
                  <Search className="w-5 h-5 text-blue-400" />
                  Mazo Research
                </CardTitle>
                <CardDescription>
                  Ask anything about markets, companies, or trading strategies
                </CardDescription>
              </CardHeader>
              <CardContent className="h-[calc(100%-80px)]">
                <ResearchTab className="h-full" />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
