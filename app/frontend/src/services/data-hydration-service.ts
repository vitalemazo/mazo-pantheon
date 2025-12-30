/**
 * Unified Data Hydration Service
 * 
 * This service implements a Stale-While-Revalidate (SWR) pattern with persistence:
 * 1. On app startup, load from localStorage first (instant)
 * 2. Then fetch fresh data from API in background
 * 3. All components share the same global state
 * 4. Tab switches NEVER reset state - it's all persisted
 * 
 * The user should NEVER see loading spinners for cached data.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { API_BASE_URL } from '@/lib/api-config';
import type { 
  AgentActivityEntry, 
  WorkflowProgress, 
  ConsoleLogEntry,
  AgentSignal,
} from '@/types/ai-transparency';

// ==================== TYPES ====================

export interface Position {
  ticker: string;
  side: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  market_value: number;
}

export interface ScheduledTask {
  id: string;
  name: string;
  next_run: string | null;
  trigger: string;
}

export interface PerformanceData {
  equity: number;
  cash: number;
  buying_power: number;
  positions_count: number;
  total_unrealized_pnl: number;
  positions: Position[];
}

export interface SchedulerStatus {
  is_running: boolean;
  scheduled_tasks: ScheduledTask[];
  task_history: any[];
}

export interface TradeHistoryItem {
  id: number;
  ticker: string;
  action: string;
  quantity: number;
  entry_price: number | null;
  exit_price: number | null;
  realized_pnl: number | null;
  return_pct: number | null;
  status: string;
  entry_time: string | null;
  context?: any;
}

export interface AgentPerformance {
  name: string;
  type: string | null;
  accuracy_rate: number | null;
  total_signals: number;
  correct_predictions: number;
  incorrect_predictions: number;
  avg_return_when_followed: number | null;
  best_call: { ticker: string; return: number } | null;
  worst_call: { ticker: string; return: number } | null;
}

export interface PerformanceMetrics {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number | null;
  total_pnl: number;
  avg_return_pct: number | null;
}

export interface WatchlistItem {
  id: number;
  ticker: string;
  strategy: string | null;
  status: string;
  entry_target: number | null;
}

export interface AutomatedTradingStatus {
  is_running: boolean;
  last_run: string | null;
  total_runs: number;
  last_result: any | null;
}

export interface PortfolioHealthData {
  success: boolean;
  portfolio: any;
  mazo_analysis: string;
  recommendations: string[];
  health_grade: string;
  timestamp: string;
}

export interface WorkflowResult {
  id: string;
  timestamp: Date | string;
  tickers: string[];
  mode: string;
  agent_signals?: Array<{
    agent: string;
    signal: string;
    confidence: number;
    reasoning?: string;
  }>;
  agentSignals?: Array<{
    agent: string;
    signal: string;
    confidence: number;
    reasoning?: string;
  }>;
  mazoResearch?: string;
  pmDecision?: {
    action: string;
    ticker: string;
    quantity: number;
    reasoning: string;
  };
  tradeExecuted?: {
    orderId: string;
    action: string;
    quantity: number;
    price: number;
  };
  success: boolean;
  error?: string;
}

export interface AIActivity {
  id: string;
  type: 'scan' | 'research' | 'analyze' | 'decide' | 'execute' | 'monitor';
  message: string;
  timestamp: Date | string;
  ticker?: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  details?: any;
}

export interface QuickAnalysisResult {
  ticker: string;
  signal: string;
  confidence?: number;
  reasoning?: string;
  agent_signals?: Array<{
    agent_name: string;
    signal: string;
    confidence?: number;
  }>;
  timestamp: string;
}

// ==================== STORE ====================

interface DataStore {
  // Core Data
  performance: PerformanceData | null;
  scheduler: SchedulerStatus | null;
  trades: TradeHistoryItem[];
  agents: AgentPerformance[];
  metrics: PerformanceMetrics | null;
  watchlist: WatchlistItem[];
  automatedStatus: AutomatedTradingStatus | null;
  portfolioHealth: PortfolioHealthData | null;
  
  // Workflow Data
  latestWorkflow: WorkflowResult | null;
  recentWorkflows: WorkflowResult[];
  
  // AI Hedge Fund State (persisted)
  isAutonomousEnabled: boolean;
  aiActivities: AIActivity[];
  tradingConfig: {
    budgetPercent: number;
    riskLevel: 'conservative' | 'balanced' | 'aggressive';
    maxPositions: number;
    stopLossPercent: number;
  };
  quickAnalysisResult: QuickAnalysisResult | null;
  quickAnalysisTicker: string;

  // Metadata
  lastUpdated: Record<string, number>; // timestamp in ms
  isInitialized: boolean;
  isRefreshing: boolean;
  errors: Record<string, string | null>;
  
  // Global loading states - visible across all tabs
  activeOperations: Record<string, {
    type: string;
    message: string;
    progress?: number;
    startedAt: number;
  }>;

  // AI Transparency State (for sidebars)
  agentActivityLog: AgentActivityEntry[];
  consoleLogs: ConsoleLogEntry[];
  agentStatuses: Record<string, 'pending' | 'running' | 'complete' | 'error'>;
  selectedAgentId: string | null;
  liveWorkflowProgress: WorkflowProgress | null;

  // Actions
  setPerformance: (data: PerformanceData) => void;
  setScheduler: (data: SchedulerStatus) => void;
  setTrades: (data: TradeHistoryItem[]) => void;
  setAgents: (data: AgentPerformance[]) => void;
  setMetrics: (data: PerformanceMetrics) => void;
  setWatchlist: (data: WatchlistItem[]) => void;
  setAutomatedStatus: (data: AutomatedTradingStatus) => void;
  setPortfolioHealth: (data: PortfolioHealthData) => void;
  setLatestWorkflow: (data: WorkflowResult) => void;
  setError: (key: string, error: string | null) => void;
  setRefreshing: (value: boolean) => void;
  setInitialized: (value: boolean) => void;
  
  // AI Hedge Fund Actions
  setAutonomousEnabled: (enabled: boolean) => void;
  addAIActivity: (activity: Omit<AIActivity, 'id' | 'timestamp'>) => void;
  setTradingConfig: (config: Partial<DataStore['tradingConfig']>) => void;
  setQuickAnalysisResult: (result: QuickAnalysisResult | null) => void;
  setQuickAnalysisTicker: (ticker: string) => void;
  
  // Operation tracking
  startOperation: (id: string, type: string, message: string) => void;
  updateOperation: (id: string, updates: { message?: string; progress?: number }) => void;
  endOperation: (id: string) => void;
  
  // AI Transparency Actions
  addAgentActivity: (entry: Omit<AgentActivityEntry, 'id'>) => void;
  clearAgentActivityLog: () => void;
  togglePinActivity: (id: string) => void;
  addConsoleLog: (entry: Omit<ConsoleLogEntry, 'id'>) => void;
  clearConsoleLogs: () => void;
  setAgentStatus: (agentId: string, status: 'pending' | 'running' | 'complete' | 'error') => void;
  resetAgentStatuses: () => void;
  setSelectedAgentId: (id: string | null) => void;
  setLiveWorkflowProgress: (progress: WorkflowProgress | null) => void;
  updateWorkflowProgress: (updates: Partial<WorkflowProgress>) => void;
}

export const useDataStore = create<DataStore>()(
  persist(
    (set, get) => ({
      // Initial empty state
      performance: null,
      scheduler: null,
      trades: [],
      agents: [],
      metrics: null,
      watchlist: [],
      automatedStatus: null,
      portfolioHealth: null,
      latestWorkflow: null,
      recentWorkflows: [],
      
      // AI Hedge Fund defaults
      isAutonomousEnabled: false,
      aiActivities: [],
      tradingConfig: {
        budgetPercent: 25,
        riskLevel: 'balanced',
        maxPositions: 5,
        stopLossPercent: 5,
      },
      quickAnalysisResult: null,
      quickAnalysisTicker: '',

      lastUpdated: {},
      isInitialized: false,
      isRefreshing: false,
      errors: {},
      activeOperations: {},
      
      // AI Transparency initial state
      agentActivityLog: [],
      consoleLogs: [],
      agentStatuses: {},
      selectedAgentId: null,
      liveWorkflowProgress: null,

      // Setters that update lastUpdated timestamp
      setPerformance: (data) => set((state) => ({
        performance: data,
        lastUpdated: { ...state.lastUpdated, performance: Date.now() }
      })),
      setScheduler: (data) => set((state) => ({
        scheduler: data,
        lastUpdated: { ...state.lastUpdated, scheduler: Date.now() }
      })),
      setTrades: (data) => set((state) => ({
        trades: data,
        lastUpdated: { ...state.lastUpdated, trades: Date.now() }
      })),
      setAgents: (data) => set((state) => ({
        agents: data,
        lastUpdated: { ...state.lastUpdated, agents: Date.now() }
      })),
      setMetrics: (data) => set((state) => ({
        metrics: data,
        lastUpdated: { ...state.lastUpdated, metrics: Date.now() }
      })),
      setWatchlist: (data) => set((state) => ({
        watchlist: data,
        lastUpdated: { ...state.lastUpdated, watchlist: Date.now() }
      })),
      setAutomatedStatus: (data) => set((state) => ({
        automatedStatus: data,
        lastUpdated: { ...state.lastUpdated, automatedStatus: Date.now() }
      })),
      setPortfolioHealth: (data) => set((state) => ({
        portfolioHealth: data,
        lastUpdated: { ...state.lastUpdated, portfolioHealth: Date.now() }
      })),
      setLatestWorkflow: (data) => set((state) => ({
        latestWorkflow: data,
        recentWorkflows: [data, ...state.recentWorkflows.slice(0, 9)],
        lastUpdated: { ...state.lastUpdated, latestWorkflow: Date.now() }
      })),
      setError: (key, error) => set((state) => ({
        errors: { ...state.errors, [key]: error }
      })),
      setRefreshing: (value) => set({ isRefreshing: value }),
      setInitialized: (value) => set({ isInitialized: value }),
      
      // AI Hedge Fund Actions
      setAutonomousEnabled: (enabled) => set({ isAutonomousEnabled: enabled }),
      
      addAIActivity: (activity) => set((state) => {
        const newActivity: AIActivity = {
          ...activity,
          id: `activity_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          timestamp: new Date().toISOString(),
        };
        // Keep last 50 activities
        return {
          aiActivities: [newActivity, ...state.aiActivities.slice(0, 49)],
        };
      }),
      
      setTradingConfig: (config) => set((state) => ({
        tradingConfig: { ...state.tradingConfig, ...config },
      })),
      
      setQuickAnalysisResult: (result) => set({ quickAnalysisResult: result }),
      setQuickAnalysisTicker: (ticker) => set({ quickAnalysisTicker: ticker }),
      
      // Operation tracking for global loading states
      startOperation: (id, type, message) => set((state) => ({
        activeOperations: {
          ...state.activeOperations,
          [id]: { type, message, startedAt: Date.now() },
        },
      })),
      
      updateOperation: (id, updates) => set((state) => {
        const op = state.activeOperations[id];
        if (!op) return state;
        return {
          activeOperations: {
            ...state.activeOperations,
            [id]: { ...op, ...updates },
          },
        };
      }),
      
      endOperation: (id) => set((state) => {
        const { [id]: removed, ...rest } = state.activeOperations;
        return { activeOperations: rest };
      }),
      
      // AI Transparency Actions
      addAgentActivity: (entry) => set((state) => {
        const newEntry: AgentActivityEntry = {
          ...entry,
          id: `activity_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        };
        // Keep last 200 activities
        return {
          agentActivityLog: [newEntry, ...state.agentActivityLog.slice(0, 199)],
        };
      }),
      
      clearAgentActivityLog: () => set({ agentActivityLog: [] }),
      
      togglePinActivity: (id) => set((state) => ({
        agentActivityLog: state.agentActivityLog.map((a) =>
          a.id === id ? { ...a, isPinned: !a.isPinned } : a
        ),
      })),
      
      addConsoleLog: (entry) => set((state) => {
        const newEntry: ConsoleLogEntry = {
          ...entry,
          id: `log_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        };
        // Keep last 500 logs
        return {
          consoleLogs: [...state.consoleLogs.slice(-499), newEntry],
        };
      }),
      
      clearConsoleLogs: () => set({ consoleLogs: [] }),
      
      setAgentStatus: (agentId, status) => set((state) => ({
        agentStatuses: { ...state.agentStatuses, [agentId]: status },
      })),
      
      resetAgentStatuses: () => set({ agentStatuses: {} }),
      
      setSelectedAgentId: (id) => set({ selectedAgentId: id }),
      
      setLiveWorkflowProgress: (progress) => set({ liveWorkflowProgress: progress }),
      
      updateWorkflowProgress: (updates) => set((state) => ({
        liveWorkflowProgress: state.liveWorkflowProgress
          ? { ...state.liveWorkflowProgress, ...updates }
          : null,
      })),
    }),
    {
      name: 'mazo-data-store', // localStorage key
      storage: createJSONStorage(() => localStorage),
      // Only persist these fields
      partialize: (state) => ({
        isAutonomousEnabled: state.isAutonomousEnabled,
        aiActivities: state.aiActivities.slice(0, 20), // Keep last 20 in storage
        tradingConfig: state.tradingConfig,
        quickAnalysisResult: state.quickAnalysisResult,
        quickAnalysisTicker: state.quickAnalysisTicker,
        performance: state.performance,
        scheduler: state.scheduler,
        trades: state.trades.slice(0, 20),
        agents: state.agents,
        metrics: state.metrics,
        lastUpdated: state.lastUpdated,
        // AI Transparency (persist last 50 activities)
        agentActivityLog: state.agentActivityLog.slice(0, 50),
      }),
    }
  )
);

// ==================== FETCH FUNCTIONS ====================

async function fetchWithTimeout(url: string, timeout = 10000): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
}

async function safeFetch<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}${url}`);
    if (!response.ok) return fallback;
    return await response.json();
  } catch {
    return fallback;
  }
}

// ==================== HYDRATION SERVICE ====================

class DataHydrationService {
  private refreshInterval: ReturnType<typeof setInterval> | null = null;
  private isHydrating = false;
  private lastHydrationTime = 0;

  /**
   * Initial hydration - fetch ALL data on app startup
   * Skips if data was fetched recently (within 30 seconds)
   */
  async hydrateAll(force = false): Promise<void> {
    if (this.isHydrating) return;
    
    // Skip if recently hydrated (unless forced)
    const now = Date.now();
    if (!force && now - this.lastHydrationTime < 30000) {
      console.log('[DataHydration] Skipping - recently hydrated');
      return;
    }

    this.isHydrating = true;
    this.lastHydrationTime = now;

    const store = useDataStore.getState();
    store.setRefreshing(true);

    console.log('[DataHydration] Starting hydration...');

    try {
      // Fetch all data in parallel for speed
      const [
        perfData,
        schedulerData,
        tradesData,
        agentsData,
        metricsData,
        watchlistData,
        automatedData,
      ] = await Promise.all([
        safeFetch<any>('/trading/performance', null),
        safeFetch<any>('/trading/scheduler/status', null),
        safeFetch<any>('/history/trades?limit=50', { trades: [] }),
        safeFetch<any>('/history/agents', { agents: [] }),
        safeFetch<any>('/history/performance', { summary: null }),
        safeFetch<any>('/trading/watchlist', { items: [] }),
        safeFetch<any>('/trading/automated/status', null),
      ]);

      // Update store with fetched data
      if (perfData) store.setPerformance(perfData);
      if (schedulerData) {
        store.setScheduler(schedulerData);
        // Sync autonomous state from backend
        if (schedulerData.is_running !== undefined) {
          store.setAutonomousEnabled(schedulerData.is_running);
        }
      }
      if (tradesData?.trades) store.setTrades(tradesData.trades);
      if (agentsData?.agents) store.setAgents(agentsData.agents);
      if (metricsData?.summary) store.setMetrics(metricsData.summary);
      if (watchlistData?.items) store.setWatchlist(watchlistData.items);
      if (automatedData) store.setAutomatedStatus(automatedData);

      store.setInitialized(true);
      console.log('[DataHydration] Hydration complete');

    } catch (error) {
      console.error('[DataHydration] Hydration failed:', error);
    } finally {
      store.setRefreshing(false);
      this.isHydrating = false;
    }
  }

  /**
   * Background refresh - updates data without showing loading states
   * Silent failure - never disrupts the UI
   */
  async backgroundRefresh(): Promise<void> {
    const store = useDataStore.getState();

    try {
      const [perfData, schedulerData, automatedData] = await Promise.all([
        safeFetch<any>('/trading/performance', null),
        safeFetch<any>('/trading/scheduler/status', null),
        safeFetch<any>('/trading/automated/status', null),
      ]);

      // Only update if we got data - never clear existing data
      if (perfData) store.setPerformance(perfData);
      if (schedulerData) {
        store.setScheduler(schedulerData);
        if (schedulerData.is_running !== undefined) {
          store.setAutonomousEnabled(schedulerData.is_running);
        }
      }
      if (automatedData) store.setAutomatedStatus(automatedData);

    } catch (error) {
      // Silent fail for background refresh
      console.warn('[DataHydration] Background refresh failed:', error);
    }
  }

  /**
   * Refresh specific data types on demand
   */
  async refreshTrades(): Promise<void> {
    const store = useDataStore.getState();
    const data = await safeFetch<any>('/history/trades?limit=50', null);
    if (data?.trades) store.setTrades(data.trades);
  }

  async refreshAgents(): Promise<void> {
    const store = useDataStore.getState();
    const data = await safeFetch<any>('/history/agents', null);
    if (data?.agents) store.setAgents(data.agents);
  }

  async refreshPortfolioHealth(): Promise<void> {
    const store = useDataStore.getState();
    try {
      const response = await fetch(`${API_BASE_URL}/unified-workflow/portfolio-health-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (response.ok) {
        const data = await response.json();
        store.setPortfolioHealth(data);
      }
    } catch (error) {
      console.error('[DataHydration] Portfolio health refresh failed:', error);
    }
  }

  /**
   * Record a completed workflow result
   */
  async recordWorkflowComplete(result: WorkflowResult): Promise<void> {
    const store = useDataStore.getState();
    
    // Store the workflow result
    store.setLatestWorkflow(result);
    
    // Add activity
    store.addAIActivity({
      type: 'analyze',
      message: `Analysis complete for ${result.tickers?.join(', ') || 'unknown'}`,
      status: 'complete',
      details: result,
    });
    
    // If a trade was executed, refresh positions and trade history
    if (result.tradeExecuted) {
      console.log('[DataHydration] Trade executed, refreshing...');
      await Promise.all([
        this.refreshTrades(),
        this.refreshAgents(),
        this.backgroundRefresh(),
      ]);
    }
  }

  /**
   * Start background refresh interval
   */
  startBackgroundRefresh(intervalMs = 15000): void {
    if (this.refreshInterval) return;
    
    console.log(`[DataHydration] Starting background refresh every ${intervalMs/1000}s`);
    
    this.refreshInterval = setInterval(() => {
      this.backgroundRefresh();
    }, intervalMs);
  }

  /**
   * Stop background refresh
   */
  stopBackgroundRefresh(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
    }
  }
}

// Singleton instance
export const dataHydrationService = new DataHydrationService();

// ==================== REACT HOOKS ====================

/**
 * Hook to get data with automatic initialization
 * Always returns cached data - never shows loading for cached data
 */
export function useHydratedData() {
  const store = useDataStore();

  return {
    // Core Data
    performance: store.performance,
    scheduler: store.scheduler,
    trades: store.trades,
    agents: store.agents,
    metrics: store.metrics,
    watchlist: store.watchlist,
    automatedStatus: store.automatedStatus,
    portfolioHealth: store.portfolioHealth,
    latestWorkflow: store.latestWorkflow,
    recentWorkflows: store.recentWorkflows,
    
    // AI Hedge Fund State
    isAutonomousEnabled: store.isAutonomousEnabled,
    aiActivities: store.aiActivities,
    tradingConfig: store.tradingConfig,
    quickAnalysisResult: store.quickAnalysisResult,
    quickAnalysisTicker: store.quickAnalysisTicker,
    
    // Active operations (loading states)
    activeOperations: store.activeOperations,

    // Status
    isInitialized: store.isInitialized,
    isRefreshing: store.isRefreshing,
    lastUpdated: store.lastUpdated,

    // Actions
    refreshTrades: () => dataHydrationService.refreshTrades(),
    refreshAgents: () => dataHydrationService.refreshAgents(),
    refreshPortfolioHealth: () => dataHydrationService.refreshPortfolioHealth(),
    refreshAll: () => dataHydrationService.backgroundRefresh(),
    recordWorkflowComplete: (result: WorkflowResult) => dataHydrationService.recordWorkflowComplete(result),
    
    // AI Hedge Fund Actions
    setAutonomousEnabled: store.setAutonomousEnabled,
    addAIActivity: store.addAIActivity,
    setTradingConfig: store.setTradingConfig,
    setQuickAnalysisResult: store.setQuickAnalysisResult,
    setQuickAnalysisTicker: store.setQuickAnalysisTicker,
    
    // Operation tracking
    startOperation: store.startOperation,
    updateOperation: store.updateOperation,
    endOperation: store.endOperation,
    
    // AI Transparency State & Actions
    agentActivityLog: store.agentActivityLog,
    consoleLogs: store.consoleLogs,
    agentStatuses: store.agentStatuses,
    selectedAgentId: store.selectedAgentId,
    liveWorkflowProgress: store.liveWorkflowProgress,
    addAgentActivity: store.addAgentActivity,
    clearAgentActivityLog: store.clearAgentActivityLog,
    togglePinActivity: store.togglePinActivity,
    addConsoleLog: store.addConsoleLog,
    clearConsoleLogs: store.clearConsoleLogs,
    setAgentStatus: store.setAgentStatus,
    resetAgentStatuses: store.resetAgentStatuses,
    setSelectedAgentId: store.setSelectedAgentId,
    setLiveWorkflowProgress: store.setLiveWorkflowProgress,
    updateWorkflowProgress: store.updateWorkflowProgress,
  };
}

// ==================== GLOBAL INITIALIZATION ====================

/**
 * Initialize data hydration on app startup
 * Call this once in your app entry point
 */
export async function initializeDataHydration() {
  // Start background refresh
  dataHydrationService.startBackgroundRefresh(15000);
  
  // Hydrate all data
  await dataHydrationService.hydrateAll();
}
