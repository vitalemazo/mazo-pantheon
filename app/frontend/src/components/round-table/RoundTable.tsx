'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Progress } from '@/components/ui/progress';
import {
  Search,
  Brain,
  Users,
  Target,
  Zap,
  TrendingUp,
  TrendingDown,
  Minus,
  CheckCircle,
  XCircle,
  Clock,
  AlertCircle,
  ChevronRight,
  RefreshCw,
  Activity,
  BarChart3,
  FileText,
  Shield,
  DollarSign,
  Loader2,
  HelpCircle,
  RotateCcw,
  Eye,
} from 'lucide-react';
import { API_BASE_URL } from '@/lib/api-config';
import { InfoTooltip } from '@/components/ui/info-tooltip';

const fetcher = (url: string) => fetch(url).then((res) => res.json());

// Types
interface GuardRailCheck {
  name: string;
  status: string;
  value: any;
  threshold?: any;
  message?: string;
}

interface AgentSignal {
  agent_id: string;
  agent_type: string | null;
  signal: string;
  confidence: number | null;
  reasoning: string | null;
  accuracy_rate: number | null;
}

interface AgentAccuracyUpdate {
  agent_id: string;
  signal_was_correct: boolean | null;
}

interface RoundTableData {
  workflow_id: string | null;
  workflow_type: string | null;
  ticker: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_duration_ms: number | null;
  status: string;
  // Stage 1: Universe & Risk
  universe_risk: {
    universe_size: number;
    universe_tickers: string[];
    watchlist_count: number;
    watchlist_tickers: string[];
    portfolio_value: number | null;
    buying_power: number | null;
    cash_available: number | null;
    day_trades_remaining: number | null;
    pdt_status: string | null;
    auto_trading_enabled: boolean;
    market_hours: boolean;
    guard_rails: GuardRailCheck[];
    concentration_check: string | null;
    cooldown_tickers: string[];
    blocked_tickers: string[];
    status: string;
  };
  // Stage 2: Strategy
  strategy: {
    tickers_scanned: number;
    signals_found: number;
    signals: any[];
    duration_ms: number | null;
  };
  // Stage 3: Mazo
  mazo: {
    ticker: string | null;
    summary: string | null;
    sentiment: string | null;
    sentiment_confidence: string | null;
    key_points: string[];
    sources_count: number;
    success: boolean;
    duration_ms: number | null;
  };
  // Stage 4: Agents
  agents: {
    agents: AgentSignal[];
    bullish_count: number;
    bearish_count: number;
    neutral_count: number;
    consensus: string | null;
    agreement_pct: number | null;
    total_duration_ms: number | null;
  };
  portfolio_manager: {
    ticker: string | null;
    action: string | null;
    quantity: number | null;
    stop_loss_pct: number | null;
    take_profit_pct: number | null;
    reasoning: string | null;
    confidence: number | null;
    action_matches_consensus: boolean | null;
    override_reason: string | null;
    duration_ms: number | null;
  };
  execution: {
    order_id: string | null;
    side: string | null;
    status: string | null;
    filled_qty: number | null;
    filled_avg_price: number | null;
    error: string | null;
  };
  // Stage 7: Post-Trade
  post_trade: {
    trade_id: number | null;
    status: string | null;
    realized_pnl: number | null;
    return_pct: number | null;
  };
  // Stage 8: Feedback Loop
  feedback_loop: {
    trade_recorded: boolean;
    trade_id: number | null;
    order_id: string | null;
    realized_pnl: number | null;
    return_pct: number | null;
    was_profitable: boolean | null;
    agents_updated: number;
    accuracy_updates: AgentAccuracyUpdate[];
    cooldown_set: boolean;
    cooldown_until: string | null;
    position_added: boolean;
    session_pnl: number | null;
    session_trades: number;
    session_win_rate: number | null;
    status: string;
  };
  consensus: {
    total_agents: number;
    bullish_pct: number;
    bearish_pct: number;
    neutral_pct: number;
    agreement_pct: number;
    conviction_met: boolean;
    recommendation: string | null;
  };
  errors: string[];
}

