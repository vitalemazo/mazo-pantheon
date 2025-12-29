/**
 * Workflow Context
 * 
 * Persists workflow state across tab switches so users can:
 * - Navigate away from the workflow tab
 * - Return to see the current progress
 * - View results even after workflow completes
 */

import { createContext, ReactNode, useContext, useRef, useState, useCallback, useEffect } from 'react';
import { UnifiedWorkflowResult } from '@/services/unified-workflow-api';

// Step types - matching DetailedWorkflowView
export interface DetailedStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  details?: any;
  startTime?: number;
  endTime?: number;
  expanded?: boolean;
  subSteps?: DetailedStep[];
  apiCalls?: APICall[];
  agentExecutions?: AgentExecution[];
  dataRetrievals?: DataRetrieval[];
  mazoResearch?: MazoResearch;
  tradeExecution?: TradeExecution;
}

export interface APICall {
  url: string;
  method: string;
  statusCode?: number;
  responseTimeMs?: number;
  cacheHit: boolean;
  error?: string;
  timestamp: string;
}

export interface AgentExecution {
  agentName: string;
  ticker: string;
  signal?: string;
  confidence?: number;
  reasoning?: string;
  executionTimeMs?: number;
  apiCalls?: APICall[];
  timestamp: string;
}

export interface DataRetrieval {
  dataType: string;
  ticker: string;
  cacheHit: boolean;
  recordsRetrieved: number;
  details?: any;
  apiCalls?: APICall[];
  timestamp: string;
}

export interface MazoResearch {
  ticker?: string;
  query?: string;
  depth?: string;
  method?: string;
  steps?: any[];
  response?: string;
  answer?: string;
  answerPreview?: string;
  executionTimeMs?: number;
  success?: boolean;
  confidence?: number;
  answerLength?: number;
  tasksCompleted?: string[];
  dataSources?: string[];
  error?: string;
  apiCalls?: APICall[];
  timestamp?: string;
}

export interface TradeExecution {
  ticker: string;
  action: string;
  quantity: number;
  executed: boolean;
  orderId?: string;
  filledPrice?: number;
  error?: string;
  apiCalls?: APICall[];
  timestamp: string;
}

// Workflow configuration
export interface WorkflowConfig {
  tickers: string;
  mode: string;
  depth: string;
  executeTrades: boolean;
  dryRun: boolean;
  forceRefresh: boolean;
}

interface WorkflowContextType {
  // State
  isRunning: boolean;
  steps: DetailedStep[];
  results: UnifiedWorkflowResult[];
  error: string | null;
  config: WorkflowConfig;
  
  // State setters
  setIsRunning: (running: boolean) => void;
  setSteps: React.Dispatch<React.SetStateAction<DetailedStep[]>>;
  setResults: (results: UnifiedWorkflowResult[]) => void;
  setError: (error: string | null) => void;
  setConfig: React.Dispatch<React.SetStateAction<WorkflowConfig>>;
  
  // AbortController ref for cancellation
  abortControllerRef: React.MutableRefObject<AbortController | null>;
  
  // Helper functions
  updateStep: (stepId: string, status: DetailedStep['status'], details?: any) => void;
  resetWorkflow: () => void;
  toggleStepExpanded: (stepId: string) => void;
  
  // Workflow run metadata
  workflowStartTime: number | null;
  setWorkflowStartTime: (time: number | null) => void;
}

const WorkflowContext = createContext<WorkflowContextType | null>(null);

export function useWorkflowContext() {
  const context = useContext(WorkflowContext);
  if (!context) {
    throw new Error('useWorkflowContext must be used within a WorkflowProvider');
  }
  return context;
}

interface WorkflowProviderProps {
  children: ReactNode;
}

const DEFAULT_CONFIG: WorkflowConfig = {
  tickers: 'AAPL',
  mode: 'signal',
  depth: 'standard',
  executeTrades: false,
  dryRun: false,
  forceRefresh: false,
};

