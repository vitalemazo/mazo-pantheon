import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface Position {
  symbol: string;
  qty: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  avg_entry_price: number;
  current_price: number;
}

interface PendingOrder {
  id: string;
  symbol: string;
  side: string;
  qty: number;
  type: string;
  status: string;
  created_at: string;
}

interface PortfolioData {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
}

export interface HealthCheckResult {
  success: boolean;
  execution_time_ms: number;
  portfolio: PortfolioData;
  positions: Position[];
  pending_orders: PendingOrder[];
  analysis: string;
  confidence: number;
  error: string | null;
}

interface PortfolioHealthContextType {
  healthData: HealthCheckResult | null;
  loading: boolean;
  error: string | null;
  lastRefresh: Date | null;
  runHealthCheck: () => Promise<void>;
  clearCache: () => void;
}

const PortfolioHealthContext = createContext<PortfolioHealthContextType | undefined>(undefined);

export function PortfolioHealthProvider({ children }: { children: ReactNode }) {
  const [healthData, setHealthData] = useState<HealthCheckResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const runHealthCheck = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/unified-workflow/portfolio-health-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      
      if (!response.ok) {
        throw new Error(`Health check failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      setHealthData(data);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run health check');
    } finally {
      setLoading(false);
    }
  }, []);

  const clearCache = useCallback(() => {
    setHealthData(null);
    setLastRefresh(null);
    setError(null);
  }, []);

  return (
    <PortfolioHealthContext.Provider value={{
      healthData,
      loading,
      error,
      lastRefresh,
      runHealthCheck,
      clearCache
    }}>
      {children}
    </PortfolioHealthContext.Provider>
  );
}

export function usePortfolioHealth() {
  const context = useContext(PortfolioHealthContext);
  if (context === undefined) {
    throw new Error('usePortfolioHealth must be used within a PortfolioHealthProvider');
  }
  return context;
}