// Pipeline Stage Component
function PipelineStage({
  icon: Icon,
  title,
  status,
  duration,
  children,
  expanded = false,
}: {
  icon: React.ElementType;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  duration?: number | null;
  children: React.ReactNode;
  expanded?: boolean;
}) {
  const statusColors = {
    pending: 'bg-slate-600/50 text-slate-400',
    running: 'bg-cyan-500/20 text-cyan-400 animate-pulse',
    completed: 'bg-emerald-500/20 text-emerald-400',
    failed: 'bg-red-500/20 text-red-400',
    skipped: 'bg-amber-500/20 text-amber-400',
  };

  const statusIcons = {
    pending: <Clock className="h-4 w-4" />,
    running: <Loader2 className="h-4 w-4 animate-spin" />,
    completed: <CheckCircle className="h-4 w-4" />,
    failed: <XCircle className="h-4 w-4" />,
    skipped: <AlertCircle className="h-4 w-4" />,
  };

  return (
    <AccordionItem value={title} className="border-slate-700">
      <AccordionTrigger className="hover:no-underline">
        <div className="flex items-center gap-3 w-full pr-4">
          <div className={`p-2 rounded-lg ${statusColors[status]}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="flex-1 text-left">
            <div className="font-medium">{title}</div>
            {duration != null && duration > 0 && (
              <div className="text-xs text-slate-500">{duration}ms</div>
            )}
          </div>
          <div className={`flex items-center gap-1 text-sm ${statusColors[status].split(' ')[1]}`}>
            {statusIcons[status]}
            <span className="capitalize">{status}</span>
          </div>
        </div>
      </AccordionTrigger>
      <AccordionContent className="pb-4">
        {children}
      </AccordionContent>
    </AccordionItem>
  );
}

// Consensus Meter Component
function ConsensusMeter({ consensus }: { consensus: RoundTableData['consensus'] }) {
  const { bullish_pct, bearish_pct, neutral_pct, agreement_pct, conviction_met, recommendation } = consensus;

  return (
    <Card className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <Activity className="h-5 w-5 text-cyan-400" />
          AI Consensus Meter
          <InfoTooltip content="Shows the agreement level among all 18 AI agents. Conviction threshold is 65%." />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Sentiment Bars */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              <span className="text-sm w-16">Bullish</span>
              <div className="flex-1 h-3 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all duration-500"
                  style={{ width: `${bullish_pct}%` }}
                />
              </div>
              <span className="text-sm w-12 text-right">{bullish_pct.toFixed(0)}%</span>
            </div>
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-400" />
              <span className="text-sm w-16">Bearish</span>
              <div className="flex-1 h-3 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-red-500 transition-all duration-500"
                  style={{ width: `${bearish_pct}%` }}
                />
              </div>
              <span className="text-sm w-12 text-right">{bearish_pct.toFixed(0)}%</span>
            </div>
            <div className="flex items-center gap-2">
              <Minus className="h-4 w-4 text-slate-400" />
              <span className="text-sm w-16">Neutral</span>
              <div className="flex-1 h-3 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-slate-500 transition-all duration-500"
                  style={{ width: `${neutral_pct}%` }}
                />
              </div>
              <span className="text-sm w-12 text-right">{neutral_pct.toFixed(0)}%</span>
            </div>
          </div>

          {/* Agreement & Conviction */}
          <div className="flex items-center justify-between pt-2 border-t border-slate-700">
            <div>
              <div className="text-xs text-slate-500">Agreement Level</div>
              <div className="text-xl font-bold">{agreement_pct.toFixed(0)}%</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-slate-500">Conviction</div>
              <Badge
                variant={conviction_met ? 'default' : 'secondary'}
                className={conviction_met ? 'bg-emerald-500' : 'bg-amber-500'}
              >
                {conviction_met ? '✓ Met (≥65%)' : '✗ Not Met (<65%)'}
              </Badge>
            </div>
          </div>

          {/* Recommendation */}
          {recommendation && (
            <div className="text-center pt-2">
              <Badge
                variant="outline"
                className={`text-lg px-4 py-1 ${
                  recommendation === 'bullish'
                    ? 'border-emerald-500 text-emerald-400'
                    : recommendation === 'bearish'
                    ? 'border-red-500 text-red-400'
                    : 'border-slate-500 text-slate-400'
                }`}
              >
                Recommendation: {recommendation.toUpperCase()}
              </Badge>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// Agent Table Component
function AgentTable({ agents }: { agents: AgentSignal[] }) {
  const getSignalColor = (signal: string) => {
    switch (signal.toLowerCase()) {
      case 'bullish':
        return 'text-emerald-400';
      case 'bearish':
        return 'text-red-400';
      default:
        return 'text-slate-400';
    }
  };

  const getSignalIcon = (signal: string) => {
    switch (signal.toLowerCase()) {
      case 'bullish':
        return <TrendingUp className="h-4 w-4" />;
      case 'bearish':
        return <TrendingDown className="h-4 w-4" />;
      default:
        return <Minus className="h-4 w-4" />;
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 px-2">Agent</th>
            <th className="text-left py-2 px-2">Type</th>
            <th className="text-center py-2 px-2">Signal</th>
            <th className="text-center py-2 px-2">Confidence</th>
            <th className="text-center py-2 px-2">Accuracy</th>
            <th className="text-left py-2 px-2">Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr
              key={agent.agent_id}
              className="border-b border-slate-800 hover:bg-slate-800/50"
            >
              <td className="py-2 px-2 font-medium">
                {agent.agent_id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
              </td>
              <td className="py-2 px-2 text-slate-400 capitalize">
                {agent.agent_type || 'analyst'}
              </td>
              <td className={`py-2 px-2 text-center ${getSignalColor(agent.signal)}`}>
                <div className="flex items-center justify-center gap-1">
                  {getSignalIcon(agent.signal)}
                  <span className="capitalize">{agent.signal}</span>
                </div>
              </td>
              <td className="py-2 px-2 text-center">
                {agent.confidence !== null ? (
                  <span className={agent.confidence >= 70 ? 'text-emerald-400' : 'text-slate-400'}>
                    {agent.confidence.toFixed(0)}%
                  </span>
                ) : (
                  <span className="text-slate-600">—</span>
                )}
              </td>
              <td className="py-2 px-2 text-center">
                {agent.accuracy_rate !== null ? (
                  <span className={agent.accuracy_rate >= 0.5 ? 'text-cyan-400' : 'text-amber-400'}>
                    {(agent.accuracy_rate * 100).toFixed(0)}%
                  </span>
                ) : (
                  <span className="text-slate-600">N/A</span>
                )}
              </td>
              <td className="py-2 px-2 text-slate-400 max-w-xs truncate">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="cursor-help">
                      {agent.reasoning?.substring(0, 60)}
                      {agent.reasoning && agent.reasoning.length > 60 ? '...' : ''}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="left" className="max-w-md">
                    <p>{agent.reasoning || 'No reasoning provided'}</p>
                  </TooltipContent>
                </Tooltip>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Main Component
export function RoundTable() {
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);

  // Fetch round table data
  const { data, error, isLoading, mutate } = useSWR<RoundTableData>(
    selectedWorkflow
      ? `${API_BASE_URL}/transparency/round-table?workflow_id=${selectedWorkflow}`
      : `${API_BASE_URL}/transparency/round-table`,
    fetcher,
    { refreshInterval: 10000 }
  );

  // Fetch workflow history for dropdown
  const { data: historyData } = useSWR(
    `${API_BASE_URL}/transparency/round-table/history?limit=20`,
    fetcher,
    { refreshInterval: 30000 }
  );

  const getStageStatus = (hasData: boolean, workflowStatus: string): 'pending' | 'running' | 'completed' | 'failed' | 'skipped' => {
    if (workflowStatus === 'failed') return 'failed';
    if (workflowStatus === 'running') return hasData ? 'completed' : 'running';
    return hasData ? 'completed' : 'skipped';
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="h-12 w-12 animate-spin mx-auto text-cyan-400" />
          <p className="text-slate-400">Loading Round Table data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <Card className="bg-red-900/20 border-red-700 max-w-md">
          <CardContent className="pt-6 text-center">
            <XCircle className="h-12 w-12 mx-auto text-red-400 mb-4" />
            <p className="text-red-400">Failed to load Round Table data</p>
            <Button variant="outline" className="mt-4" onClick={() => mutate()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const roundTable = data;

  if (!roundTable || roundTable.status === 'no_data') {
    return (
      <div className="h-full flex items-center justify-center">
        <Card className="bg-slate-800/50 border-slate-700 max-w-md">
          <CardContent className="pt-6 text-center">
            <FileText className="h-12 w-12 mx-auto text-slate-500 mb-4" />
            <p className="text-slate-400 mb-2">No workflow data available</p>
            <p className="text-sm text-slate-500">
              Run an AI Trading Cycle to see the Round Table view
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="h-full overflow-auto p-4 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Users className="h-7 w-7 text-cyan-400" />
              Round Table
            </h1>
            <p className="text-slate-400 text-sm">
              Full transparency into the AI trading decision pipeline
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Workflow Selector */}
            {historyData?.workflows?.length > 0 && (
              <Select
                value={selectedWorkflow || 'latest'}
                onValueChange={(v) => setSelectedWorkflow(v === 'latest' ? null : v)}
              >
                <SelectTrigger className="w-64 bg-slate-800 border-slate-700">
                  <SelectValue placeholder="Select workflow" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="latest">Latest Workflow</SelectItem>
                  {historyData.workflows.map((wf: any) => (
                    <SelectItem key={wf.workflow_id} value={wf.workflow_id}>
                      {wf.ticker || 'Multi'} - {new Date(wf.started_at).toLocaleString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Button variant="outline" size="sm" onClick={() => mutate()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Workflow Info Banner */}
        <Card className="bg-slate-800/50 border-slate-700">
          <CardContent className="py-3">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-4">
                <Badge
                  variant={
                    roundTable.status === 'completed'
                      ? 'default'
                      : roundTable.status === 'failed'
                      ? 'destructive'
                      : 'secondary'
                  }
                  className={
                    roundTable.status === 'completed'
                      ? 'bg-emerald-500'
                      : roundTable.status === 'running'
                      ? 'bg-cyan-500 animate-pulse'
                      : ''
                  }
                >
                  {roundTable.status.toUpperCase()}
                </Badge>
                {roundTable.ticker && (
                  <span className="font-mono text-lg">{roundTable.ticker}</span>
                )}
                {roundTable.started_at && (
                  <span className="text-slate-500">
                    {new Date(roundTable.started_at).toLocaleString()}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-slate-400">
                {roundTable.total_duration_ms && (
                  <span>Duration: {(roundTable.total_duration_ms / 1000).toFixed(1)}s</span>
                )}
                {roundTable.workflow_id && (
                  <span className="font-mono text-xs">
                    ID: {roundTable.workflow_id.substring(0, 8)}...
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left Column - Consensus Meter */}
          <div className="lg:col-span-1">
            <ConsensusMeter consensus={roundTable.consensus} />
          </div>

          {/* Right Column - Pipeline Stages */}
          <div className="lg:col-span-2">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-cyan-400" />
                  Decision Pipeline
                </CardTitle>
                <CardDescription>
                  Click each stage to see details
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Accordion type="multiple" defaultValue={['Universe & Risk Prep', 'Strategy Engine', 'AI Agents', 'Portfolio Manager']}>
                  {/* Stage 1: Universe & Risk Prep */}
                  <PipelineStage
                    icon={Shield}
                    title="Universe & Risk Prep"
                    status={roundTable.universe_risk?.status === 'pass' ? 'completed' : roundTable.universe_risk?.status === 'fail' ? 'failed' : 'pending'}
                  >
                    <div className="pl-12 space-y-3">
                      {/* Guard Rails */}
                      <div className="space-y-2">
                        <div className="text-xs text-slate-500 font-medium">Guard Rails</div>
                        <div className="grid grid-cols-2 gap-2">
                          {roundTable.universe_risk?.guard_rails?.map((rail, idx) => (
                            <div key={idx} className="flex items-center gap-2 bg-slate-900/50 p-2 rounded-lg">
                              {rail.status === 'pass' ? (
                                <CheckCircle className="h-4 w-4 text-emerald-400" />
                              ) : rail.status === 'fail' ? (
                                <XCircle className="h-4 w-4 text-red-400" />
                              ) : (
                                <AlertCircle className="h-4 w-4 text-amber-400" />
                              )}
                              <div className="flex-1">
                                <div className="text-xs font-medium">{rail.name}</div>
                                <div className="text-xs text-slate-500">{rail.message}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      {/* Account & Risk */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="bg-slate-900/50 p-3 rounded-lg">
                          <div className="text-xs text-slate-500">Portfolio Value</div>
                          <div className="text-lg font-mono">
                            {roundTable.universe_risk?.portfolio_value 
                              ? `$${roundTable.universe_risk.portfolio_value.toLocaleString()}`
                              : '—'}
                          </div>
                        </div>
                        <div className="bg-slate-900/50 p-3 rounded-lg">
                          <div className="text-xs text-slate-500">Buying Power</div>
                          <div className="text-lg font-mono text-cyan-400">
                            {roundTable.universe_risk?.buying_power 
                              ? `$${roundTable.universe_risk.buying_power.toLocaleString()}`
                              : '—'}
                          </div>
                        </div>
                        <div className="bg-slate-900/50 p-3 rounded-lg">
                          <div className="text-xs text-slate-500">Day Trades Left</div>
                          <div className={`text-lg font-mono ${
                            (roundTable.universe_risk?.day_trades_remaining || 0) <= 1 
                              ? 'text-red-400' 
                              : 'text-emerald-400'
                          }`}>
                            {roundTable.universe_risk?.day_trades_remaining ?? '—'}
                          </div>
                        </div>
                      </div>
                      
                      {/* Universe */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-slate-900/50 p-3 rounded-lg">
                          <div className="text-xs text-slate-500">Universe Size</div>
                          <div className="text-xl font-bold">{roundTable.universe_risk?.universe_size || 0}</div>
                          {roundTable.universe_risk?.universe_tickers?.length > 0 && (
                            <div className="text-xs text-slate-400 mt-1 truncate">
                              {roundTable.universe_risk.universe_tickers.slice(0, 5).join(', ')}
                              {roundTable.universe_risk.universe_tickers.length > 5 && '...'}
                            </div>
                          )}
                        </div>
                        <div className="bg-slate-900/50 p-3 rounded-lg">
                          <div className="text-xs text-slate-500">Watchlist</div>
                          <div className="text-xl font-bold">{roundTable.universe_risk?.watchlist_count || 0}</div>
                          {roundTable.universe_risk?.watchlist_tickers?.length > 0 && (
                            <div className="text-xs text-slate-400 mt-1 truncate">
                              {roundTable.universe_risk.watchlist_tickers.slice(0, 5).join(', ')}
                              {roundTable.universe_risk.watchlist_tickers.length > 5 && '...'}
                            </div>
                          )}
                        </div>
                      </div>
                      
                      {/* Blocked/Cooldown */}
                      {(roundTable.universe_risk?.cooldown_tickers?.length > 0 || roundTable.universe_risk?.blocked_tickers?.length > 0) && (
                        <div className="bg-amber-900/20 border border-amber-700 p-3 rounded-lg text-sm">
                          {roundTable.universe_risk?.cooldown_tickers?.length > 0 && (
                            <div className="text-amber-400">
                              <span className="font-medium">Cooldown:</span> {roundTable.universe_risk.cooldown_tickers.join(', ')}
                            </div>
                          )}
                          {roundTable.universe_risk?.blocked_tickers?.length > 0 && (
                            <div className="text-red-400 mt-1">
                              <span className="font-medium">Blocked:</span> {roundTable.universe_risk.blocked_tickers.join(', ')}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </PipelineStage>

                  {/* Stage 2: Strategy Engine */}
                  <PipelineStage
                    icon={Search}
                    title="Strategy Engine"
                    status={getStageStatus(roundTable.strategy.signals_found > 0, roundTable.status)}
                    duration={roundTable.strategy.duration_ms}
                  >
                    <div className="pl-12 space-y-2">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-slate-900/50 p-3 rounded-lg">
                          <div className="text-xs text-slate-500">Tickers Scanned</div>
                          <div className="text-2xl font-bold">{roundTable.strategy.tickers_scanned}</div>
                        </div>
                        <div className="bg-slate-900/50 p-3 rounded-lg">
                          <div className="text-xs text-slate-500">Signals Found</div>
                          <div className="text-2xl font-bold text-cyan-400">
                            {roundTable.strategy.signals_found}
                          </div>
                        </div>
                      </div>
                      {roundTable.strategy.signals.length > 0 && (
                        <div className="text-sm text-slate-400">
                          Signals: {roundTable.strategy.signals.map((s: any) => s.ticker || s).join(', ')}
                        </div>
                      )}
                    </div>
                  </PipelineStage>

                  {/* Stage 2: Mazo Research */}
                  <PipelineStage
                    icon={Brain}
                    title="Mazo Research"
                    status={getStageStatus(roundTable.mazo.success, roundTable.status)}
                    duration={roundTable.mazo.duration_ms}
                  >
                    <div className="pl-12 space-y-3">
                      {roundTable.mazo.success ? (
                        <>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant="outline"
                              className={
                                roundTable.mazo.sentiment === 'bullish'
                                  ? 'border-emerald-500 text-emerald-400'
                                  : roundTable.mazo.sentiment === 'bearish'
                                  ? 'border-red-500 text-red-400'
                                  : 'border-slate-500'
                              }
                            >
                              {roundTable.mazo.sentiment?.toUpperCase() || 'NEUTRAL'}
                            </Badge>
                            <span className="text-sm text-slate-500">
                              Confidence: {roundTable.mazo.sentiment_confidence || 'medium'}
                            </span>
                            <span className="text-sm text-slate-500">
                              ({roundTable.mazo.sources_count} sources)
                            </span>
                          </div>
                          {roundTable.mazo.summary && (
                            <p className="text-sm text-slate-400 bg-slate-900/50 p-3 rounded-lg">
                              {roundTable.mazo.summary}
                            </p>
                          )}
                          {roundTable.mazo.key_points.length > 0 && (
                            <div className="space-y-1">
                              <div className="text-xs text-slate-500">Key Points:</div>
                              <ul className="list-disc list-inside text-sm text-slate-400">
                                {roundTable.mazo.key_points.slice(0, 3).map((point, i) => (
                                  <li key={i}>{point}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </>
                      ) : (
                        <p className="text-sm text-slate-500">No Mazo research data available</p>
                      )}
                    </div>
                  </PipelineStage>

                  {/* Stage 4: AI Agents */}
                  <PipelineStage
                    icon={Users}
                    title={`AI Agents${roundTable.agents.agents.length > 0 ? ` (${roundTable.agents.agents.length})` : ''}`}
                    status={getStageStatus(roundTable.agents.agents.length > 0, roundTable.status)}
                    duration={roundTable.agents.total_duration_ms}
                  >
                    <div className="pl-12">
                      {roundTable.agents.agents.length > 0 ? (
                        <>
                          <div className="flex items-center gap-4 mb-3">
                            <Badge variant="outline" className="border-emerald-500 text-emerald-400">
                              {roundTable.agents.bullish_count} Bullish
                            </Badge>
                            <Badge variant="outline" className="border-red-500 text-red-400">
                              {roundTable.agents.bearish_count} Bearish
                            </Badge>
                            <Badge variant="outline" className="border-slate-500 text-slate-400">
                              {roundTable.agents.neutral_count} Neutral
                            </Badge>
                          </div>
                          <AgentTable agents={roundTable.agents.agents} />
                        </>
                      ) : (
                        <p className="text-sm text-slate-500">No agent signals recorded</p>
                      )}
                    </div>
                  </PipelineStage>

                  {/* Stage 4: Portfolio Manager */}
                  <PipelineStage
                    icon={Target}
                    title="Portfolio Manager"
                    status={getStageStatus(!!roundTable.portfolio_manager.action, roundTable.status)}
                    duration={roundTable.portfolio_manager.duration_ms}
                  >
                    <div className="pl-12 space-y-3">
                      {roundTable.portfolio_manager.action ? (
                        <>
                          <div className="flex items-center gap-3">
                            <Badge
                              className={`text-lg px-3 py-1 ${
                                ['buy', 'cover'].includes(roundTable.portfolio_manager.action.toLowerCase())
                                  ? 'bg-emerald-500'
                                  : ['sell', 'short'].includes(roundTable.portfolio_manager.action.toLowerCase())
                                  ? 'bg-red-500'
                                  : 'bg-slate-500'
                              }`}
                            >
                              {roundTable.portfolio_manager.action.toUpperCase()}
                            </Badge>
                            {roundTable.portfolio_manager.quantity && (
                              <span className="text-lg">
                                {roundTable.portfolio_manager.quantity} shares
                              </span>
                            )}
                            {roundTable.portfolio_manager.confidence && (
                              <span className="text-slate-400">
                                ({roundTable.portfolio_manager.confidence.toFixed(0)}% confidence)
                              </span>
                            )}
                          </div>
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div className="bg-slate-900/50 p-3 rounded-lg">
                              <div className="text-xs text-slate-500">Stop Loss</div>
                              <div className="text-red-400">
                                {roundTable.portfolio_manager.stop_loss_pct
                                  ? `${roundTable.portfolio_manager.stop_loss_pct}%`
                                  : 'Not set'}
                              </div>
                            </div>
                            <div className="bg-slate-900/50 p-3 rounded-lg">
                              <div className="text-xs text-slate-500">Take Profit</div>
                              <div className="text-emerald-400">
                                {roundTable.portfolio_manager.take_profit_pct
                                  ? `${roundTable.portfolio_manager.take_profit_pct}%`
                                  : 'Not set'}
                              </div>
                            </div>
                          </div>
                          {!roundTable.portfolio_manager.action_matches_consensus && roundTable.portfolio_manager.override_reason && (
                            <div className="bg-amber-900/20 border border-amber-700 p-3 rounded-lg text-sm">
                              <div className="text-amber-400 font-medium">⚠️ Override:</div>
                              <p className="text-slate-400">{roundTable.portfolio_manager.override_reason}</p>
                            </div>
                          )}
                          {roundTable.portfolio_manager.reasoning && (
                            <div className="bg-slate-900/50 p-3 rounded-lg text-sm text-slate-400">
                              <div className="text-xs text-slate-500 mb-1">Reasoning:</div>
                              {roundTable.portfolio_manager.reasoning}
                            </div>
                          )}
                        </>
                      ) : (
                        <p className="text-sm text-slate-500">No PM decision recorded</p>
                      )}
                    </div>
                  </PipelineStage>

                  {/* Stage 5: Execution */}
                  <PipelineStage
                    icon={Zap}
                    title="Execution"
                    status={
                      roundTable.execution.error
                        ? 'failed'
                        : getStageStatus(!!roundTable.execution.order_id, roundTable.status)
                    }
                  >
                    <div className="pl-12 space-y-3">
                      {roundTable.execution.order_id ? (
                        <>
                          <div className="flex items-center gap-3">
                            <Badge
                              variant={roundTable.execution.status === 'filled' ? 'default' : 'secondary'}
                              className={roundTable.execution.status === 'filled' ? 'bg-emerald-500' : ''}
                            >
                              {roundTable.execution.status?.toUpperCase() || 'PENDING'}
                            </Badge>
                            <span className="font-mono text-sm">
                              Order: {roundTable.execution.order_id.substring(0, 12)}...
                            </span>
                          </div>
                          {roundTable.execution.filled_avg_price && (
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div className="bg-slate-900/50 p-3 rounded-lg">
                                <div className="text-xs text-slate-500">Fill Price</div>
                                <div className="text-lg font-mono">
                                  ${roundTable.execution.filled_avg_price.toFixed(2)}
                                </div>
                              </div>
                              <div className="bg-slate-900/50 p-3 rounded-lg">
                                <div className="text-xs text-slate-500">Quantity Filled</div>
                                <div className="text-lg font-mono">
                                  {roundTable.execution.filled_qty}
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      ) : roundTable.execution.error ? (
                        <div className="bg-red-900/20 border border-red-700 p-3 rounded-lg text-sm text-red-400">
                          {roundTable.execution.error}
                        </div>
                      ) : (
                        <p className="text-sm text-slate-500">
                          {roundTable.status === 'dry_run'
                            ? 'Dry run — no execution'
                            : 'No execution data'}
                        </p>
                      )}
                    </div>
                  </PipelineStage>

                  {/* Stage 7: Post-Trade Monitoring */}
                  <PipelineStage
                    icon={Eye}
                    title="Post-Trade Monitoring"
                    status={getStageStatus(!!roundTable.post_trade.trade_id, roundTable.status)}
                  >
                    <div className="pl-12 space-y-3">
                      {roundTable.post_trade.trade_id ? (
                        <>
                          <div className="flex items-center gap-3">
                            <Badge variant="outline">
                              Trade #{roundTable.post_trade.trade_id}
                            </Badge>
                            <Badge
                              variant={roundTable.post_trade.status === 'closed' ? 'default' : 'secondary'}
                            >
                              {roundTable.post_trade.status?.toUpperCase() || 'PENDING'}
                            </Badge>
                          </div>
                          {roundTable.post_trade.realized_pnl !== null && (
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div className="bg-slate-900/50 p-3 rounded-lg">
                                <div className="text-xs text-slate-500">Realized P&L</div>
                                <div
                                  className={`text-lg font-mono ${
                                    roundTable.post_trade.realized_pnl >= 0
                                      ? 'text-emerald-400'
                                      : 'text-red-400'
                                  }`}
                                >
                                  {roundTable.post_trade.realized_pnl >= 0 ? '+' : ''}$
                                  {roundTable.post_trade.realized_pnl.toFixed(2)}
                                </div>
                              </div>
                              <div className="bg-slate-900/50 p-3 rounded-lg">
                                <div className="text-xs text-slate-500">Return</div>
                                <div
                                  className={`text-lg font-mono ${
                                    (roundTable.post_trade.return_pct || 0) >= 0
                                      ? 'text-emerald-400'
                                      : 'text-red-400'
                                  }`}
                                >
                                  {(roundTable.post_trade.return_pct || 0) >= 0 ? '+' : ''}
                                  {(roundTable.post_trade.return_pct || 0).toFixed(2)}%
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <p className="text-sm text-slate-500">
                          Position monitoring active — no closed trade yet
                        </p>
                      )}
                    </div>
                  </PipelineStage>

                  {/* Stage 8: Feedback Loop */}
                  <PipelineStage
                    icon={RotateCcw}
                    title="Feedback Loop"
                    status={
                      roundTable.feedback_loop?.status === 'updated' 
                        ? 'completed' 
                        : roundTable.feedback_loop?.status === 'skipped' 
                        ? 'skipped' 
                        : 'pending'
                    }
                  >
                    <div className="pl-12 space-y-3">
                      {roundTable.feedback_loop?.trade_recorded ? (
                        <>
                          {/* Trade Outcome */}
                          <div className="grid grid-cols-3 gap-3">
                            <div className="bg-slate-900/50 p-3 rounded-lg">
                              <div className="text-xs text-slate-500">Trade Recorded</div>
                              <div className="flex items-center gap-2">
                                <CheckCircle className="h-4 w-4 text-emerald-400" />
                                <span className="font-mono">#{roundTable.feedback_loop.trade_id}</span>
                              </div>
                            </div>
                            <div className="bg-slate-900/50 p-3 rounded-lg">
                              <div className="text-xs text-slate-500">Realized P&L</div>
                              <div className={`text-lg font-mono ${
                                (roundTable.feedback_loop.realized_pnl || 0) >= 0 
                                  ? 'text-emerald-400' 
                                  : 'text-red-400'
                              }`}>
                                {(roundTable.feedback_loop.realized_pnl || 0) >= 0 ? '+' : ''}
                                ${(roundTable.feedback_loop.realized_pnl || 0).toFixed(2)}
                              </div>
                            </div>
                            <div className="bg-slate-900/50 p-3 rounded-lg">
                              <div className="text-xs text-slate-500">Result</div>
                              <Badge className={
                                roundTable.feedback_loop.was_profitable 
                                  ? 'bg-emerald-500' 
                                  : roundTable.feedback_loop.was_profitable === false 
                                  ? 'bg-red-500' 
                                  : 'bg-slate-500'
                              }>
                                {roundTable.feedback_loop.was_profitable 
                                  ? '✓ WIN' 
                                  : roundTable.feedback_loop.was_profitable === false 
                                  ? '✗ LOSS' 
                                  : 'PENDING'}
                              </Badge>
                            </div>
                          </div>

                          {/* Agent Accuracy Updates */}
                          {roundTable.feedback_loop.agents_updated > 0 && (
                            <div className="bg-cyan-900/20 border border-cyan-700 p-3 rounded-lg">
                              <div className="text-xs text-cyan-400 font-medium mb-2">
                                Agent Accuracy Updates ({roundTable.feedback_loop.agents_updated} agents)
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {roundTable.feedback_loop.accuracy_updates?.slice(0, 10).map((update, idx) => (
                                  <Badge 
                                    key={idx} 
                                    variant="outline"
                                    className={
                                      update.signal_was_correct 
                                        ? 'border-emerald-500 text-emerald-400' 
                                        : 'border-red-500 text-red-400'
                                    }
                                  >
                                    {update.agent_id.replace(/_/g, ' ')} {update.signal_was_correct ? '✓' : '✗'}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* System Updates */}
                          <div className="flex items-center gap-4 text-sm text-slate-400">
                            {roundTable.feedback_loop.cooldown_set && (
                              <div className="flex items-center gap-1">
                                <Clock className="h-4 w-4" />
                                Cooldown activated
                              </div>
                            )}
                            {roundTable.feedback_loop.position_added && (
                              <div className="flex items-center gap-1">
                                <CheckCircle className="h-4 w-4 text-emerald-400" />
                                Position tracked
                              </div>
                            )}
                          </div>

                          {/* Session Performance */}
                          {roundTable.feedback_loop.session_trades > 0 && (
                            <div className="bg-slate-900/50 p-3 rounded-lg">
                              <div className="text-xs text-slate-500 mb-2">Today's Session</div>
                              <div className="grid grid-cols-3 gap-4">
                                <div>
                                  <div className="text-lg font-mono">{roundTable.feedback_loop.session_trades}</div>
                                  <div className="text-xs text-slate-500">Trades</div>
                                </div>
                                <div>
                                  <div className={`text-lg font-mono ${
                                    (roundTable.feedback_loop.session_pnl || 0) >= 0 
                                      ? 'text-emerald-400' 
                                      : 'text-red-400'
                                  }`}>
                                    {(roundTable.feedback_loop.session_pnl || 0) >= 0 ? '+' : ''}
                                    ${(roundTable.feedback_loop.session_pnl || 0).toFixed(2)}
                                  </div>
                                  <div className="text-xs text-slate-500">P&L</div>
                                </div>
                                <div>
                                  <div className={`text-lg font-mono ${
                                    (roundTable.feedback_loop.session_win_rate || 0) >= 0.5 
                                      ? 'text-emerald-400' 
                                      : 'text-amber-400'
                                  }`}>
                                    {((roundTable.feedback_loop.session_win_rate || 0) * 100).toFixed(0)}%
                                  </div>
                                  <div className="text-xs text-slate-500">Win Rate</div>
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <p className="text-sm text-slate-500">
                          No trade executed — feedback loop skipped
                        </p>
                      )}
                    </div>
                  </PipelineStage>
                </Accordion>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Errors */}
        {roundTable.errors.length > 0 && (
          <Card className="bg-red-900/20 border-red-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-red-400 flex items-center gap-2">
                <AlertCircle className="h-5 w-5" />
                Errors
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-disc list-inside text-sm text-red-400">
                {roundTable.errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
}

export default RoundTable;
