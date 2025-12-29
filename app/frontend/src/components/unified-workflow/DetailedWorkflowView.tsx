/**
 * Detailed Workflow View
 * 
 * Enhanced version with expandable sections showing:
 * - API calls in detail
 * - Agent execution details
 * - Data retrieval information
 * - Mazo research steps
 * - Trade execution details
 */

import { useEffect } from 'react';
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
  DollarSign,
  ChevronDown,
  ChevronRight,
  Globe,
  Clock,
  Activity,
  Zap,
  BarChart3,
  DollarSign as DollarIcon,
  Shield,
  Lightbulb,
  Timer,
  Info
} from 'lucide-react';
import { runUnifiedWorkflow, UnifiedWorkflowRequest } from '@/services/unified-workflow-api';
import { cn } from '@/lib/utils';
import { WorkflowModeHelp } from './WorkflowModeHelp';
import { ResearchDepthHelp } from './ResearchDepthHelp';
import { TradingOptionsHelp } from './TradingOptionsHelp';
import { WorkflowExecutionGraph } from './WorkflowExecutionGraph';
import { 
  useWorkflowContext, 
  DetailedStep,
  APICall,
  AgentExecution,
  DataRetrieval,
  MazoResearch,
  TradeExecution
} from '@/contexts/workflow-context';

// Types are now imported from workflow-context

