/**
 * Unified Data Hydration Service v2
 * 
 * Implements a slice-based architecture where each UI experience has its own
 * data slice and hydration function. This allows:
 * - Independent refresh cycles per view
 * - Only hydrating what's needed
 * - Clear data ownership
 * 
 * Slices:
 * - controlTower: Autopilot, mission console, budget, cycle history
 * - workspace: Positions, trades, performance metrics, scheduler
 * - monitoring: Services, rate limits (uses SWR directly, minimal store)
 * - roundTable: Workflow history, pipeline events (uses SWR directly)
 * - intelligence: Agent activity, logs, live workflow progress
 * 
 * The store uses Stale-While-Revalidate (SWR) pattern with localStorage persistence.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { API_BASE_URL } from '@/lib/api-config';
import type { 
  AgentActivityEntry, 
  WorkflowProgress, 
  ConsoleLogEntry,
} from '@/types/ai-transparency';

// ==================== SHARED TYPES ====================

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
  has_data?: boolean;
  message?: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number | null;
  total_pnl: number;
  avg_return_pct: number | null;
  average_pnl?: number | null;
  average_return_pct?: number | null;
  profit_factor?: number | null;
  average_holding_hours?: number | null;
  biggest_winner?: { ticker: string; pnl: number; return_pct: number } | null;
  biggest_loser?: { ticker: string; pnl: number; return_pct: number } | null;
}

export interface WatchlistItem {
  id: number;
  ticker: string;
  strategy: string | null;
  status: string;
  entry_target: number | null;
}

export interface AutomatedTradingStatus {
  success: boolean;
  is_running: boolean;
  auto_trading_enabled: boolean;
  last_run: string | null;
  total_runs: number;
  last_result: any | null;
  error?: string;
  message?: string;
  requires_setup?: {
    alpaca?: boolean;
    missing_keys?: string[];
  };
  watchlist?: WatchlistItem[];
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
  workflow_id?: string;
  timestamp: Date | string;
  started_at?: string;
  tickers: string[];
  mode: string;
  status?: string;
  workflow_type?: string;
  trades_executed?: number;
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
  type: 'scan' | 'research' | 'analyze' | 'decide' | 'execute' | 'monitor' | 'workflow' | 'decision';
  message: string;
  timestamp: Date | string;
  ticker?: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  workflow_id?: string;
  details?: Record<string, any>;
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

export interface TradingConfig {
  budgetPercent: number;
  riskLevel: 'conservative' | 'balanced' | 'aggressive';
  maxPositions: number;
  stopLossPercent: number;
  takeProfitPercent: number;
}

// ==================== SLICE INTERFACES ====================

/** Control Tower slice - Autopilot, mission console, budget, AI team */
export interface ControlTowerSlice {
  isAutonomousEnabled: boolean;
  automatedStatus: AutomatedTradingStatus | null;
  tradingConfig: TradingConfig;
  recentWorkflows: WorkflowResult[];
  aiActivities: AIActivity[];
  quickAnalysisResult: QuickAnalysisResult | null;
  quickAnalysisTicker: string;
}

/** Trading Workspace slice - Positions, performance, scheduler */
export interface WorkspaceSlice {
  performance: PerformanceData | null;
  scheduler: SchedulerStatus | null;
  metrics: PerformanceMetrics | null;
  trades: TradeHistoryItem[];
  agents: AgentPerformance[];
  watchlist: WatchlistItem[];
  portfolioHealth: PortfolioHealthData | null;
}

/** Intelligence Panel slice - Activity log, console, workflow progress */
export interface IntelligenceSlice {
  agentActivityLog: AgentActivityEntry[];
  consoleLogs: ConsoleLogEntry[];
  agentStatuses: Record<string, 'pending' | 'running' | 'complete' | 'error'>;
  selectedAgentId: string | null;
  liveWorkflowProgress: WorkflowProgress | null;
}

/** Global metadata slice */
export interface MetadataSlice {
  lastUpdated: Record<string, number>;
  isInitialized: boolean;
  isRefreshing: boolean;
  errors: Record<string, string | null>;
  activeOperations: Record<string, {
    type: string;
    message: string;
    progress?: number;
    startedAt: number;
  }>;
}

// ==================== STORE INTERFACE ====================

interface DataStore extends ControlTowerSlice, WorkspaceSlice, IntelligenceSlice, MetadataSlice {
  // Legacy compat: latestWorkflow derived from recentWorkflows[0]
  latestWorkflow: WorkflowResult | null;

  // ========== Workspace Actions ==========
  setPerformance: (data: PerformanceData) => void;
  setScheduler: (data: SchedulerStatus) => void;
  setTrades: (data: TradeHistoryItem[]) => void;
  setAgents: (data: AgentPerformance[]) => void;
  setMetrics: (data: PerformanceMetrics) => void;
  setWatchlist: (data: WatchlistItem[]) => void;
  setPortfolioHealth: (data: PortfolioHealthData) => void;

