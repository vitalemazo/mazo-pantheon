/**
 * Data Hydration Service
 * 
 * This service implements the Stale-While-Revalidate (SWR) pattern:
 * 1. On app startup, fetch ALL data and cache it
 * 2. Background refresh at configurable intervals
 * 3. Components ALWAYS see cached data immediately (no loading states)
 * 4. When new data arrives, update the cache and notify subscribers
 * 
 * The user should NEVER see an empty state unless there truly is no data.
 */

import { create } from 'zustand';

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

// Latest workflow result - shared across all tabs
export interface WorkflowResult {
  id: string;
  timestamp: Date;
  tickers: string[];
  mode: string;
  agentSignals: Array<{
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

// ==================== STORE ====================

interface DataStore {
  // Data
  performance: PerformanceData | null;
  scheduler: SchedulerStatus | null;
  trades: TradeHistoryItem[];
  agents: AgentPerformance[];
  metrics: PerformanceMetrics | null;
  watchlist: WatchlistItem[];
  automatedStatus: AutomatedTradingStatus | null;
  portfolioHealth: PortfolioHealthData | null;
  latestWorkflow: WorkflowResult | null;
  recentWorkflows: WorkflowResult[];

  // Metadata
  lastUpdated: Record<string, Date>;
  isInitialized: boolean;
  isRefreshing: boolean;
  errors: Record<string, string | null>;

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
}

export const useDataStore = create<DataStore>((set) => ({
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

  lastUpdated: {},
  isInitialized: false,
  isRefreshing: false,
  errors: {},

  // Setters that update lastUpdated timestamp
  setPerformance: (data) => set((state) => ({
    performance: data,
    lastUpdated: { ...state.lastUpdated, performance: new Date() }
  })),
  setScheduler: (data) => set((state) => ({
    scheduler: data,
    lastUpdated: { ...state.lastUpdated, scheduler: new Date() }
  })),
  setTrades: (data) => set((state) => ({
    trades: data,
    lastUpdated: { ...state.lastUpdated, trades: new Date() }
  })),
  setAgents: (data) => set((state) => ({
    agents: data,
    lastUpdated: { ...state.lastUpdated, agents: new Date() }
  })),
  setMetrics: (data) => set((state) => ({
    metrics: data,
    lastUpdated: { ...state.lastUpdated, metrics: new Date() }
  })),
  setWatchlist: (data) => set((state) => ({
    watchlist: data,
    lastUpdated: { ...state.lastUpdated, watchlist: new Date() }
  })),
  setAutomatedStatus: (data) => set((state) => ({
    automatedStatus: data,
    lastUpdated: { ...state.lastUpdated, automatedStatus: new Date() }
  })),
  setPortfolioHealth: (data) => set((state) => ({
    portfolioHealth: data,
    lastUpdated: { ...state.lastUpdated, portfolioHealth: new Date() }
  })),
  setLatestWorkflow: (data) => set((state) => ({
    latestWorkflow: data,
    recentWorkflows: [data, ...state.recentWorkflows.slice(0, 9)], // Keep last 10
    lastUpdated: { ...state.lastUpdated, latestWorkflow: new Date() }
  })),
  setError: (key, error) => set((state) => ({
    errors: { ...state.errors, [key]: error }
  })),
  setRefreshing: (value) => set({ isRefreshing: value }),
  setInitialized: (value) => set({ isInitialized: value }),
}));

// ==================== FETCH FUNCTIONS ====================

const API_BASE = 'http://localhost:8000';

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
    const response = await fetchWithTimeout(`${API_BASE}${url}`);
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

  /**
   * Initial hydration - fetch ALL data on app startup
   * This runs once when the app loads
   */
  async hydrateAll(): Promise<void> {
    if (this.isHydrating) return;
    this.isHydrating = true;

    const store = useDataStore.getState();
    store.setRefreshing(true);

    console.log('[DataHydration] Starting initial hydration...');

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
      if (schedulerData) store.setScheduler(schedulerData);
      if (tradesData?.trades) store.setTrades(tradesData.trades);
      if (agentsData?.agents) store.setAgents(agentsData.agents);
      if (metricsData?.summary) store.setMetrics(metricsData.summary);
      if (watchlistData?.items) store.setWatchlist(watchlistData.items);
      if (automatedData) store.setAutomatedStatus(automatedData);

      store.setInitialized(true);
      console.log('[DataHydration] Initial hydration complete');

    } catch (error) {
      console.error('[DataHydration] Hydration failed:', error);
    } finally {
      store.setRefreshing(false);
      this.isHydrating = false;
    }
  }

  /**
   * Background refresh - updates data without showing loading states
   * Runs every N seconds in the background
   */
  async backgroundRefresh(): Promise<void> {
    const store = useDataStore.getState();
    
    // Don't show loading state for background refresh
    // The UI keeps showing old data while new data loads

    try {
      const [perfData, schedulerData, automatedData] = await Promise.all([
        safeFetch<any>('/trading/performance', null),
        safeFetch<any>('/trading/scheduler/status', null),
        safeFetch<any>('/trading/automated/status', null),
      ]);

      // Only update if we got data - never clear existing data
      if (perfData) store.setPerformance(perfData);
      if (schedulerData) store.setScheduler(schedulerData);
      if (automatedData) store.setAutomatedStatus(automatedData);

    } catch (error) {
      // Silent fail for background refresh - don't disrupt UI
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
      const response = await fetch(`${API_BASE}/unified-workflow/portfolio-health-check`, {
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
   * This updates the store AND triggers refresh of related data
   * so all tabs see the new trade/positions
   */
  async recordWorkflowComplete(result: WorkflowResult): Promise<void> {
    const store = useDataStore.getState();
    
    // Store the workflow result
    store.setLatestWorkflow(result);
    
    // If a trade was executed, refresh positions and trade history
    if (result.tradeExecuted) {
      console.log('[DataHydration] Trade executed, refreshing positions and history...');
      
      // Refresh in parallel
      await Promise.all([
        this.refreshTrades(),
        this.refreshAgents(),
        this.backgroundRefresh(), // Updates positions from Alpaca
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
    // Data (always available after first load)
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
  };
}