export function WorkflowProvider({ children }: WorkflowProviderProps) {
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [steps, setSteps] = useState<DetailedStep[]>([]);
  const [results, setResults] = useState<UnifiedWorkflowResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<WorkflowConfig>(DEFAULT_CONFIG);
  const [workflowStartTime, setWorkflowStartTime] = useState<number | null>(null);
  
  const abortControllerRef = useRef<AbortController | null>(null);

  // Initialize steps based on mode
  useEffect(() => {
    // Only initialize if not running and no results yet
    if (!isRunning && results.length === 0 && steps.length === 0) {
      initializeSteps(config.mode, config.executeTrades, config.dryRun);
    }
  }, [config.mode, config.executeTrades, config.dryRun]);

  const initializeSteps = useCallback((mode: string, executeTrades: boolean, dryRun: boolean) => {
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
  }, []);

  const toggleStepExpanded = useCallback((stepId: string) => {
    setSteps(prev => prev.map(step => 
      step.id === stepId 
        ? { ...step, expanded: !step.expanded }
        : step
    ));
  }, []);

  const updateStep = useCallback((stepId: string, status: DetailedStep['status'], details?: any) => {
    console.log('[WorkflowContext] updateStep:', { stepId, status, hasDetails: !!details });
    setSteps(prev => {
      return prev.map(step => {
        if (step.id === stepId) {
          const updated: DetailedStep = {
            ...step,
            status,
            details,
            ...(status === 'running' && !step.startTime ? { startTime: Date.now() } : {}),
            ...(status === 'completed' || status === 'error' ? { endTime: Date.now() } : {}),
          };

          // Parse detailed information from details
          if (details) {
            try {
              const parsed = typeof details === 'string' ? JSON.parse(details) : details;
              
              // Update API calls
              if (parsed.api_calls && Array.isArray(parsed.api_calls)) {
                updated.apiCalls = parsed.api_calls;
              } else if (parsed.apiCalls && Array.isArray(parsed.apiCalls)) {
                updated.apiCalls = parsed.apiCalls;
              }
              
              // Update agent executions
              if (parsed.agent_executions && Array.isArray(parsed.agent_executions)) {
                updated.agentExecutions = parsed.agent_executions.map((exec: any) => ({
                  ...exec,
                  reasoning: exec.reasoning || null,
                  agentName: exec.agent_name || exec.agentName || 'Unknown',
                  ticker: exec.ticker || 'N/A',
                }));
              } else if (parsed.agentExecutions && Array.isArray(parsed.agentExecutions)) {
                updated.agentExecutions = parsed.agentExecutions.map((exec: any) => ({
                  ...exec,
                  reasoning: exec.reasoning || null,
                  agentName: exec.agent_name || exec.agentName || 'Unknown',
                  ticker: exec.ticker || 'N/A',
                }));
              }
              
              // Update data retrievals
              if (parsed.data_retrievals && Array.isArray(parsed.data_retrievals)) {
                updated.dataRetrievals = parsed.data_retrievals;
              } else if (parsed.dataRetrievals && Array.isArray(parsed.dataRetrievals)) {
                updated.dataRetrievals = parsed.dataRetrievals;
              }
              
              // Update Mazo research
              if (parsed.mazo_research) {
                updated.mazoResearch = parsed.mazo_research;
              } else if (parsed.mazoResearch) {
                updated.mazoResearch = parsed.mazoResearch;
              } else if (parsed.mazo_research_active) {
                updated.mazoResearch = parsed.mazo_research_active;
              }
              
              // Update trade execution
              if (parsed.trade_execution) {
                updated.tradeExecution = parsed.trade_execution;
              } else if (parsed.tradeExecution) {
                updated.tradeExecution = parsed.tradeExecution;
              }
              
              // Store full parsed details for display
              updated.details = parsed;
            } catch (e) {
              console.error('Error parsing details:', e, details);
            }
          }

          return updated;
        }
        return step;
      });
    });
  }, []);

  const resetWorkflow = useCallback(() => {
    setIsRunning(false);
    setError(null);
    setResults([]);
    setWorkflowStartTime(null);
    
    // Re-initialize steps
    setSteps(prev => prev.map(step => ({
      ...step,
      status: 'pending' as const,
      startTime: undefined,
      endTime: undefined,
      expanded: false,
      apiCalls: [],
      agentExecutions: [],
      dataRetrievals: [],
      mazoResearch: undefined,
      tradeExecution: undefined,
      details: undefined,
    })));
  }, []);

  const value: WorkflowContextType = {
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
    workflowStartTime,
    setWorkflowStartTime,
  };

  return (
    <WorkflowContext.Provider value={value}>
      {children}
    </WorkflowContext.Provider>
  );
}
