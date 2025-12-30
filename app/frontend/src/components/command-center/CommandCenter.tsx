import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  useHydratedData, 
  dataHydrationService,
  type Position,
  type ScheduledTask,
} from '@/services/data-hydration-service';
import { 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  DollarSign,
  Activity,
  Clock,
  Award,
  History,
  Users,
  Zap,
  CheckCircle,
  XCircle,
  BarChart3
} from 'lucide-react';

function formatCurrency(value: number): string {
  const sign = value >= 0 ? '' : '-';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function CommandCenter() {
  // Use hydrated data - already cached, no loading needed
  const { 
    performance, 
    scheduler, 
    trades, 
    agents, 
    metrics,
    isRefreshing,
    refreshTrades,
    refreshAgents,
    recentWorkflows,
  } = useHydratedData();
  
  const [selectedTrade, setSelectedTrade] = useState<any>(null);
  const [isManualRefresh, setIsManualRefresh] = useState(false);

  const handleRefresh = async () => {
    setIsManualRefresh(true);
    await dataHydrationService.backgroundRefresh();
    await refreshTrades();
    await refreshAgents();
    setIsManualRefresh(false);
  };

  // Data is always available (from cache) - no loading states needed

  return (
    <div className="h-full overflow-auto bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-amber-400 via-orange-400 to-red-400 bg-clip-text text-transparent">
              Command Center
            </h1>
            <p className="text-slate-400 mt-1">
              Unified view • Trade history • Agent performance • Real-time status
            </p>
          </div>
          <Button 
            onClick={handleRefresh}
            disabled={isManualRefresh || isRefreshing}
            variant="outline"
            className="border-slate-600"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isManualRefresh || isRefreshing ? 'animate-spin' : ''}`} />
            Refresh All
          </Button>
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

          <Card className={`border ${scheduler?.is_running ? 'bg-emerald-500/10 border-emerald-500/50' : 'bg-slate-800/50 border-slate-700'}`}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                <Clock className="w-3 h-3" />
                Auto-Trading
              </div>
              <Badge className={scheduler?.is_running ? 'bg-emerald-600' : 'bg-slate-600'}>
                {scheduler?.is_running ? 'ACTIVE' : 'STOPPED'}
              </Badge>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Tabs */}
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList className="bg-slate-800 border border-slate-700">
            <TabsTrigger value="overview" className="data-[state=active]:bg-slate-700">
              <Activity className="w-4 h-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="trades" className="data-[state=active]:bg-slate-700">
              <History className="w-4 h-4 mr-2" />
              Trade History
            </TabsTrigger>
            <TabsTrigger value="agents" className="data-[state=active]:bg-slate-700">
              <Users className="w-4 h-4 mr-2" />
              Agent Leaderboard
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Current Positions */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <BarChart3 className="w-5 h-5 text-blue-400" />
                    Open Positions
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {!performance?.positions || performance.positions.length === 0 ? (
                    <div className="text-center py-6 text-slate-400">
                      <BarChart3 className="w-10 h-10 mx-auto mb-2 opacity-50" />
                      <p>No open positions</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {performance.positions.map((pos: Position) => (
                        <div 
                          key={pos.ticker}
                          className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{pos.ticker}</span>
                            <Badge variant="outline" className={pos.side === 'long' ? 'border-emerald-500 text-emerald-400' : 'border-red-500 text-red-400'}>
                              {pos.side.toUpperCase()}
                            </Badge>
                            <span className="text-slate-400 text-sm">{Math.abs(pos.qty)} shares</span>
                          </div>
                          <div className={`font-mono ${pos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {formatCurrency(pos.unrealized_pnl)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Scheduled Tasks */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Clock className="w-5 h-5 text-orange-400" />
                    Next Scheduled Actions
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {!scheduler?.scheduled_tasks || scheduler.scheduled_tasks.length === 0 ? (
                    <div className="text-center py-6 text-slate-400">
                      <Clock className="w-10 h-10 mx-auto mb-2 opacity-50" />
                      <p>No scheduled tasks</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {scheduler.scheduled_tasks.slice(0, 5).map((task: ScheduledTask) => (
                        <div 
                          key={task.id}
                          className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
                        >
                          <span className="text-white">{task.name}</span>
                          <span className="text-cyan-400 text-sm font-mono">
                            {task.next_run ? new Date(task.next_run).toLocaleTimeString() : 'N/A'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Recent Trade Decisions - Shows both executed trades AND workflow decisions */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Zap className="w-5 h-5 text-yellow-400" />
                  Recent Trade Decisions
                </CardTitle>
                <CardDescription>
                  Latest AI decisions from Unified Workflow
                </CardDescription>
              </CardHeader>
              <CardContent>
                {/* Show recent workflows first (includes HOLD decisions) */}
                {recentWorkflows.length > 0 && (
                  <div className="space-y-3 mb-4">
                    {recentWorkflows.slice(0, 3).map((workflow) => (
                      <div 
                        key={workflow.id}
                        className="p-4 bg-slate-700/30 rounded-lg border border-slate-600/50"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{workflow.tickers.join(', ')}</span>
                            {workflow.pmDecision && (
                              <Badge className={
                                workflow.pmDecision.action === 'buy' || workflow.pmDecision.action === 'cover'
                                  ? 'bg-green-500/20 text-green-400 border-green-500/50'
                                  : workflow.pmDecision.action === 'sell' || workflow.pmDecision.action === 'short'
                                  ? 'bg-red-500/20 text-red-400 border-red-500/50'
                                  : 'bg-slate-500/20 text-slate-400 border-slate-500/50'
                              }>
                                {workflow.pmDecision.action.toUpperCase()}
                              </Badge>
                            )}
                            {workflow.tradeExecuted && (
                              <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/50">
                                <CheckCircle className="w-3 h-3 mr-1" />
                                Executed
                              </Badge>
                            )}
                          </div>
                          <span className="text-xs text-slate-500">
                            {workflow.timestamp.toLocaleTimeString()}
                          </span>
                        </div>
                        {workflow.pmDecision?.reasoning && (
                          <p className="text-sm text-slate-400 line-clamp-2">
                            {workflow.pmDecision.reasoning}
                          </p>
                        )}
                        {workflow.agentSignals.length > 0 && (
                          <div className="flex gap-1 mt-2 flex-wrap">
                            {workflow.agentSignals.slice(0, 6).map((sig, i) => (
                              <span 
                                key={i}
                                className={`text-xs px-1.5 py-0.5 rounded ${
                                  sig.signal === 'BULLISH' ? 'bg-green-500/20 text-green-400' :
                                  sig.signal === 'BEARISH' ? 'bg-red-500/20 text-red-400' :
                                  'bg-slate-500/20 text-slate-400'
                                }`}
                              >
                                {sig.agent.split(' ')[0]}: {sig.signal}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                
                {/* Also show executed trades from history */}
                {trades.length === 0 && recentWorkflows.length === 0 ? (
                  <div className="text-center py-8 text-slate-400">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-slate-700/50 flex items-center justify-center">
                      <Zap className="w-8 h-8 opacity-50" />
                    </div>
                    <p className="text-lg font-medium text-slate-300">No AI decisions yet</p>
                    <p className="text-sm mt-2 max-w-md mx-auto">
                      When you run an analysis from the <span className="text-cyan-400">Unified Workflow</span> tab, 
                      the AI decisions will appear here with full reasoning and agent signals.
                    </p>
                    <div className="mt-4 p-3 bg-slate-700/30 rounded-lg inline-block">
                      <p className="text-xs text-slate-500">
                        💡 Tip: Try running a workflow with "Dry Run" enabled first to test safely
                      </p>
                    </div>
                  </div>
                ) : trades.length > 0 && (
                  <div className="space-y-3">
                    {trades.slice(0, 5).map((trade) => (
                      <div 
                        key={trade.id}
                        className="p-4 bg-slate-700/30 rounded-lg border border-slate-600/50 hover:border-slate-500 transition-colors cursor-pointer"
                        onClick={() => setSelectedTrade(trade)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white text-lg">{trade.ticker}</span>
                            <Badge className={
                              trade.action === 'buy' || trade.action === 'cover' 
                                ? 'bg-emerald-600' 
                                : trade.action === 'sell' || trade.action === 'short'
                                ? 'bg-red-600'
                                : 'bg-slate-600'
                            }>
                              {trade.action.toUpperCase()}
                            </Badge>
                            <span className="text-slate-400">{trade.quantity} shares</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {trade.status === 'closed' && trade.realized_pnl != null && (
                              <span className={`font-mono ${trade.realized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                {formatCurrency(trade.realized_pnl)}
                              </span>
                            )}
                            <Badge variant="outline" className={
                              trade.status === 'closed' ? 'border-slate-500 text-slate-400' :
                              trade.status === 'pending' ? 'border-yellow-500 text-yellow-400' :
                              'border-blue-500 text-blue-400'
                            }>
                              {trade.status}
                            </Badge>
                          </div>
                        </div>
                        
                        {trade.context && (
                          <div className="flex items-center gap-4 text-sm">
                            <span className="text-slate-500">
                              {trade.context.trigger_source}
                            </span>
                            <span className="text-slate-500">|</span>
                            <span className={
                              trade.context.consensus_direction === 'bullish' ? 'text-emerald-400' :
                              trade.context.consensus_direction === 'bearish' ? 'text-red-400' :
                              'text-slate-400'
                            }>
                              {trade.context.bullish_count}B / {trade.context.bearish_count}S / {trade.context.neutral_count}N
                            </span>
                            {trade.context.mazo_sentiment && (
                              <>
                                <span className="text-slate-500">|</span>
                                <span className="text-purple-400">
                                  Mazo: {trade.context.mazo_sentiment}
                                </span>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Trade History Tab */}
          <TabsContent value="trades" className="space-y-4">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <History className="w-5 h-5 text-cyan-400" />
                  Complete Trade History
                </CardTitle>
                <CardDescription>
                  All trades with full decision context and agent signals
                </CardDescription>
              </CardHeader>
              <CardContent>
                {trades.length === 0 ? (
                  <div className="text-center py-12 text-slate-400">
                    <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-slate-700/50 flex items-center justify-center">
                      <History className="w-10 h-10 opacity-50" />
                    </div>
                    <p className="text-xl font-medium text-slate-300">Trade History Empty</p>
                    <p className="text-sm mt-3 max-w-lg mx-auto">
                      Your trading history will appear here after you execute trades. Each trade includes:
                    </p>
                    <div className="grid grid-cols-3 gap-3 mt-4 max-w-md mx-auto text-xs">
                      <div className="p-2 bg-slate-700/30 rounded">
                        <span className="text-cyan-400">Entry/Exit</span>
                        <p className="text-slate-500 mt-1">Price & timing</p>
                      </div>
                      <div className="p-2 bg-slate-700/30 rounded">
                        <span className="text-purple-400">Agent Votes</span>
                        <p className="text-slate-500 mt-1">18 AI signals</p>
                      </div>
                      <div className="p-2 bg-slate-700/30 rounded">
                        <span className="text-emerald-400">P&L</span>
                        <p className="text-slate-500 mt-1">Real returns</p>
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 mt-4">
                      Enable "Execute Trades" in Unified Workflow to start recording trades
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-700">
                          <th className="text-left py-3 px-2 text-slate-400 font-medium">Time</th>
                          <th className="text-left py-3 px-2 text-slate-400 font-medium">Ticker</th>
                          <th className="text-left py-3 px-2 text-slate-400 font-medium">Action</th>
                          <th className="text-right py-3 px-2 text-slate-400 font-medium">Qty</th>
                          <th className="text-right py-3 px-2 text-slate-400 font-medium">Entry</th>
                          <th className="text-right py-3 px-2 text-slate-400 font-medium">Exit</th>
                          <th className="text-right py-3 px-2 text-slate-400 font-medium">P&L</th>
                          <th className="text-center py-3 px-2 text-slate-400 font-medium">Status</th>
                          <th className="text-center py-3 px-2 text-slate-400 font-medium">Agents</th>
                        </tr>
                      </thead>
                      <tbody>
                        {trades.map((trade) => (
                          <tr 
                            key={trade.id} 
                            className="border-b border-slate-700/50 hover:bg-slate-700/30 cursor-pointer"
                            onClick={() => setSelectedTrade(trade)}
                          >
                            <td className="py-3 px-2 text-slate-300 text-sm">
                              {trade.entry_time ? new Date(trade.entry_time).toLocaleDateString() : 'N/A'}
                            </td>
                            <td className="py-3 px-2 font-bold text-white">{trade.ticker}</td>
                            <td className="py-3 px-2">
                              <Badge className={
                                trade.action === 'buy' || trade.action === 'cover' 
                                  ? 'bg-emerald-600' 
                                  : trade.action === 'sell' || trade.action === 'short'
                                  ? 'bg-red-600'
                                  : 'bg-slate-600'
                              }>
                                {trade.action}
                              </Badge>
                            </td>
                            <td className="py-3 px-2 text-right text-white font-mono">{trade.quantity}</td>
                            <td className="py-3 px-2 text-right text-slate-300 font-mono">
                              {trade.entry_price ? `$${trade.entry_price.toFixed(2)}` : 'N/A'}
                            </td>
                            <td className="py-3 px-2 text-right text-slate-300 font-mono">
                              {trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : '-'}
                            </td>
                            <td className={`py-3 px-2 text-right font-mono ${
                              (trade.realized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                            }`}>
                              {trade.realized_pnl != null ? formatCurrency(trade.realized_pnl) : '-'}
                            </td>
                            <td className="py-3 px-2 text-center">
                              <Badge variant="outline" className={
                                trade.status === 'closed' ? 'border-slate-500 text-slate-400' :
                                trade.status === 'pending' ? 'border-yellow-500 text-yellow-400' :
                                'border-blue-500 text-blue-400'
                              }>
                                {trade.status}
                              </Badge>
                            </td>
                            <td className="py-3 px-2 text-center">
                              {trade.context && (
                                <span className="text-sm text-slate-400">
                                  {trade.context.bullish_count + trade.context.bearish_count + trade.context.neutral_count} agents
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Agent Leaderboard Tab */}
          <TabsContent value="agents" className="space-y-4">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Users className="w-5 h-5 text-purple-400" />
                  Agent Performance Leaderboard
                </CardTitle>
                <CardDescription>
                  Track which AI agents give the most accurate signals
                </CardDescription>
              </CardHeader>
              <CardContent>
                {agents.length === 0 ? (
                  <div className="text-center py-12 text-slate-400">
                    <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-slate-700/50 flex items-center justify-center">
                      <Users className="w-10 h-10 opacity-50" />
                    </div>
                    <p className="text-xl font-medium text-slate-300">Agent Leaderboard Coming Soon</p>
                    <p className="text-sm mt-3 max-w-lg mx-auto">
                      The system will track how each of the 18 AI agents performs over time:
                    </p>
                    <div className="flex flex-wrap justify-center gap-2 mt-4 max-w-lg mx-auto">
                      {['Warren Buffett', 'Ben Graham', 'Cathie Wood', 'Peter Lynch', 'Charlie Munger', 'Bill Ackman'].map((name) => (
                        <Badge key={name} variant="outline" className="border-slate-600 text-slate-400">
                          {name}
                        </Badge>
                      ))}
                      <Badge variant="outline" className="border-slate-600 text-slate-500">
                        +12 more agents
                      </Badge>
                    </div>
                    <div className="mt-6 p-4 bg-slate-700/30 rounded-lg max-w-sm mx-auto text-left">
                      <p className="text-xs text-slate-400 mb-2">Tracking includes:</p>
                      <ul className="text-xs text-slate-500 space-y-1">
                        <li>• Accuracy rate (correct predictions)</li>
                        <li>• Average return when signal was followed</li>
                        <li>• Best and worst calls</li>
                      </ul>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {agents.map((agent, index) => (
                      <div 
                        key={agent.name}
                        className="p-4 bg-slate-700/30 rounded-lg border border-slate-600/50"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                              index === 0 ? 'bg-yellow-500 text-yellow-900' :
                              index === 1 ? 'bg-slate-300 text-slate-800' :
                              index === 2 ? 'bg-orange-600 text-orange-100' :
                              'bg-slate-600 text-slate-200'
                            }`}>
                              {index + 1}
                            </div>
                            <div>
                              <span className="font-semibold text-white">{agent.name}</span>
                              {agent.type && (
                                <span className="text-slate-400 text-sm ml-2">({agent.type})</span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="text-right">
                              <div className="text-sm text-slate-400">Accuracy</div>
                              <div className={`text-lg font-bold ${
                                (agent.accuracy_rate || 0) >= 60 ? 'text-emerald-400' :
                                (agent.accuracy_rate || 0) >= 40 ? 'text-yellow-400' :
                                'text-red-400'
                              }`}>
                                {agent.accuracy_rate != null ? `${agent.accuracy_rate}%` : 'N/A'}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-sm text-slate-400">Signals</div>
                              <div className="text-lg font-bold text-cyan-400">
                                {agent.total_signals}
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-6 text-sm mt-2">
                          <span className="text-slate-400">
                            <CheckCircle className="w-3 h-3 inline mr-1 text-emerald-400" />
                            {agent.correct_predictions} correct
                          </span>
                          <span className="text-slate-400">
                            <XCircle className="w-3 h-3 inline mr-1 text-red-400" />
                            {agent.incorrect_predictions} incorrect
                          </span>
                          {agent.avg_return_when_followed != null && (
                            <span className={agent.avg_return_when_followed >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                              Avg return: {formatPercent(agent.avg_return_when_followed)}
                            </span>
                          )}
                          {agent.best_call && (
                            <span className="text-emerald-400">
                              Best: {agent.best_call.ticker} ({formatPercent(agent.best_call.return)})
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Trade Detail Modal */}
        {selectedTrade && (
          <div 
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setSelectedTrade(null)}
          >
            <div 
              className="bg-slate-800 border border-slate-600 rounded-lg max-w-2xl w-full max-h-[80vh] overflow-auto m-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="p-6 border-b border-slate-700">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold text-white">
                    Trade Details: {selectedTrade.ticker}
                  </h2>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={() => setSelectedTrade(null)}
                  >
                    ✕
                  </Button>
                </div>
              </div>
              
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-slate-400">Action</div>
                    <Badge className={
                      selectedTrade.action === 'buy' || selectedTrade.action === 'cover' 
                        ? 'bg-emerald-600' 
                        : 'bg-red-600'
                    }>
                      {selectedTrade.action.toUpperCase()} {selectedTrade.quantity} shares
                    </Badge>
                  </div>
                  <div>
                    <div className="text-sm text-slate-400">Status</div>
                    <span className="text-white">{selectedTrade.status}</span>
                  </div>
                  <div>
                    <div className="text-sm text-slate-400">Entry Price</div>
                    <span className="text-white font-mono">
                      {selectedTrade.entry_price ? `$${selectedTrade.entry_price.toFixed(2)}` : 'N/A'}
                    </span>
                  </div>
                  <div>
                    <div className="text-sm text-slate-400">Exit Price</div>
                    <span className="text-white font-mono">
                      {selectedTrade.exit_price ? `$${selectedTrade.exit_price.toFixed(2)}` : 'N/A'}
                    </span>
                  </div>
                  {selectedTrade.realized_pnl != null && (
                    <div>
                      <div className="text-sm text-slate-400">Realized P&L</div>
                      <span className={`font-mono ${selectedTrade.realized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {formatCurrency(selectedTrade.realized_pnl)} ({formatPercent(selectedTrade.return_pct || 0)})
                      </span>
                    </div>
                  )}
                </div>
                
                {selectedTrade.context && (
                  <>
                    <div className="border-t border-slate-700 pt-4">
                      <h3 className="font-semibold text-white mb-2">Decision Context</h3>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <span className="text-slate-400">Trigger:</span>{' '}
                          <span className="text-white">{selectedTrade.context.trigger_source}</span>
                        </div>
                        <div>
                          <span className="text-slate-400">Mode:</span>{' '}
                          <span className="text-white">{selectedTrade.context.workflow_mode || 'N/A'}</span>
                        </div>
                        <div>
                          <span className="text-slate-400">Consensus:</span>{' '}
                          <span className={
                            selectedTrade.context.consensus_direction === 'bullish' ? 'text-emerald-400' :
                            selectedTrade.context.consensus_direction === 'bearish' ? 'text-red-400' :
                            'text-slate-300'
                          }>
                            {selectedTrade.context.consensus_direction} ({selectedTrade.context.consensus_confidence?.toFixed(0)}%)
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400">Votes:</span>{' '}
                          <span className="text-emerald-400">{selectedTrade.context.bullish_count}B</span>
                          {' / '}
                          <span className="text-red-400">{selectedTrade.context.bearish_count}S</span>
                          {' / '}
                          <span className="text-slate-400">{selectedTrade.context.neutral_count}N</span>
                        </div>
                        {selectedTrade.context.mazo_sentiment && (
                          <div className="col-span-2">
                            <span className="text-slate-400">Mazo Sentiment:</span>{' '}
                            <span className="text-purple-400">{selectedTrade.context.mazo_sentiment}</span>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {selectedTrade.context.pm_reasoning && (
                      <div className="border-t border-slate-700 pt-4">
                        <h3 className="font-semibold text-white mb-2">PM Reasoning</h3>
                        <p className="text-slate-300 text-sm whitespace-pre-wrap">
                          {selectedTrade.context.pm_reasoning}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
