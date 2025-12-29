/**
 * Unified Workflow View
 * 
 * Visual interface for the unified workflow that combines AI Hedge Fund and Mazo.
 * Shows real-time progress of each step with visual flow diagram.
 * 
 * For detailed view with expandable sections, see DetailedWorkflowView.tsx
 */

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { TickerSearch } from '@/components/ticker-search';
import { Badge } from '@/components/ui/badge';
import { 
  Play, 
  Square, 
  CheckCircle2, 
  Loader2, 
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Minus,
  Database,
  Brain,
  FileSearch,
  DollarSign
} from 'lucide-react';
import { runUnifiedWorkflow, UnifiedWorkflowRequest, UnifiedWorkflowResult } from '@/services/unified-workflow-api';

interface WorkflowStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  details?: any;
  startTime?: number;
  endTime?: number;
}

interface WorkflowResult {
  ticker: string;
  signal: string;
  confidence: number;
  agent_signals: Array<{
    agent_name: string;
    signal: string;
    confidence: number;
    reasoning: string;
  }>;
  research_report?: string;
  recommendations: string[];
  trade?: {
    action: string;
    quantity: number;
    executed: boolean;
    order_id?: string;
    filled_price?: number;
    error?: string;
  };
}

export function UnifiedWorkflowView() {
  const [tickers, setTickers] = useState<string>('AAPL');
  const [mode, setMode] = useState<string>('full');
  const [depth, setDepth] = useState<string>('standard');
  const [executeTrades, setExecuteTrades] = useState<boolean>(false);
  const [dryRun, setDryRun] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [results, setResults] = useState<WorkflowResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Initialize workflow steps based on mode
  useEffect(() => {
    const initialSteps: WorkflowStep[] = [];
    
    if (mode === 'signal' || mode === 'pre-research' || mode === 'post-research' || mode === 'full') {
      initialSteps.push({
        id: 'data_aggregation',
        name: 'Data Aggregation',
        status: 'pending',
      });
    }
    
    if (mode === 'research' || mode === 'pre-research' || mode === 'full') {
      initialSteps.push({
        id: 'mazo_initial',
        name: 'Mazo Initial Research',
        status: 'pending',
      });
    }
    
    if (mode === 'signal' || mode === 'pre-research' || mode === 'post-research' || mode === 'full') {
      initialSteps.push({
        id: 'ai_hedge_fund',
        name: 'AI Hedge Fund Analysis',
        status: 'pending',
      });
      initialSteps.push({
        id: 'agents',
        name: '18 Agents Processing',
        status: 'pending',
      });
      initialSteps.push({
        id: 'portfolio_manager',
        name: 'Portfolio Manager Decision',
        status: 'pending',
      });
    }
    
    if (mode === 'research' || mode === 'post-research' || mode === 'full') {
      initialSteps.push({
        id: 'mazo_deep_dive',
        name: 'Mazo Deep Dive',
        status: 'pending',
      });
    }
    
    if (executeTrades || dryRun) {
      initialSteps.push({
        id: 'trade_execution',
        name: 'Trade Execution',
        status: 'pending',
      });
    }
    
    setSteps(initialSteps);
  }, [mode, executeTrades, dryRun]);

  const updateStep = (stepId: string, status: WorkflowStep['status'], details?: any) => {
    setSteps(prev => prev.map(step => {
      if (step.id === stepId) {
        return {
          ...step,
          status,
          details,
          ...(status === 'running' && !step.startTime ? { startTime: Date.now() } : {}),
          ...(status === 'completed' || status === 'error' ? { endTime: Date.now() } : {}),
        };
      }
      return step;
    }));
  };

  const handleRun = async () => {
    if (isRunning) return;
    
    setIsRunning(true);
    setError(null);
    setResults([]);
    
    // Reset all steps to pending
    setSteps(prev => prev.map(step => ({ ...step, status: 'pending' as const })));
    
    // Parse tickers
    const tickerList = tickers.split(',').map(t => t.trim().toUpperCase()).filter(Boolean);
    if (tickerList.length === 0) {
      setError('Please enter at least one ticker');
      setIsRunning(false);
      return;
    }
    
    try {
      // Create abort controller for cancellation
      abortControllerRef.current = new AbortController();
      
      const request: UnifiedWorkflowRequest = {
        tickers: tickerList,
        mode: mode as any,
        depth: depth as any,
        execute_trades: executeTrades,
        dry_run: dryRun,
      };
      
      // Run workflow with streaming
      const results = await runUnifiedWorkflow(
        request,
        (event) => {
          if (event.type === 'start') {
            updateStep('workflow_start', 'running');
          } else if (event.type === 'progress') {
            const stepId = event.agent || '';
            if (stepId.includes('data_aggregation')) {
              updateStep('data_aggregation', 'running', event.data);
            } else if (stepId.includes('ai_hedge_fund') || stepId.includes('analysis_')) {
              updateStep('ai_hedge_fund', 'running', event.data);
              updateStep('agents', 'running', event.data);
            } else if (stepId.includes('mazo')) {
              if (stepId.includes('initial')) {
                updateStep('mazo_initial', 'running', event.data);
              } else {
                updateStep('mazo_deep_dive', 'running', event.data);
              }
            } else if (stepId.includes('trade')) {
              updateStep('trade_execution', 'running', event.data);
            } else if (stepId.includes('portfolio')) {
              updateStep('portfolio_manager', 'running', event.data);
            }
            
            if (event.status === 'completed') {
              updateStep(stepId, 'completed', event.data);
            }
          } else if (event.type === 'complete') {
            setResults(event.data?.results || []);
            // Mark all steps as completed
            setSteps(prev => prev.map(step => 
              step.status === 'running' 
                ? { ...step, status: 'completed' as const, endTime: Date.now() }
                : step
            ));
            setIsRunning(false);
          } else if (event.type === 'error') {
            setError(event.message || 'An error occurred');
            updateStep('error', 'error', { message: event.message });
            setIsRunning(false);
          }
        },
        abortControllerRef.current.signal
      );
      
      setResults(results);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setError('Workflow cancelled');
      } else {
        setError(err.message || 'An error occurred');
      }
      setIsRunning(false);
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsRunning(false);
    setSteps(prev => prev.map(step => 
      step.status === 'running' 
        ? { ...step, status: 'pending' as const }
        : step
    ));
  };

  const getStepIcon = (status: WorkflowStep['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <div className="w-5 h-5 rounded-full border-2 border-gray-300" />;
    }
  };

  const getSignalIcon = (signal: string) => {
    switch (signal?.toUpperCase()) {
      case 'BULLISH':
        return <TrendingUp className="w-4 h-4 text-green-500" />;
      case 'BEARISH':
        return <TrendingDown className="w-4 h-4 text-red-500" />;
      default:
        return <Minus className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="h-full w-full flex flex-col bg-background p-6 overflow-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Unified Trading Workflow</h1>
        <p className="text-muted-foreground">
          Analyze stocks using AI Hedge Fund agents and Mazo research, then execute trades on Alpaca
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        {/* Left Panel: Configuration */}
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="text-lg font-semibold mb-4">Configuration</h2>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Tickers</label>
                <TickerSearch
                  value={tickers}
                  onChange={setTickers}
                  placeholder="Search tickers (e.g., AAPL, MSFT)"
                  disabled={isRunning}
                />
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Workflow Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  disabled={isRunning}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value="signal">Signal Only (AI Hedge Fund)</option>
                  <option value="research">Research Only (Mazo)</option>
                  <option value="pre-research">Pre-Research (Mazo → AI HF)</option>
                  <option value="post-research">Post-Research (AI HF → Mazo)</option>
                  <option value="full">Full Workflow</option>
                </select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Research Depth</label>
                <select
                  value={depth}
                  onChange={(e) => setDepth(e.target.value)}
                  disabled={isRunning}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value="quick">Quick</option>
                  <option value="standard">Standard</option>
                  <option value="deep">Deep</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={dryRun}
                    onChange={(e) => setDryRun(e.target.checked)}
                    disabled={isRunning || executeTrades}
                    className="rounded"
                  />
                  <span className="text-sm">Dry Run (preview trades)</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={executeTrades}
                    onChange={(e) => setExecuteTrades(e.target.checked)}
                    disabled={isRunning || dryRun}
                    className="rounded"
                  />
                  <span className="text-sm">Execute Trades (Alpaca)</span>
                </label>
              </div>

              <div className="flex gap-2 pt-4">
                <Button
                  onClick={handleRun}
                  disabled={isRunning}
                  className="flex-1"
                >
                  {isRunning ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Running...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      Run Analysis
                    </>
                  )}
                </Button>
                {isRunning && (
                  <Button
                    onClick={handleStop}
                    variant="destructive"
                  >
                    <Square className="w-4 h-4 mr-2" />
                    Stop
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* Center Panel: Workflow Visualization */}
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="text-lg font-semibold mb-4">Workflow Progress</h2>
            
            <div className="space-y-3">
              {steps.map((step, index) => (
                <div key={step.id} className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    {getStepIcon(step.status)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{step.name}</span>
                      {step.status === 'running' && step.startTime && (
                        <span className="text-xs text-muted-foreground">
                          {Math.floor((Date.now() - step.startTime) / 1000)}s
                        </span>
                      )}
                    </div>
                    {step.details && (
                      <div className="text-xs text-muted-foreground mt-1">
                        {JSON.stringify(step.details).substring(0, 100)}...
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {steps.length === 0 && (
                <div className="text-sm text-muted-foreground text-center py-8">
                  Configure and run to see workflow progress
                </div>
              )}
            </div>
          </Card>

          {/* Workflow Diagram */}
          <Card className="p-4">
            <h2 className="text-lg font-semibold mb-4">Workflow Flow</h2>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4" />
                <span>Data Aggregation</span>
              </div>
              <div className="ml-6 text-xs text-muted-foreground">↓</div>
              {mode !== 'research' && (
                <>
                  <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4" />
                    <span>AI Hedge Fund (18 Agents)</span>
                  </div>
                  <div className="ml-6 text-xs text-muted-foreground">↓</div>
                </>
              )}
              {mode !== 'signal' && (
                <>
                  <div className="flex items-center gap-2">
                    <FileSearch className="w-4 h-4" />
                    <span>Mazo Research</span>
                  </div>
                  <div className="ml-6 text-xs text-muted-foreground">↓</div>
                </>
              )}
              {(executeTrades || dryRun) && (
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4" />
                  <span>Trade Execution</span>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Right Panel: Results */}
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="text-lg font-semibold mb-4">Results</h2>
            
            {error && (
              <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded">
                <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
                  <AlertCircle className="w-4 h-4" />
                  <span className="font-medium">Error</span>
                </div>
                <p className="text-sm mt-1">{error}</p>
              </div>
            )}

            {results.length > 0 ? (
              <div className="space-y-4">
                {results.map((result, idx) => (
                  <div key={idx} className="border rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold">{result.ticker}</h3>
                      <div className="flex items-center gap-2">
                        {getSignalIcon(result.signal)}
                        <Badge variant={result.signal === 'BULLISH' ? 'default' : 'destructive'}>
                          {result.signal} ({result.confidence}%)
                        </Badge>
                      </div>
                    </div>

                    {result.agent_signals && result.agent_signals.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium mb-2">Agent Signals:</h4>
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                          {result.agent_signals.slice(0, 5).map((agent, i) => (
                            <div key={i} className="text-xs flex justify-between">
                              <span>{agent.agent_name}</span>
                              <span className="text-muted-foreground">
                                {agent.signal} ({agent.confidence}%)
                              </span>
                            </div>
                          ))}
                          {result.agent_signals.length > 5 && (
                            <div className="text-xs text-muted-foreground">
                              +{result.agent_signals.length - 5} more agents
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {result.trade && (
                      <div className="pt-2 border-t">
                        <h4 className="text-sm font-medium mb-2">Trade:</h4>
                        <div className="text-xs space-y-1">
                          <div>Action: {result.trade.action.toUpperCase()}</div>
                          <div>Quantity: {result.trade.quantity}</div>
                          <div>Status: {result.trade.executed ? 'Executed' : 'Not Executed'}</div>
                          {result.trade.order_id && <div>Order ID: {result.trade.order_id}</div>}
                          {result.trade.filled_price && (
                            <div>Filled Price: ${result.trade.filled_price}</div>
                          )}
                          {result.trade.error && (
                            <div className="text-red-500">Error: {result.trade.error}</div>
                          )}
                        </div>
                      </div>
                    )}

                    {result.recommendations && result.recommendations.length > 0 && (
                      <div className="pt-2 border-t">
                        <h4 className="text-sm font-medium mb-2">Recommendations:</h4>
                        <ul className="text-xs space-y-1 list-disc list-inside">
                          {result.recommendations.map((rec, i) => (
                            <li key={i}>{rec}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground text-center py-8">
                Results will appear here after analysis completes
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