export function DetailedWorkflowView() {
  // Use workflow context for persistent state across tab switches
  const {
    isRunning,
    steps,
    results,
    error,
    config,
    setIsRunning,
    setSteps,
    setResults,
    setError,
    setConfig,
    abortControllerRef,
    updateStep,
    resetWorkflow,
    toggleStepExpanded,
    setWorkflowStartTime,
  } = useWorkflowContext();

  // Extract config values for easier access
  const { tickers, mode, depth, executeTrades, dryRun, forceRefresh } = config;

  // Helper to update config fields
  const setTickers = (value: string) => setConfig(prev => ({ ...prev, tickers: value }));
  const setMode = (value: string) => setConfig(prev => ({ ...prev, mode: value }));
  const setDepth = (value: string) => setConfig(prev => ({ ...prev, depth: value }));
  const setExecuteTrades = (value: boolean) => setConfig(prev => ({ ...prev, executeTrades: value }));
  const setDryRun = (value: boolean) => setConfig(prev => ({ ...prev, dryRun: value }));
  const setForceRefresh = (value: boolean) => setConfig(prev => ({ ...prev, forceRefresh: value }));

  // Re-initialize steps when mode/trade options change (only if not running)
  useEffect(() => {
    if (!isRunning && results.length === 0) {
      const initialSteps: DetailedStep[] = [];
      
      // Always add workflow_start step
      initialSteps.push({
        id: 'workflow_start',
        name: 'Workflow Start',
        status: 'pending',
      });
      
      if (mode === 'signal' || mode === 'pre-research' || mode === 'post-research' || mode === 'full') {
        initialSteps.push({
          id: 'data_aggregation',
          name: 'Data Aggregation',
          status: 'pending',
          expanded: false,
          subSteps: [],
          dataRetrievals: [],
        });
      }
      
      if (mode === 'research') {
        initialSteps.push({
          id: 'mazo_initial',
          name: 'Mazo Research',
          status: 'pending',
          expanded: false,
          mazoResearch: undefined,
        });
      } else if (mode === 'pre-research' || mode === 'full') {
        initialSteps.push({
          id: 'mazo_initial',
          name: 'Mazo Initial Research',
          status: 'pending',
          expanded: false,
          mazoResearch: undefined,
        });
      }
      
      if (mode === 'signal' || mode === 'pre-research' || mode === 'post-research' || mode === 'full') {
        initialSteps.push({
          id: 'ai_hedge_fund',
          name: 'AI Hedge Fund Analysis',
          status: 'pending',
          expanded: false,
          subSteps: [],
          agentExecutions: [],
        });
        initialSteps.push({
          id: 'agents',
          name: '18 Agents Processing',
          status: 'pending',
          expanded: false,
          subSteps: [],
          agentExecutions: [],
        });
        initialSteps.push({
          id: 'portfolio_manager',
          name: 'Portfolio Manager Decision',
          status: 'pending',
          expanded: false,
          agentExecutions: [],
        });
      }
      
      if (mode === 'post-research' || mode === 'full') {
        initialSteps.push({
          id: 'mazo_deep_dive',
          name: 'Mazo Deep Dive',
          status: 'pending',
          expanded: false,
          mazoResearch: undefined,
        });
      }
      
      if (executeTrades || dryRun) {
        initialSteps.push({
          id: 'trade_execution',
          name: 'Trade Execution',
          status: 'pending',
          expanded: false,
          tradeExecution: undefined,
        });
      }
      
      setSteps(initialSteps);
    }
  }, [mode, executeTrades, dryRun, isRunning, results.length, setSteps]);

  // Use context's toggleStepExpanded
  const toggleStep = toggleStepExpanded;

  const handleRun = async () => {
    if (isRunning) return;
    
    // Reset and start workflow
    resetWorkflow();
    setIsRunning(true);
    setWorkflowStartTime(Date.now());
    
    const tickerList = tickers.split(',').map(t => t.trim().toUpperCase()).filter(Boolean);
    if (tickerList.length === 0) {
      setError('Please enter at least one ticker');
      setIsRunning(false);
      return;
    }
    
    try {
      abortControllerRef.current = new AbortController();
      
      const request: UnifiedWorkflowRequest = {
        tickers: tickerList,
        mode: mode as any,
        depth: depth as any,
        execute_trades: executeTrades,
        dry_run: dryRun,
        force_refresh: forceRefresh,
      };
      
      const workflowResults = await runUnifiedWorkflow(
        request,
        (event) => {
          console.log('[DetailedWorkflowView] Received event:', event.type, event.agent, event.status);
          if (event.type === 'start') {
            console.log('[DetailedWorkflowView] Start event - updating workflow_start');
            updateStep('workflow_start', 'running');
            } else if (event.type === 'progress') {
            const stepId = event.agent || '';
            const details = event.data;
            console.log('[DetailedWorkflowView] Progress event:', { stepId, status: event.status, hasDetails: !!details });
            
            // Determine the actual status from the event
            let actualStatus: DetailedStep['status'] = 'pending';
            if (event.status === 'completed' || details?.status === 'complete') {
              actualStatus = 'completed';
            } else if (event.status === 'running' || details?.status === 'running') {
              actualStatus = 'running';
            } else if (details?.status === 'error' || event.status === 'error') {
              actualStatus = 'error';
            }
            
            // Map step IDs correctly, especially for Mazo research
            let mappedStepId = stepId;
            if (stepId === 'mazo_research') {
              mappedStepId = 'mazo_initial';
            } else if (stepId === 'mazo_research_active') {
              mappedStepId = 'mazo_initial';
            } else if (stepId === 'mazo_initial_research') {
              mappedStepId = 'mazo_initial';
            } else if (stepId === 'mazo_deep_dive') {
              mappedStepId = 'mazo_deep_dive';
            } else if (stepId.includes('mazo')) {
              if (stepId.includes('initial') || stepId.includes('initial_research')) {
                mappedStepId = 'mazo_initial';
              } else if (stepId.includes('deep_dive') || stepId.includes('deep')) {
                mappedStepId = 'mazo_deep_dive';
              } else if (stepId.includes('research') && mode === 'research') {
                mappedStepId = 'mazo_initial';
              }
            }
            
            // Update steps based on mapped ID
            if (mappedStepId.includes('data_aggregation')) {
              updateStep('data_aggregation', actualStatus, details);
            } else if (mappedStepId.includes('ai_hedge_fund') || mappedStepId.includes('analysis_')) {
              updateStep('ai_hedge_fund', actualStatus, details);
              if (actualStatus !== 'pending') {
                updateStep('agents', actualStatus, details);
              }
            } else if (mappedStepId.includes('mazo')) {
              if (mappedStepId === 'mazo_initial' || mappedStepId.includes('initial')) {
                updateStep('mazo_initial', actualStatus, details);
              } else if (mappedStepId === 'mazo_deep_dive' || mappedStepId.includes('deep_dive')) {
                updateStep('mazo_deep_dive', actualStatus, details);
              }
            } else if (mappedStepId.includes('trade')) {
              updateStep('trade_execution', actualStatus, details);
            } else if (mappedStepId.includes('portfolio')) {
              updateStep('portfolio_manager', actualStatus, details);
            } else if (mappedStepId && actualStatus !== 'pending') {
              updateStep(mappedStepId, actualStatus, details);
            }
          } else if (event.type === 'complete') {
            setResults(event.data?.results || []);
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
      
      setResults(workflowResults);
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
  };

  const getStepIcon = (status: DetailedStep['status']) => {
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

  const renderAPICalls = (apiCalls?: APICall[]) => {
    if (!apiCalls || apiCalls.length === 0) return null;
    
    return (
      <div className="mt-3 space-y-2">
        <h4 className="text-sm font-semibold flex items-center gap-2">
          <Globe className="w-4 h-4" />
          API Calls ({apiCalls.length})
        </h4>
        <div className="space-y-2 pl-4">
          {apiCalls.map((call, idx) => (
            <div key={idx} className="text-xs bg-gray-50 dark:bg-gray-900 p-2 rounded border">
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs">{call.method} {call.url}</span>
                <Badge 
                  variant={call.cacheHit ? 'default' : 'secondary'} 
                  className={`text-xs ${call.cacheHit ? '' : 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'}`}
                >
                  {call.cacheHit ? '⚠️ Cached' : '✅ Fresh'}
                </Badge>
              </div>
              {call.statusCode && (
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>Status: {call.statusCode}</span>
                  {call.responseTimeMs && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {call.responseTimeMs.toFixed(0)}ms
                    </span>
                  )}
                </div>
              )}
              {call.error && (
                <div className="text-red-500 text-xs mt-1">Error: {call.error}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderAgentExecutions = (executions?: AgentExecution[]) => {
    if (!executions || executions.length === 0) return null;
    
    return (
      <div className="mt-3 space-y-2">
        <h4 className="text-sm font-semibold flex items-center gap-2">
          <Brain className="w-4 h-4" />
          Agent Executions ({executions.length})
        </h4>
        <div className="space-y-2 pl-4">
          {executions.map((exec, idx) => {
            // Safely handle reasoning - format objects as JSON for readability
            const reasoningText = exec.reasoning 
              ? (typeof exec.reasoning === 'string' 
                  ? exec.reasoning 
                  : JSON.stringify(exec.reasoning, null, 2))
              : null;
            
            return (
              <div key={idx} className="text-xs bg-blue-50 dark:bg-blue-900/20 p-2 rounded border">
                <div className="font-semibold mb-1">
                  {exec.agentName || 'Unknown Agent'} - {exec.ticker || 'N/A'}
                </div>
                {exec.signal && (
                  <div className="flex items-center gap-2 mb-1">
                    <span>Signal: {exec.signal}</span>
                    {exec.confidence !== undefined && exec.confidence !== null && (
                      <span>({typeof exec.confidence === 'number' ? exec.confidence.toFixed(2) : exec.confidence}%)</span>
                    )}
                  </div>
                )}
                {reasoningText && (
                  <div className="text-muted-foreground mt-1 p-2 bg-white dark:bg-gray-800 rounded border max-h-96 overflow-y-auto whitespace-pre-wrap text-xs">
                    {reasoningText}
                  </div>
                )}
                {exec.executionTimeMs !== undefined && exec.executionTimeMs !== null && (
                  <div className="text-xs text-muted-foreground mt-1">
                    Execution time: {typeof exec.executionTimeMs === 'number' ? exec.executionTimeMs.toFixed(0) : exec.executionTimeMs}ms
                  </div>
                )}
                {exec.apiCalls && exec.apiCalls.length > 0 && (
                  <div className="mt-2">
                    <div className="text-xs font-semibold">API Calls: {exec.apiCalls.length}</div>
                    {renderAPICalls(exec.apiCalls)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderDataRetrievals = (retrievals?: DataRetrieval[]) => {
    if (!retrievals || retrievals.length === 0) return null;
    
    return (
      <div className="mt-3 space-y-2">
        <h4 className="text-sm font-semibold flex items-center gap-2">
          <Database className="w-4 h-4" />
          Data Retrievals ({retrievals.length})
        </h4>
        <div className="space-y-2 pl-4">
          {retrievals.map((ret, idx) => (
            <div key={idx} className="text-xs bg-green-50 dark:bg-green-900/20 p-3 rounded border">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold">{ret.dataType} - {ret.ticker}</span>
                <Badge variant={ret.cacheHit ? 'default' : 'secondary'}>
                  {ret.cacheHit ? 'Cache Hit' : 'API Fetch'}
                </Badge>
              </div>
              <div className="text-muted-foreground mb-2">
                Records: {ret.recordsRetrieved}
              </div>
              {/* Show detailed data if available */}
              {ret.details && (
                <div className="mt-2 p-2 bg-white dark:bg-gray-800 rounded text-xs">
                  <div className="font-semibold mb-1">Sample Data:</div>
                  <pre className="overflow-x-auto text-[10px]">
                    {JSON.stringify(ret.details, null, 2)}
                  </pre>
                </div>
              )}
              {ret.apiCalls && ret.apiCalls.length > 0 && renderAPICalls(ret.apiCalls)}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderMazoResearch = (research?: MazoResearch) => {
    if (!research) return null;
    
    // Get the full answer (preferred) or response, or answerPreview
    const fullAnswer = research.answer || research.response || research.answerPreview || null;
    
    // Safely handle response string
    const responseText = fullAnswer
      ? (typeof fullAnswer === 'string' ? fullAnswer : String(fullAnswer))
      : null;
    
    return (
      <div className="mt-3 space-y-2">
        <h4 className="text-sm font-semibold flex items-center gap-2">
          <FileSearch className="w-4 h-4" />
          Mazo Research
        </h4>
        <div className="text-xs bg-purple-50 dark:bg-purple-900/20 p-3 rounded border pl-4">
          <div className="mb-2">
            <span className="font-semibold">Ticker:</span> {research.ticker || 'N/A'}
          </div>
          {research.method && (
            <div className="mb-2">
              <span className="font-semibold">Method:</span> {research.method}
            </div>
          )}
          <div className="mb-2">
            <span className="font-semibold">Query:</span>
            <div className="text-muted-foreground mt-1 whitespace-pre-wrap">{research.query || 'N/A'}</div>
          </div>
          {research.depth && (
            <div className="mb-2">
              <span className="font-semibold">Depth:</span> {research.depth}
            </div>
          )}
          {research.executionTimeMs !== undefined && research.executionTimeMs !== null && (
            <div className="mb-2">
              <span className="font-semibold">Execution Time:</span> {
                typeof research.executionTimeMs === 'number' 
                  ? research.executionTimeMs.toFixed(0) 
                  : research.executionTimeMs
              }ms
            </div>
          )}
          {research.success !== undefined && (
            <div className="mb-2">
              <span className="font-semibold">Status:</span> 
              <Badge variant={research.success ? 'default' : 'destructive'} className="ml-2">
                {research.success ? 'Success' : 'Failed'}
              </Badge>
            </div>
          )}
          {research.confidence !== undefined && research.confidence !== null && (
            <div className="mb-2">
              <span className="font-semibold">Confidence:</span> {
                typeof research.confidence === 'number' 
                  ? (research.confidence * 100).toFixed(1) 
                  : research.confidence
              }%
            </div>
          )}
          {research.answerLength !== undefined && research.answerLength !== null && (
            <div className="mb-2">
              <span className="font-semibold">Answer Length:</span> {research.answerLength} characters
            </div>
          )}
          {research.tasksCompleted && research.tasksCompleted.length > 0 && (
            <div className="mb-2">
              <span className="font-semibold">Tasks Completed:</span>
              <ul className="list-disc list-inside mt-1 text-muted-foreground">
                {research.tasksCompleted.map((task, i) => (
                  <li key={i}>{task}</li>
                ))}
              </ul>
            </div>
          )}
          {research.dataSources && research.dataSources.length > 0 && (
            <div className="mb-2">
              <span className="font-semibold">Data Sources:</span>
              <div className="text-muted-foreground mt-1">
                {research.dataSources.join(', ')}
              </div>
            </div>
          )}
          {research.steps && research.steps.length > 0 && (
            <div className="mb-2">
              <span className="font-semibold">Steps:</span> {research.steps.length}
              <div className="mt-1 p-2 bg-white dark:bg-gray-800 rounded text-[10px] max-h-40 overflow-y-auto">
                <pre>{JSON.stringify(research.steps, null, 2)}</pre>
              </div>
            </div>
          )}
          {responseText && (
            <div className="mb-2">
              <span className="font-semibold">Research Report (Full):</span>
              <div className="text-muted-foreground mt-1 p-3 bg-white dark:bg-gray-800 rounded border max-h-[600px] overflow-y-auto whitespace-pre-wrap text-sm">
                {responseText}
              </div>
            </div>
          )}
          {research.error && (
            <div className="mb-2 text-red-500">
              <span className="font-semibold">Error:</span> {research.error}
            </div>
          )}
          {research.apiCalls && research.apiCalls.length > 0 && renderAPICalls(research.apiCalls)}
        </div>
      </div>
    );
  };

  const renderTradeExecution = (trade?: TradeExecution) => {
    if (!trade) return null;
    
    return (
      <div className="mt-3 space-y-2">
        <h4 className="text-sm font-semibold flex items-center gap-2">
          <DollarSign className="w-4 h-4" />
          Trade Execution
        </h4>
        <div className="text-xs bg-yellow-50 dark:bg-yellow-900/20 p-3 rounded border pl-4">
          <div className="grid grid-cols-2 gap-2 mb-2">
            <div><span className="font-semibold">Ticker:</span> {trade.ticker}</div>
            <div><span className="font-semibold">Action:</span> {trade.action.toUpperCase()}</div>
            <div><span className="font-semibold">Quantity:</span> {trade.quantity}</div>
            <div><span className="font-semibold">Status:</span> {trade.executed ? 'Executed' : 'Not Executed'}</div>
            {trade.orderId && <div><span className="font-semibold">Order ID:</span> {trade.orderId}</div>}
            {trade.filledPrice && <div><span className="font-semibold">Filled Price:</span> ${trade.filledPrice}</div>}
          </div>
          {trade.error && (
            <div className="text-red-500">Error: {trade.error}</div>
          )}
          {trade.apiCalls && trade.apiCalls.length > 0 && renderAPICalls(trade.apiCalls)}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full w-full flex flex-col bg-background p-6 overflow-auto">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">Mazo's Detailed Trading Workflow</h1>
          <p className="text-muted-foreground">
            Complete transparency: See every API call, agent execution, data retrieval, and trade execution
          </p>
        </div>
        <WorkflowModeHelp />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1">
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
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium block">Workflow Mode</label>
                  <WorkflowModeHelp />
                </div>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  disabled={isRunning}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value="signal">Signal Only</option>
                  <option value="research">Research Only</option>
                  <option value="pre-research">Pre-Research</option>
                  <option value="post-research">Post-Research</option>
                  <option value="full">Full Workflow</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium block">Research Depth</label>
                  <ResearchDepthHelp />
                </div>
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

              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={forceRefresh}
                        onChange={(e) => setForceRefresh(e.target.checked)}
                        disabled={isRunning}
                        className="rounded"
                      />
                      <span className="text-sm font-medium">Force Fresh Data</span>
                    </label>
                    <Info className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <p className="text-xs text-muted-foreground ml-6">
                    Bypass cache and fetch fresh data from API. Slower but ensures data freshness.
                  </p>
                  {forceRefresh && (
                    <div className="ml-6 mt-2 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-800">
                      <p className="text-xs text-yellow-700 dark:text-yellow-300">
                        <strong>Fresh Data Mode:</strong> All API calls will bypass cache. This may take longer but ensures you have the latest data.
                      </p>
                    </div>
                  )}
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={dryRun}
                        onChange={(e) => setDryRun(e.target.checked)}
                        disabled={isRunning || executeTrades}
                        className="rounded"
                      />
                      <span className="text-sm font-medium">Dry Run</span>
                    </label>
                    <TradingOptionsHelp />
                  </div>
                  <p className="text-xs text-muted-foreground ml-6">
                    Simulate trades without executing. Safe for testing.
                  </p>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={executeTrades}
                        onChange={(e) => setExecuteTrades(e.target.checked)}
                        disabled={isRunning || dryRun}
                        className="rounded"
                      />
                      <span className="text-sm font-medium">Execute Trades</span>
                    </label>
                    <TradingOptionsHelp />
                  </div>
                  <p className="text-xs text-muted-foreground ml-6">
                    Actually place orders with your broker. Real money at risk.
                  </p>
                </div>
                {dryRun && (
                  <div className="ml-6 p-2 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
                    <p className="text-xs text-blue-700 dark:text-blue-300">
                      <strong>Dry Run Active:</strong> Trades will be simulated but not executed. Perfect for testing and validation.
                    </p>
                  </div>
                )}
                {executeTrades && (
                  <div className="ml-6 p-2 bg-orange-50 dark:bg-orange-900/20 rounded border border-orange-200 dark:border-orange-800">
                    <p className="text-xs text-orange-700 dark:text-orange-300">
                      <strong>⚠️ Live Trading:</strong> Real trades will be executed with your broker. Make sure you've tested with Dry Run first!
                    </p>
                  </div>
                )}
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
                  <Button onClick={handleStop} variant="destructive">
                    <Square className="w-4 h-4 mr-2" />
                    Stop
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* Center Panel: Detailed Workflow Progress */}
        <div className="lg:col-span-2 space-y-4">
          {/* Workflow Execution Graph */}
          <WorkflowExecutionGraph steps={steps} mode={mode} />
          
          <Card className="p-4">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5" />
              Detailed Workflow Progress
            </h2>
            
            <div className="space-y-3">
              {steps.map((step) => (
                <div key={step.id} className="border rounded-lg">
                  <div
                    className={cn(
                      "flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors",
                      step.expanded && "bg-gray-50 dark:bg-gray-900"
                    )}
                    onClick={() => toggleStep(step.id)}
                  >
                    <div className="flex-shrink-0">
                      {step.expanded ? (
                        <ChevronDown className="w-4 h-4" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                    </div>
                    <div className="flex-shrink-0">
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
                    </div>
                  </div>
                  
                  {step.expanded && (
                    <div className="px-3 pb-3 space-y-3 border-t pt-3">
                      {/* Show summary first if available */}
                      {step.details && step.details.summary && (
                        <div className="text-xs bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg border">
                          <div className="font-semibold mb-2 flex items-center gap-2">
                            <Activity className="w-3.5 h-3.5" />
                            Summary
                          </div>
                          {typeof step.details.summary === 'string' ? (
                            <div className="text-muted-foreground">
                              {step.details.summary}
                            </div>
                          ) : typeof step.details.summary === 'object' && step.details.summary !== null ? (
                            <div className="space-y-3">
                              {/* Main message */}
                              {step.details.summary.message && (
                                <div className="font-medium text-foreground pb-2 border-b">
                                  {step.details.summary.message}
                                </div>
                              )}
                              
                              {/* Cache Status (for Data Aggregation) */}
                              {step.id === 'data_aggregation' && step.details.cache_stats && (
                                <div className="pt-2 border-t space-y-2">
                                  <div className="flex items-center gap-2 font-semibold text-[11px] text-muted-foreground uppercase tracking-wide">
                                    <Shield className="w-3 h-3" />
                                    Data Freshness
                                  </div>
                                  <div className="grid grid-cols-2 gap-2">
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Cache Hits:</span>
                                      <span className="font-semibold">{step.details.cache_stats.cache_hits || 0}</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Fresh API Calls:</span>
                                      <span className="font-semibold text-green-600">{step.details.cache_stats.cache_misses || 0}</span>
                                    </div>
                                    <div className="col-span-2 flex items-center justify-between pt-1 border-t">
                                      <span className="text-muted-foreground">Fresh Data:</span>
                                      <span className={`font-semibold ${
                                        (step.details.cache_stats.fresh_data_percent || 0) >= 50 ? 'text-green-600' :
                                        (step.details.cache_stats.fresh_data_percent || 0) > 0 ? 'text-yellow-600' :
                                        'text-orange-600'
                                      }`}>
                                        {step.details.cache_stats.fresh_data_percent || 0}%
                                      </span>
                                    </div>
                                  </div>
                                  {(step.details.cache_stats.fresh_data_percent || 0) < 50 && (
                                    <div className="pt-2 p-2 bg-orange-50 dark:bg-orange-900/20 rounded border border-orange-200 dark:border-orange-800">
                                      <div className="flex items-start gap-2 text-[10px] text-orange-700 dark:text-orange-300">
                                        <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                        <div>
                                          <strong>Warning:</strong> Most data came from cache. Enable "Force Fresh Data" to ensure you have the latest information.
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                              
                              {/* Statistics */}
                              {step.details.summary.statistics && (
                                <div className="space-y-2">
                                  <div className="font-semibold text-[11px] text-muted-foreground uppercase tracking-wide">
                                    Statistics
                                  </div>
                                  <div className="grid grid-cols-2 gap-2">
                                    {step.details.summary.statistics.total_agents !== undefined && (
                                      <div className="flex items-center justify-between">
                                        <span className="text-muted-foreground">Total Agents:</span>
                                        <span className="font-semibold">{step.details.summary.statistics.total_agents}</span>
                                      </div>
                                    )}
                                    {step.details.summary.statistics.tickers_processed !== undefined && (
                                      <div className="flex items-center justify-between">
                                        <span className="text-muted-foreground">Tickers:</span>
                                        <span className="font-semibold">{step.details.summary.statistics.tickers_processed}</span>
                                      </div>
                                    )}
                                    {step.details.summary.statistics.average_confidence !== undefined && (
                                      <div className="flex items-center justify-between">
                                        <span className="text-muted-foreground">Avg Confidence:</span>
                                        <span className="font-semibold">{step.details.summary.statistics.average_confidence}%</span>
                                      </div>
                                    )}
                                    {step.details.summary.statistics.agents_per_ticker !== undefined && (
                                      <div className="flex items-center justify-between">
                                        <span className="text-muted-foreground">Agents/Ticker:</span>
                                        <span className="font-semibold">{Math.round(step.details.summary.statistics.agents_per_ticker)}</span>
                                      </div>
                                    )}
                                  </div>
                                  
                                  {/* Signal Distribution */}
                                  {step.details.summary.statistics.signal_distribution && 
                                   Object.keys(step.details.summary.statistics.signal_distribution).length > 0 && (
                                    <div className="pt-2 border-t">
                                      <div className="font-semibold text-[11px] text-muted-foreground uppercase tracking-wide mb-1">
                                        Signal Distribution
                                      </div>
                                      <div className="flex flex-wrap gap-2">
                                        {Object.entries(step.details.summary.statistics.signal_distribution).map(([signal, count]) => {
                                          const variant = signal === 'BULLISH' ? 'default' : 
                                                         signal === 'BEARISH' ? 'destructive' : 'secondary';
                                          return (
                                            <Badge key={signal} variant={variant} className="text-[10px]">
                                              {signal}: {String(count)}
                                            </Badge>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  )}
                                  
                                  {/* Agents by Ticker */}
                                  {step.details.summary.statistics.agents_by_ticker && 
                                   Object.keys(step.details.summary.statistics.agents_by_ticker).length > 0 && (
                                    <div className="pt-2 border-t">
                                      <div className="font-semibold text-[11px] text-muted-foreground uppercase tracking-wide mb-1">
                                        Agents by Ticker
                                      </div>
                                      <div className="space-y-1">
                                        {Object.entries(step.details.summary.statistics.agents_by_ticker).map(([ticker, count]) => (
                                          <div key={ticker} className="flex items-center justify-between text-[10px]">
                                            <span className="font-mono font-medium">{ticker}:</span>
                                            <span className="text-muted-foreground">{String(count)} agents</span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                              
                              {/* Execution Time Metrics */}
                              {step.details.summary.execution_time && (
                                <div className="pt-3 border-t space-y-2">
                                  <div className="flex items-center gap-2 font-semibold text-[11px] text-muted-foreground uppercase tracking-wide">
                                    <Timer className="w-3 h-3" />
                                    Execution Time
                                  </div>
                                  <div className="grid grid-cols-2 gap-2">
                                    {step.details.summary.execution_time.total_formatted && (
                                      <div className="flex items-center justify-between">
                                        <span className="text-muted-foreground">Total:</span>
                                        <span className="font-semibold">{step.details.summary.execution_time.total_formatted}</span>
                                      </div>
                                    )}
                                    {step.details.summary.execution_time.average_per_agent_ms !== undefined && (
                                      <div className="flex items-center justify-between">
                                        <span className="text-muted-foreground">Avg/Agent:</span>
                                        <span className="font-semibold">{step.details.summary.execution_time.average_per_agent_ms}ms</span>
                                      </div>
                                    )}
                                    {step.details.summary.execution_time.fastest_agent_ms !== undefined && (
                                      <div className="flex items-center justify-between">
                                        <span className="text-muted-foreground">Fastest:</span>
                                        <span className="font-semibold text-green-600">{step.details.summary.execution_time.fastest_agent_ms}ms</span>
                                      </div>
                                    )}
                                    {step.details.summary.execution_time.slowest_agent_ms !== undefined && (
                                      <div className="flex items-center justify-between">
                                        <span className="text-muted-foreground">Slowest:</span>
                                        <span className="font-semibold text-orange-600">{step.details.summary.execution_time.slowest_agent_ms}ms</span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )}
                              
                              {/* Confidence Distribution */}
                              {step.details.summary.confidence_distribution && (
                                <div className="pt-3 border-t space-y-2">
                                  <div className="flex items-center gap-2 font-semibold text-[11px] text-muted-foreground uppercase tracking-wide">
                                    <BarChart3 className="w-3 h-3" />
                                    Confidence Distribution
                                  </div>
                                  <div className="grid grid-cols-2 gap-2">
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Min:</span>
                                      <span className="font-semibold">{step.details.summary.confidence_distribution.min}%</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Max:</span>
                                      <span className="font-semibold">{step.details.summary.confidence_distribution.max}%</span>
                                    </div>
                                  </div>
                                  <div className="space-y-1 pt-1">
                                    <div className="flex items-center justify-between text-[10px]">
                                      <span className="text-green-600">High (≥{step.details.summary.confidence_distribution.high_confidence_threshold}%):</span>
                                      <Badge variant="default" className="text-[9px] px-1.5 py-0">
                                        {step.details.summary.confidence_distribution.high_confidence_count}
                                      </Badge>
                                    </div>
                                    <div className="flex items-center justify-between text-[10px]">
                                      <span className="text-yellow-600">Medium ({step.details.summary.confidence_distribution.medium_confidence_threshold}-{step.details.summary.confidence_distribution.high_confidence_threshold}%):</span>
                                      <Badge variant="secondary" className="text-[9px] px-1.5 py-0">
                                        {step.details.summary.confidence_distribution.medium_confidence_count}
                                      </Badge>
                                    </div>
                                    <div className="flex items-center justify-between text-[10px]">
                                      <span className="text-red-600">Low (&lt;{step.details.summary.confidence_distribution.medium_confidence_threshold}%):</span>
                                      <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                                        {step.details.summary.confidence_distribution.low_confidence_count}
                                      </Badge>
                                    </div>
                                  </div>
                                </div>
                              )}
                              
                              {/* Agent Performance */}
                              {step.details.summary.agent_performance && (
                                <div className="pt-3 border-t space-y-2">
                                  <div className="flex items-center gap-2 font-semibold text-[11px] text-muted-foreground uppercase tracking-wide">
                                    <Zap className="w-3 h-3" />
                                    Agent Performance
                                  </div>
                                  <div className="grid grid-cols-2 gap-2">
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Successful:</span>
                                      <span className="font-semibold text-green-600">{step.details.summary.agent_performance.successful}</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Failed:</span>
                                      <span className="font-semibold text-red-600">{step.details.summary.agent_performance.failed}</span>
                                    </div>
                                    <div className="col-span-2 flex items-center justify-between pt-1 border-t">
                                      <span className="text-muted-foreground">Success Rate:</span>
                                      <span className="font-semibold">{step.details.summary.agent_performance.success_rate}%</span>
                                    </div>
                                  </div>
                                </div>
                              )}
                              
                              {/* API Usage */}
                              {step.details.summary.api_usage && (
                                <div className="pt-3 border-t space-y-2">
                                  <div className="flex items-center gap-2 font-semibold text-[11px] text-muted-foreground uppercase tracking-wide">
                                    <DollarIcon className="w-3 h-3" />
                                    API Usage (Estimated)
                                  </div>
                                  <div className="grid grid-cols-2 gap-2">
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Total Tokens:</span>
                                      <span className="font-semibold">{step.details.summary.api_usage.estimated_total_tokens?.toLocaleString()}</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Est. Cost:</span>
                                      <span className="font-semibold text-green-600">${step.details.summary.api_usage.estimated_cost_usd}</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Input Tokens:</span>
                                      <span className="font-semibold">{step.details.summary.api_usage.estimated_input_tokens?.toLocaleString()}</span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Output Tokens:</span>
                                      <span className="font-semibold">{step.details.summary.api_usage.estimated_output_tokens?.toLocaleString()}</span>
                                    </div>
                                  </div>
                                  {step.details.summary.api_usage.note && (
                                    <div className="text-[9px] text-muted-foreground italic pt-1">
                                      {step.details.summary.api_usage.note}
                                    </div>
                                  )}
                                </div>
                              )}
                              
                              {/* Data Quality */}
                              {step.details.summary.data_quality && (
                                <div className="pt-3 border-t space-y-2">
                                  <div className="flex items-center gap-2 font-semibold text-[11px] text-muted-foreground uppercase tracking-wide">
                                    <Shield className="w-3 h-3" />
                                    Data Quality
                                  </div>
                                  <div className="grid grid-cols-2 gap-2">
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Completeness:</span>
                                      <span className={`font-semibold ${
                                        step.details.summary.data_quality.data_completeness_percent >= 100 ? 'text-green-600' :
                                        step.details.summary.data_quality.data_completeness_percent >= 80 ? 'text-yellow-600' :
                                        'text-red-600'
                                      }`}>
                                        {step.details.summary.data_quality.data_completeness_percent}%
                                      </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                      <span className="text-muted-foreground">Tickers w/ Data:</span>
                                      <span className="font-semibold">{step.details.summary.data_quality.tickers_with_data}</span>
                                    </div>
                                  </div>
                                  {step.details.summary.data_quality.warnings && step.details.summary.data_quality.warnings.length > 0 && (
                                    <div className="pt-2 space-y-1">
                                      {step.details.summary.data_quality.warnings.map((warning: string, idx: number) => (
                                        <div key={idx} className="text-[10px] text-orange-600 bg-orange-50 dark:bg-orange-900/20 p-1.5 rounded border border-orange-200 dark:border-orange-800">
                                          <AlertCircle className="w-3 h-3 inline mr-1" />
                                          {warning}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                              
                              {/* Recommendations Preview */}
                              {step.details.summary.recommendations_preview && step.details.summary.recommendations_preview.length > 0 && (
                                <div className="pt-3 border-t space-y-2">
                                  <div className="flex items-center gap-2 font-semibold text-[11px] text-muted-foreground uppercase tracking-wide">
                                    <Lightbulb className="w-3 h-3" />
                                    Top Recommendations
                                  </div>
                                  <div className="space-y-2">
                                    {step.details.summary.recommendations_preview.map((rec: any, idx: number) => (
                                      <div key={idx} className="text-[10px] p-2 bg-gray-50 dark:bg-gray-800 rounded border">
                                        <div className="flex items-center justify-between mb-1">
                                          <span className="font-mono font-semibold">{rec.ticker}</span>
                                          <Badge 
                                            variant={rec.signal === 'BULLISH' ? 'default' : rec.signal === 'BEARISH' ? 'destructive' : 'secondary'}
                                            className="text-[9px] px-1.5 py-0"
                                          >
                                            {rec.signal} {rec.confidence}%
                                          </Badge>
                                        </div>
                                        {rec.top_recommendation && (
                                          <div className="text-muted-foreground mt-1 italic">
                                            {rec.top_recommendation}
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              
                              {/* Fallback for other object structures */}
                              {!step.details.summary.message && !step.details.summary.statistics && 
                               !step.details.summary.execution_time && !step.details.summary.confidence_distribution &&
                               !step.details.summary.agent_performance && !step.details.summary.api_usage &&
                               !step.details.summary.data_quality && !step.details.summary.recommendations_preview && (
                                <div className="grid grid-cols-2 gap-2">
                                  {Object.entries(step.details.summary).map(([key, value]) => (
                                    <div key={key}>
                                      <span className="font-medium">{key.replace(/_/g, ' ')}:</span> {String(value)}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-muted-foreground">
                              {String(step.details.summary)}
                            </div>
                          )}
                        </div>
                      )}
                      
                      {/* Mazo Research Integration (for Portfolio Manager) */}
                      {step.id === 'portfolio_manager' && step.details && step.details.mazo_research_integration && (
                        <div className="text-xs bg-green-50 dark:bg-green-900/20 p-3 rounded-lg border border-green-200 dark:border-green-800">
                          <div className="font-semibold mb-2 flex items-center gap-2">
                            <FileSearch className="w-3.5 h-3.5" />
                            Mazo Research Integration Status
                          </div>
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-muted-foreground">Mazo Research Provided to PM:</span>
                              <Badge variant={step.details.mazo_research_integration.mazo_research_provided ? 'default' : 'secondary'}>
                                {step.details.mazo_research_integration.mazo_research_provided ? '✅ Yes' : '❌ No'}
                              </Badge>
                            </div>
                            
                            {/* Integration Details */}
                            {step.details.mazo_research_integration.integration_details && (
                              <div className="pt-2 border-t space-y-1">
                                <div className="text-muted-foreground text-[10px] mb-1">Research Available:</div>
                                <div className="flex items-center gap-2 text-[10px]">
                                  <Badge variant={step.details.mazo_research_integration.integration_details.initial_research_provided ? 'default' : 'outline'} className="text-[9px] px-1.5 py-0">
                                    {step.details.mazo_research_integration.integration_details.initial_research_provided ? '✅' : '❌'} Initial Research
                                  </Badge>
                                  <Badge variant={step.details.mazo_research_integration.integration_details.deep_dive_provided ? 'default' : 'outline'} className="text-[9px] px-1.5 py-0">
                                    {step.details.mazo_research_integration.integration_details.deep_dive_provided ? '✅' : '❌'} Deep Dive
                                  </Badge>
                                </div>
                                {step.details.mazo_research_integration.integration_details.note && (
                                  <div className="text-[9px] text-muted-foreground italic mt-1">
                                    {step.details.mazo_research_integration.integration_details.note}
                                  </div>
                                )}
                              </div>
                            )}
                            
                            {step.details.mazo_research_integration.summary && (
                              <div className="pt-2 border-t">
                                <div className="text-muted-foreground text-[10px] mb-1">Integration Status:</div>
                                <div className={`text-sm font-medium ${
                                  step.details.mazo_research_integration.summary.includes('was explicitly considered') 
                                    ? 'text-green-600 dark:text-green-400' 
                                    : 'text-orange-600 dark:text-orange-400'
                                }`}>
                                  {step.details.mazo_research_integration.summary}
                                </div>
                              </div>
                            )}
                            
                            {step.details.mazo_research_integration.decisions_with_mazo && step.details.mazo_research_integration.decisions_with_mazo.length > 0 && (
                              <div className="pt-2 border-t space-y-1">
                                <div className="text-muted-foreground text-[10px] mb-1">Per-Ticker Evaluation:</div>
                                {step.details.mazo_research_integration.decisions_with_mazo.map((decision: any, idx: number) => (
                                  <div key={idx} className="p-2 bg-white dark:bg-gray-800 rounded border text-[10px]">
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="font-mono font-semibold">{decision.ticker}:</span>
                                      <Badge 
                                        variant={decision.mazo_research_considered ? 'default' : 'secondary'}
                                        className="text-[9px] px-1.5 py-0"
                                      >
                                        {decision.mazo_research_considered ? '✅ Used in Decision' : '⚠️ Not Explicitly Referenced'}
                                      </Badge>
                                    </div>
                                    <div className="flex items-center gap-2 mt-1">
                                      {decision.has_initial_research && (
                                        <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                                          Initial Research Available
                                        </Badge>
                                      )}
                                      {decision.has_deep_dive && (
                                        <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                                          Deep Dive Available
                                        </Badge>
                                      )}
                                    </div>
                                    {decision.portfolio_manager_reasoning && (
                                      <div className="mt-2 pt-2 border-t">
                                        <div className="text-[9px] text-muted-foreground mb-1">Portfolio Manager Reasoning:</div>
                                        <div className="text-[9px] bg-gray-50 dark:bg-gray-900 p-1.5 rounded">
                                          {decision.portfolio_manager_reasoning}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                            
                            {step.details.mazo_research_integration.mazo_research_provided && 
                             !step.details.mazo_research_integration.summary?.includes('was explicitly considered') && (
                              <div className="pt-2 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-800">
                                <div className="flex items-start gap-2 text-[10px] text-yellow-700 dark:text-yellow-300">
                                  <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                  <div>
                                    <strong>Note:</strong> Mazo research was provided to the portfolio manager in the decision-making context, but may not have been explicitly referenced in the reasoning. The research was included in the LLM prompt for consideration.
                                  </div>
                                </div>
                              </div>
                            )}
                            
                            {!step.details.mazo_research_integration.mazo_research_provided && (
                              <div className="pt-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
                                <div className="flex items-start gap-2 text-[10px] text-blue-700 dark:text-blue-300">
                                  <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                  <div>
                                    <strong>Info:</strong> In this workflow mode, Mazo research is not provided to the portfolio manager before the decision. Use "Full" or "Pre-Research" mode to include Mazo research in portfolio manager evaluation.
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      
                      {/* Show detailed breakdown */}
                      {step.details && step.details.detailed_breakdown && (
                        <div className="text-xs bg-purple-50 dark:bg-purple-900/20 p-2 rounded border">
                          <div className="font-semibold mb-1">Detailed Breakdown:</div>
                          <pre className="overflow-x-auto text-[10px] max-h-60 overflow-y-auto">
                            {JSON.stringify(step.details.detailed_breakdown, null, 2)}
                          </pre>
                        </div>
                      )}
                      
                      {/* Render specific detail sections - with error boundaries */}
                      {(() => {
                        try {
                          return (
                            <>
                              {step.dataRetrievals && renderDataRetrievals(step.dataRetrievals)}
                              {step.agentExecutions && renderAgentExecutions(step.agentExecutions)}
                              {step.mazoResearch && renderMazoResearch(step.mazoResearch)}
                              {step.tradeExecution && renderTradeExecution(step.tradeExecution)}
                              {step.apiCalls && renderAPICalls(step.apiCalls)}
                            </>
                          );
                        } catch (error) {
                          console.error('Error rendering step details:', error, step);
                          return (
                            <div className="text-xs text-red-500 p-2 bg-red-50 dark:bg-red-900/20 rounded">
                              Error rendering details: {error instanceof Error ? error.message : String(error)}
                            </div>
                          );
                        }
                      })()}
                      
                      {/* Show full details JSON if no specific sections */}
                      {step.details && !step.dataRetrievals?.length && !step.agentExecutions?.length && !step.mazoResearch && !step.tradeExecution && !step.apiCalls?.length && (
                        <div className="text-xs">
                          <div className="font-semibold mb-1">Full Details:</div>
                          <pre className="bg-gray-100 dark:bg-gray-800 p-2 rounded overflow-x-auto max-h-96 overflow-y-auto text-[10px]">
                            {JSON.stringify(step.details, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              
              {steps.length === 0 && (
                <div className="text-sm text-muted-foreground text-center py-8">
                  Configure and run to see detailed workflow progress
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
                      {result.signal && result.confidence !== undefined && (
                        <Badge variant={result.signal === 'BULLISH' ? 'default' : 'destructive'}>
                          {result.signal} ({result.confidence}%)
                        </Badge>
                      )}
                      {!result.signal && (
                        <Badge variant="secondary">Research Only</Badge>
                      )}
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
                        </div>
                      </div>
                    )}

                    {result.research_report && (
                      <div className="pt-2 border-t">
                        <h4 className="text-sm font-medium mb-2">Research Report (Full):</h4>
                        <div className="text-xs p-3 bg-gray-50 dark:bg-gray-900 rounded border max-h-[500px] overflow-y-auto whitespace-pre-wrap">
                          {result.research_report}
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

                    {result.trade && (
                      <div className="pt-2 border-t">
                        <h4 className="text-sm font-medium mb-2">Trade:</h4>
                        <div className="text-xs space-y-1">
                          <div>Action: {result.trade.action.toUpperCase()}</div>
                          <div>Quantity: {result.trade.quantity}</div>
                          <div>Status: {result.trade.executed ? 'Executed' : 'Not Executed'}</div>
                          {result.trade.error && (
                            <div className="text-red-500">Error: {result.trade.error}</div>
                          )}
                        </div>
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