  // ========== Control Tower Actions ==========
  setAutonomousEnabled: (enabled: boolean) => void;
  setAutomatedStatus: (data: AutomatedTradingStatus) => void;
  setTradingConfig: (config: Partial<TradingConfig>) => void;
  setLatestWorkflow: (data: WorkflowResult) => void;
  addAIActivity: (activity: Omit<AIActivity, 'id' | 'timestamp'>) => void;
  setQuickAnalysisResult: (result: QuickAnalysisResult | null) => void;
  setQuickAnalysisTicker: (ticker: string) => void;

  // ========== Intelligence Actions ==========
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

  // ========== Metadata Actions ==========
  setError: (key: string, error: string | null) => void;
  setRefreshing: (value: boolean) => void;
  setInitialized: (value: boolean) => void;
  startOperation: (id: string, type: string, message: string) => void;
  updateOperation: (id: string, updates: { message?: string; progress?: number }) => void;
  endOperation: (id: string) => void;
}

// ==================== STORE IMPLEMENTATION ====================

export const useDataStore = create<DataStore>()(
  persist(
    (set, get) => ({
      // ========== Control Tower Initial State ==========
      isAutonomousEnabled: false,
      automatedStatus: null,
      tradingConfig: {
        budgetPercent: 25,
        riskLevel: 'balanced',
        maxPositions: 5,
        stopLossPercent: 5,
        takeProfitPercent: 10,
      },
      recentWorkflows: [],
      aiActivities: [],
      quickAnalysisResult: null,
      quickAnalysisTicker: '',

      // ========== Workspace Initial State ==========
      performance: null,
      scheduler: null,
      metrics: null,
      trades: [],
      agents: [],
      watchlist: [],
      portfolioHealth: null,

      // ========== Intelligence Initial State ==========
      agentActivityLog: [],
      consoleLogs: [],
      agentStatuses: {},
      selectedAgentId: null,
      liveWorkflowProgress: null,

      // ========== Metadata Initial State ==========
      lastUpdated: {},
      isInitialized: false,
      isRefreshing: false,
      errors: {},
      activeOperations: {},

      // Legacy compat
      get latestWorkflow() {
        return get().recentWorkflows[0] || null;
      },

      // ========== Workspace Actions ==========
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

      setPortfolioHealth: (data) => set((state) => ({
        portfolioHealth: data,
        lastUpdated: { ...state.lastUpdated, portfolioHealth: Date.now() }
      })),

      // ========== Control Tower Actions ==========
      setAutonomousEnabled: (enabled) => set({ isAutonomousEnabled: enabled }),

      setAutomatedStatus: (data) => set((state) => ({
        automatedStatus: data,
        lastUpdated: { ...state.lastUpdated, automatedStatus: Date.now() }
      })),

      setTradingConfig: (config) => set((state) => ({
        tradingConfig: { ...state.tradingConfig, ...config },
      })),

      setLatestWorkflow: (data) => set((state) => ({
        recentWorkflows: [data, ...state.recentWorkflows.slice(0, 9)],
        lastUpdated: { ...state.lastUpdated, recentWorkflows: Date.now() }
      })),

      addAIActivity: (activity) => set((state) => {
        const newActivity: AIActivity = {
          ...activity,
          id: `activity_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          timestamp: new Date().toISOString(),
        };
        return {
          aiActivities: [newActivity, ...state.aiActivities.slice(0, 49)],
        };
      }),

      setQuickAnalysisResult: (result) => set({ quickAnalysisResult: result }),
      setQuickAnalysisTicker: (ticker) => set({ quickAnalysisTicker: ticker }),

      // ========== Intelligence Actions ==========
      addAgentActivity: (entry) => set((state) => {
        const newEntry: AgentActivityEntry = {
          ...entry,
          id: `activity_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        };
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

      updateWorkflowProgress: (updates) => set((state) => {
        if (!state.liveWorkflowProgress) return { liveWorkflowProgress: null };
        const current = state.liveWorkflowProgress;
        return {
          liveWorkflowProgress: {
            ...current,
            ...updates,
            signals: { ...(current.signals || {}), ...(updates.signals || {}) },
            agentStatuses: { ...(current.agentStatuses || {}), ...(updates.agentStatuses || {}) },
          },
        };
      }),

      // ========== Metadata Actions ==========
      setError: (key, error) => set((state) => ({
        errors: { ...state.errors, [key]: error }
      })),

      setRefreshing: (value) => set({ isRefreshing: value }),
      setInitialized: (value) => set({ isInitialized: value }),

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
    }),
    {
      name: 'mazo-data-store-v2',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // Control Tower (persist)
        isAutonomousEnabled: state.isAutonomousEnabled,
        tradingConfig: state.tradingConfig,
        aiActivities: state.aiActivities.slice(0, 20),
        quickAnalysisResult: state.quickAnalysisResult,
        quickAnalysisTicker: state.quickAnalysisTicker,
        // Workspace (persist for instant load)
        performance: state.performance,
        scheduler: state.scheduler,
        metrics: state.metrics,
        trades: state.trades.slice(0, 20),
        agents: state.agents,
        // Metadata
        lastUpdated: state.lastUpdated,
        // Intelligence (persist recent activity)
        agentActivityLog: state.agentActivityLog.slice(0, 50),
      }),
    }
  )
);

