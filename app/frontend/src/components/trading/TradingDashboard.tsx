import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useTradingDashboard } from '@/contexts/trading-dashboard-context';
import { 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  DollarSign,
  Target,
  BarChart3,
  Clock,
  Play,
  Pause,
  Plus,
  Eye,
  Zap,
  Calendar,
  Award,
  Brain,
  Rocket,
  AlertCircle,
  Settings
} from 'lucide-react';

function formatCurrency(value: number): string {
  const sign = value >= 0 ? '' : '-';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function TradingDashboard() {
  // Use context - data persists across tab switches and auto-refreshes in background!
  const {
    performance,
    metrics,
    scheduler,
    watchlist,
    automatedStatus,
    loading,
    aiLoading,
    error,
    lastRefresh,
    fetchData,
    toggleScheduler,
    addDefaultSchedule,
    runAiTradingCycle,
  } = useTradingDashboard();

  return (
    <div className="h-full overflow-auto bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
              Trading Dashboard
            </h1>
            <p className="text-slate-400 mt-1">
              Real-time performance • Strategy signals • Automated trading
            </p>
          </div>
          <div className="flex items-center gap-4">
            {lastRefresh && (
              <span className="text-xs text-slate-500">
                Updated: {lastRefresh.toLocaleTimeString()}
                <span className="ml-1 text-slate-600">(auto-refreshes every 30s)</span>
              </span>
            )}
            <Button 
              onClick={fetchData} 
              disabled={loading}
              variant="outline"
              className="border-slate-600"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {error && (
          <Card className="border-red-500/50 bg-red-500/10">
            <CardContent className="pt-6">
              <div className="text-red-400">{error}</div>
            </CardContent>
          </Card>
        )}

        {/* Top Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Equity */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2 text-slate-400">
                <DollarSign className="w-4 h-4" />
                Total Equity
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading && !performance ? (
                <Skeleton className="h-8 w-32" />
              ) : (
                <>
                  <div className="text-3xl font-bold text-white">
                    {formatCurrency(performance?.equity || 0)}
                  </div>
                  <div className={`text-sm mt-1 ${(performance?.day_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(performance?.day_pnl || 0)} today ({formatPercent(performance?.day_pnl_pct || 0)})
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Unrealized P&L */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2 text-slate-400">
                {(performance?.total_unrealized_pnl || 0) >= 0 ? (
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-red-400" />
                )}
                Unrealized P&L
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading && !performance ? (
                <Skeleton className="h-8 w-32" />
              ) : (
                <>
                  <div className={`text-3xl font-bold ${(performance?.total_unrealized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(performance?.total_unrealized_pnl || 0)}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    {performance?.positions_count || 0} open positions
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Win Rate */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2 text-slate-400">
                <Award className="w-4 h-4" />
                Win Rate
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading && !metrics ? (
                <Skeleton className="h-8 w-32" />
              ) : (
                <>
                  <div className="text-3xl font-bold text-cyan-400">
                    {metrics?.win_rate != null ? `${metrics.win_rate}%` : 'N/A'}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    {metrics?.winning_trades || 0}W / {metrics?.losing_trades || 0}L ({metrics?.total_trades || 0} total)
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Scheduler Status */}
          <Card className={`border ${scheduler?.is_running ? 'bg-emerald-500/10 border-emerald-500/50' : 'bg-slate-800/50 border-slate-700'}`}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2 text-slate-400">
                <Clock className="w-4 h-4" />
                Auto-Trading
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <Badge className={scheduler?.is_running ? 'bg-emerald-600' : 'bg-slate-600'}>
                  {scheduler?.is_running ? 'ACTIVE' : 'STOPPED'}
                </Badge>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={toggleScheduler}
                  className={scheduler?.is_running ? 'border-red-500 text-red-400 hover:bg-red-500/20' : 'border-emerald-500 text-emerald-400 hover:bg-emerald-500/20'}
                >
                  {scheduler?.is_running ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>
              </div>
              <div className="text-sm text-slate-400 mt-2">
                {scheduler?.scheduled_tasks.length || 0} scheduled tasks
              </div>
            </CardContent>
          </Card>
        </div>

        {/* AI Trading Control Panel */}
        <Card className="bg-gradient-to-r from-purple-900/30 via-indigo-900/30 to-blue-900/30 border-purple-500/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-3 text-white">
              <Brain className="w-6 h-6 text-purple-400" />
              AI-Powered Trading Pipeline
              {automatedStatus?.is_running && (
                <Badge className="bg-purple-600 animate-pulse">RUNNING</Badge>
              )}
            </CardTitle>
            <CardDescription className="text-slate-300">
              Strategy Engine → Mazo Validation → AI Analysts → Portfolio Manager → Alpaca Execution
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
                    {automatedStatus.message || 'Set ALPACA_API_KEY and ALPACA_SECRET_KEY in Settings to enable automated trading.'}
                  </p>
                  <a 
                    href="/settings" 
                    className="inline-flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 mt-2"
                  >
                    <Settings className="w-3 h-3" />
                    Go to Settings
                  </a>
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
                    className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50"
                  >
                    {aiLoading ? (
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Rocket className="w-4 h-4 mr-2" />
                    )}
                    Run AI Trading Cycle
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => runAiTradingCycle(true)}
                    disabled={aiLoading || automatedStatus?.is_running || automatedStatus?.success === false}
                    className="border-purple-500 text-purple-400 hover:bg-purple-500/20 disabled:opacity-50"
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    Dry Run
                  </Button>
                </div>
                <p className="text-xs text-slate-400">
                  Full cycle: Screen → Validate → Analyze → Decide → Execute
                </p>
              </div>
              
              {/* Last Run Stats */}
              <div className="grid grid-cols-5 gap-2 text-center">
                <div className="p-2 bg-slate-700/50 rounded-lg">
                  <div className="text-lg font-bold text-white">
                    {automatedStatus?.last_result?.tickers_screened || 0}
                  </div>
                  <div className="text-xs text-slate-400">Screened</div>
                </div>
                <div className="p-2 bg-slate-700/50 rounded-lg">
                  <div className="text-lg font-bold text-cyan-400">
                    {automatedStatus?.last_result?.signals_found || 0}
                  </div>
                  <div className="text-xs text-slate-400">Signals</div>
                </div>
                <div className="p-2 bg-slate-700/50 rounded-lg">
                  <div className="text-lg font-bold text-purple-400">
                    {automatedStatus?.last_result?.mazo_validated || 0}
                  </div>
                  <div className="text-xs text-slate-400">Validated</div>
                </div>
                <div className="p-2 bg-slate-700/50 rounded-lg">
                  <div className="text-lg font-bold text-yellow-400">
                    {automatedStatus?.last_result?.trades_analyzed || 0}
                  </div>
                  <div className="text-xs text-slate-400">Analyzed</div>
                </div>
                <div className="p-2 bg-slate-700/50 rounded-lg">
                  <div className="text-lg font-bold text-emerald-400">
                    {automatedStatus?.last_result?.trades_executed || 0}
                  </div>
                  <div className="text-xs text-slate-400">Executed</div>
                </div>
              </div>
            </div>
            
            {/* Recent AI Trade Results */}
            {automatedStatus?.last_result?.results && automatedStatus.last_result.results.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-600">
                <h4 className="text-sm font-medium text-slate-300 mb-2">Latest AI Decisions</h4>
                <div className="flex flex-wrap gap-2">
                  {automatedStatus.last_result.results.slice(0, 5).map((res, i) => (
                    <Badge 
                      key={i} 
                      variant="outline"
                      className={
                        res.action === 'buy' || res.action === 'cover' 
                          ? 'border-emerald-500 text-emerald-400' 
                          : res.action === 'sell' || res.action === 'short'
                          ? 'border-red-500 text-red-400'
                          : 'border-slate-500 text-slate-400'
                      }
                    >
                      {res.ticker}: {res.action.toUpperCase()}
                      {res.dry_run && ' (dry)'}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            
            {automatedStatus?.last_run && (
              <div className="text-xs text-slate-500 mt-3">
                Last run: {new Date(automatedStatus.last_run).toLocaleString()} 
                ({automatedStatus.total_runs} total runs)
              </div>
            )}
          </CardContent>
        </Card>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Positions */}
          <Card className="lg:col-span-2 bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <BarChart3 className="w-5 h-5 text-blue-400" />
                Open Positions
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading && !performance ? (
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
                <div className="space-y-3">
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
                        <span className="text-slate-400">{Math.abs(pos.qty)} shares</span>
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
                </CardTitle>
                <Button size="sm" variant="ghost" className="text-slate-400 hover:text-white">
                  <Plus className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {watchlist.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <Eye className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No items in watchlist</p>
                  <p className="text-sm mt-1">Add stocks to monitor</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {watchlist.slice(0, 5).map((item) => (
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
                      <div className="flex items-center gap-2">
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
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Scheduled Tasks & Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Scheduled Tasks */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-white">
                  <Calendar className="w-5 h-5 text-orange-400" />
                  Scheduled Tasks
                </CardTitle>
                {scheduler && !scheduler.is_running && (
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={addDefaultSchedule}
                    className="border-orange-500 text-orange-400 hover:bg-orange-500/20"
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    Add Schedule
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {!scheduler?.scheduled_tasks || scheduler.scheduled_tasks.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <Calendar className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No scheduled tasks</p>
                  <p className="text-sm mt-1">Click "Add Schedule" to set up automated trading</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {scheduler.scheduled_tasks.map((task) => (
                    <div 
                      key={task.id}
                      className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
                    >
                      <div>
                        <span className="font-medium text-white">{task.name}</span>
                        <div className="text-xs text-slate-400">
                          {task.trigger}
                        </div>
                      </div>
                      <div className="text-right text-sm">
                        <div className="text-slate-400">Next run:</div>
                        <div className="text-cyan-400">
                          {task.next_run ? new Date(task.next_run).toLocaleTimeString() : 'N/A'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

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
                      <p className="text-sm text-amber-200 font-medium">
                        No trading data yet
                      </p>
                      <p className="text-xs text-amber-300/70 mt-1">
                        {metrics.message || 'Run an AI trading cycle or wait for positions to close to see performance metrics.'}
                      </p>
                      <Button
                        onClick={() => runAiTradingCycle(true)}
                        disabled={aiLoading || automatedStatus?.is_running || automatedStatus?.success === false}
                        size="sm"
                        className="mt-3 bg-amber-600 hover:bg-amber-700 text-white"
                      >
                        <Rocket className="w-3 h-3 mr-2" />
                        Run AI Cycle (Dry Run)
                      </Button>
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
        </div>

        {/* Recent Task History */}
        {scheduler?.recent_history && scheduler.recent_history.length > 0 && (
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Zap className="w-5 h-5 text-yellow-400" />
                Recent Task Executions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 flex-wrap">
                {scheduler.recent_history.slice(0, 10).map((hist, i) => (
                  <Badge 
                    key={i}
                    variant="outline"
                    className={hist.success ? 'border-emerald-500 text-emerald-400' : 'border-red-500 text-red-400'}
                  >
                    {hist.task_type} • {new Date(hist.timestamp).toLocaleTimeString()}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
