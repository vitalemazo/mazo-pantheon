import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react';

interface Position {
  ticker: string;
  qty: number;
  side: string;
  entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

interface PerformanceData {
  timestamp: string;
  equity: number;
  cash: number;
  buying_power: number;
  day_pnl: number;
  day_pnl_pct: number;
  total_unrealized_pnl: number;
  positions_count: number;
  positions: Position[];
  best_position: Position | null;
  worst_position: Position | null;
}

interface Metrics {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number | null;
  total_pnl: number;
  average_pnl: number | null;
  average_return_pct: number | null;
  profit_factor: number | null;
  average_holding_hours: number | null;
}

interface SchedulerStatus {
  is_running: boolean;
  scheduled_tasks: Array<{
    id: string;
    name: string;
    next_run: string;
    trigger: string;
  }>;
  recent_history: Array<{
    task_id: string;
    task_type: string;
    success: boolean;
    timestamp: string;
  }>;
}

interface WatchlistItem {
  id: number;
  ticker: string;
  entry_target: number;
  status: string;
  priority: number;
  strategy: string;
}

interface AutomatedTradingStatus {
  is_running: boolean;
  last_run: string | null;
  total_runs: number;
  last_result: {
    tickers_screened: number;
    signals_found: number;
    mazo_validated: number;
    trades_analyzed: number;
    trades_executed: number;
    total_execution_time_ms: number;
    results: Array<{
      ticker: string;
      action: string;
      dry_run?: boolean;
    }>;
    errors: string[];
  } | null;
}

interface TradingDashboardContextType {
  performance: PerformanceData | null;
  metrics: Metrics | null;
  scheduler: SchedulerStatus | null;
  watchlist: WatchlistItem[];
  automatedStatus: AutomatedTradingStatus | null;
  loading: boolean;
  aiLoading: boolean;
  error: string | null;
  lastRefresh: Date | null;
  fetchData: () => Promise<void>;
  toggleScheduler: () => Promise<void>;
  addDefaultSchedule: () => Promise<void>;
  runAiTradingCycle: (dryRun?: boolean) => Promise<void>;
}

const TradingDashboardContext = createContext<TradingDashboardContextType | undefined>(undefined);

// Cache duration in milliseconds (30 seconds)
const CACHE_DURATION_MS = 30000;

export function TradingDashboardProvider({ children }: { children: ReactNode }) {
  const [performance, setPerformance] = useState<PerformanceData | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [automatedStatus, setAutomatedStatus] = useState<AutomatedTradingStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  
  // Track if we've ever fetched data
  const hasFetchedRef = useRef(false);
  // Track the auto-refresh interval
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [perfRes, metricsRes, schedulerRes, watchlistRes, automatedRes] = await Promise.all([
        fetch('http://localhost:8000/trading/performance'),
        fetch('http://localhost:8000/trading/performance/metrics'),
        fetch('http://localhost:8000/trading/scheduler/status'),
        fetch('http://localhost:8000/trading/watchlist'),
        fetch('http://localhost:8000/trading/automated/status'),
      ]);

      if (perfRes.ok) {
        const data = await perfRes.json();
        setPerformance(data);
      }

      if (metricsRes.ok) {
        const data = await metricsRes.json();
        setMetrics(data.metrics);
      }

      if (schedulerRes.ok) {
        const data = await schedulerRes.json();
        setScheduler(data);
      }

      if (watchlistRes.ok) {
        const data = await watchlistRes.json();
        setWatchlist(data.items || []);
      }

      if (automatedRes.ok) {
        const data = await automatedRes.json();
        setAutomatedStatus(data);
      }

      setLastRefresh(new Date());
      hasFetchedRef.current = true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleScheduler = useCallback(async () => {
    try {
      const endpoint = scheduler?.is_running 
        ? 'http://localhost:8000/trading/scheduler/stop'
        : 'http://localhost:8000/trading/scheduler/start';
      
      await fetch(endpoint, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error('Failed to toggle scheduler:', err);
    }
  }, [scheduler?.is_running, fetchData]);

  const addDefaultSchedule = useCallback(async () => {
    try {
      await fetch('http://localhost:8000/trading/scheduler/add-default-schedule', { 
        method: 'POST' 
      });
      fetchData();
    } catch (err) {
      console.error('Failed to add schedule:', err);
    }
  }, [fetchData]);

  const runAiTradingCycle = useCallback(async (dryRun: boolean = false) => {
    setAiLoading(true);
    try {
      const endpoint = dryRun 
        ? 'http://localhost:8000/trading/automated/dry-run'
        : 'http://localhost:8000/trading/automated/run';
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          min_confidence: 60,
          max_signals: 5,
          execute_trades: true,
        }),
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('AI Trading Result:', data);
        fetchData();
      }
    } catch (err) {
      console.error('Failed to run AI trading:', err);
    } finally {
      setAiLoading(false);
    }
  }, [fetchData]);

  // Set up background auto-refresh (runs regardless of tab visibility)
  useEffect(() => {
    // Initial fetch only if we haven't fetched before
    if (!hasFetchedRef.current) {
      fetchData();
    }

    // Set up auto-refresh every 30 seconds
    intervalRef.current = setInterval(() => {
      fetchData();
    }, CACHE_DURATION_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchData]);

  return (
    <TradingDashboardContext.Provider value={{
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
    }}>
      {children}
    </TradingDashboardContext.Provider>
  );
}

export function useTradingDashboard() {
  const context = useContext(TradingDashboardContext);
  if (context === undefined) {
    throw new Error('useTradingDashboard must be used within a TradingDashboardProvider');
  }
  return context;
}