// ==================== FETCH UTILITIES ====================

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
   * Hydrate Control Tower slice
   * - Autopilot status, scheduler status (for is_running), automated trading status
   */
  async hydrateControlTower(): Promise<void> {
    const store = useDataStore.getState();
    console.log('[DataHydration] Hydrating Control Tower slice...');

    const [schedulerData, automatedData] = await Promise.all([
      safeFetch<any>('/trading/scheduler/status', null),
      safeFetch<any>('/trading/automated/status', null),
    ]);

    if (schedulerData) {
      store.setScheduler(schedulerData);
      if (schedulerData.is_running !== undefined) {
        store.setAutonomousEnabled(schedulerData.is_running);
      }
    }
    if (automatedData) store.setAutomatedStatus(automatedData);
  }

  /**
   * Hydrate Workspace slice
   * - Performance, metrics, trades, agents, watchlist
   */
  async hydrateWorkspace(): Promise<void> {
    const store = useDataStore.getState();
    console.log('[DataHydration] Hydrating Workspace slice...');

    const [perfData, metricsData, tradesData, agentsData, watchlistData] = await Promise.all([
      safeFetch<any>('/trading/performance', null),
      safeFetch<any>('/history/performance', { summary: null }),
      safeFetch<any>('/history/trades?limit=50', { trades: [] }),
      safeFetch<any>('/history/agents', { agents: [] }),
      safeFetch<any>('/trading/watchlist', { items: [] }),
    ]);

    if (perfData) store.setPerformance(perfData);
    if (metricsData?.summary) store.setMetrics(metricsData.summary);
    if (tradesData?.trades) store.setTrades(tradesData.trades);
    if (agentsData?.agents) store.setAgents(agentsData.agents);
    if (watchlistData?.items) store.setWatchlist(watchlistData.items);
  }

  /**
   * Hydrate both Control Tower and Workspace (full app hydration)
   */
  async hydrateAll(force = false): Promise<void> {
    if (this.isHydrating) return;

    const now = Date.now();
    if (!force && now - this.lastHydrationTime < 30000) {
      console.log('[DataHydration] Skipping - recently hydrated');
      return;
    }

    this.isHydrating = true;
    this.lastHydrationTime = now;

    const store = useDataStore.getState();
    store.setRefreshing(true);

    console.log('[DataHydration] Starting full hydration...');

    try {
      await Promise.all([
        this.hydrateControlTower(),
        this.hydrateWorkspace(),
      ]);

      store.setInitialized(true);
      console.log('[DataHydration] Full hydration complete');
    } catch (error) {
      console.error('[DataHydration] Hydration failed:', error);
    } finally {
      store.setRefreshing(false);
      this.isHydrating = false;
    }
  }

  /**
   * Background refresh - lightweight, silent updates
   */
  async backgroundRefresh(): Promise<void> {
    const store = useDataStore.getState();

    try {
      const [perfData, schedulerData, automatedData] = await Promise.all([
        safeFetch<any>('/trading/performance', null),
        safeFetch<any>('/trading/scheduler/status', null),
        safeFetch<any>('/trading/automated/status', null),
      ]);

      if (perfData) store.setPerformance(perfData);
      if (schedulerData) {
        store.setScheduler(schedulerData);
        if (schedulerData.is_running !== undefined) {
          store.setAutonomousEnabled(schedulerData.is_running);
        }
      }
      if (automatedData) store.setAutomatedStatus(automatedData);
    } catch (error) {
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

  async refreshMetrics(): Promise<void> {
    const store = useDataStore.getState();
    const data = await safeFetch<any>('/history/performance', null);
    if (data?.summary) store.setMetrics(data.summary);
  }

  /**
   * Record a completed workflow result
   */
  async recordWorkflowComplete(result: WorkflowResult): Promise<void> {
    const store = useDataStore.getState();
    
    store.setLatestWorkflow(result);
    store.addAIActivity({
      type: 'analyze',
      message: `Analysis complete for ${result.tickers?.join(', ') || 'unknown'}`,
      status: 'complete',
      details: result,
    });

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
    
    console.log(`[DataHydration] Starting background refresh every ${intervalMs / 1000}s`);
    
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

// ==================== SLICE SELECTOR HOOKS ====================

/**
 * Control Tower slice data
 */
export function useControlTowerData() {
  const store = useDataStore();
  return {
    // State
    isAutonomousEnabled: store.isAutonomousEnabled,
    automatedStatus: store.automatedStatus,
    tradingConfig: store.tradingConfig,
    recentWorkflows: store.recentWorkflows,
    latestWorkflow: store.recentWorkflows[0] || null,
    aiActivities: store.aiActivities,
    quickAnalysisResult: store.quickAnalysisResult,
    quickAnalysisTicker: store.quickAnalysisTicker,
    // Shared data needed by Control Tower
    performance: store.performance,
    scheduler: store.scheduler,
    metrics: store.metrics,
    trades: store.trades,
    // Status
    isRefreshing: store.isRefreshing,
    // Actions
    setAutonomousEnabled: store.setAutonomousEnabled,
    setTradingConfig: store.setTradingConfig,
    setQuickAnalysisResult: store.setQuickAnalysisResult,
    setQuickAnalysisTicker: store.setQuickAnalysisTicker,
    addAIActivity: store.addAIActivity,
    // Hydration
    refresh: () => dataHydrationService.hydrateControlTower(),
    refreshAll: () => dataHydrationService.backgroundRefresh(),
  };
}

/**
 * Trading Workspace slice data
 */
export function useWorkspaceData() {
  const store = useDataStore();
  return {
    // State
    performance: store.performance,
    scheduler: store.scheduler,
    metrics: store.metrics,
    trades: store.trades,
    agents: store.agents,
    watchlist: store.watchlist,
    portfolioHealth: store.portfolioHealth,
    automatedStatus: store.automatedStatus,
    recentWorkflows: store.recentWorkflows,
    // Status
    isRefreshing: store.isRefreshing,
    // Actions
    setPortfolioHealth: store.setPortfolioHealth,
    // Hydration
    refresh: () => dataHydrationService.hydrateWorkspace(),
    refreshAll: () => dataHydrationService.backgroundRefresh(),
    refreshTrades: () => dataHydrationService.refreshTrades(),
    refreshAgents: () => dataHydrationService.refreshAgents(),
    refreshPortfolioHealth: () => dataHydrationService.refreshPortfolioHealth(),
    refreshMetrics: () => dataHydrationService.refreshMetrics(),
  };
}

/**
 * Intelligence Panel slice data (sidebar)
 */
export function useIntelligenceData() {
  const store = useDataStore();
  return {
    // State
    agentActivityLog: store.agentActivityLog,
    consoleLogs: store.consoleLogs,
    agentStatuses: store.agentStatuses,
    selectedAgentId: store.selectedAgentId,
    liveWorkflowProgress: store.liveWorkflowProgress,
    // Actions
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

/**
 * Global operations tracking (loading states visible across all tabs)
 */
export function useOperations() {
  const store = useDataStore();
  return {
    activeOperations: store.activeOperations,
    startOperation: store.startOperation,
    updateOperation: store.updateOperation,
    endOperation: store.endOperation,
  };
}

// ==================== LEGACY COMPAT HOOK ====================

/**
 * Legacy hook for backward compatibility
 * @deprecated Use slice-specific hooks instead: useControlTowerData, useWorkspaceData, useIntelligenceData
 */
export function useHydratedData() {
  const store = useDataStore();

  return {
    // Core Data (Workspace)
    performance: store.performance,
    scheduler: store.scheduler,
    trades: store.trades,
    agents: store.agents,
    metrics: store.metrics,
    watchlist: store.watchlist,
    automatedStatus: store.automatedStatus,
    portfolioHealth: store.portfolioHealth,
    latestWorkflow: store.recentWorkflows[0] || null,
    recentWorkflows: store.recentWorkflows,
    
    // Control Tower State
    isAutonomousEnabled: store.isAutonomousEnabled,
    aiActivities: store.aiActivities,
    tradingConfig: store.tradingConfig,
    quickAnalysisResult: store.quickAnalysisResult,
    quickAnalysisTicker: store.quickAnalysisTicker,
    
    // Active operations
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
    
    // Control Tower Actions
    setAutonomousEnabled: store.setAutonomousEnabled,
    addAIActivity: store.addAIActivity,
    setTradingConfig: store.setTradingConfig,
    setQuickAnalysisResult: store.setQuickAnalysisResult,
    setQuickAnalysisTicker: store.setQuickAnalysisTicker,
    
    // Operation tracking
    startOperation: store.startOperation,
    updateOperation: store.updateOperation,
    endOperation: store.endOperation,
    
    // Intelligence State & Actions
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
 */
export async function initializeDataHydration() {
  dataHydrationService.startBackgroundRefresh(15000);
  await dataHydrationService.hydrateAll();
}
