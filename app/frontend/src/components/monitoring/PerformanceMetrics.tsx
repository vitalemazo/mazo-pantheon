/**
 * PerformanceMetrics
 * 
 * Displays key performance metrics including:
 * - Daily P&L
 * - Win rate
 * - Sharpe ratio
 * - Workflow and trade counts
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  Target,
  Zap,
  Clock
} from 'lucide-react';
import useSWR from 'swr';
import { API_BASE_URL } from '@/lib/api-config';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
}

function MetricCard({ title, value, subtitle, icon, trend, trendValue }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
            )}
            {trend && trendValue && (
              <div className={`flex items-center gap-1 mt-1 text-xs ${
                trend === 'up' ? 'text-green-500' : 
                trend === 'down' ? 'text-red-500' : 
                'text-muted-foreground'
              }`}>
                {trend === 'up' ? <TrendingUp className="h-3 w-3" /> : 
                 trend === 'down' ? <TrendingDown className="h-3 w-3" /> : null}
                {trendValue}
              </div>
            )}
          </div>
          <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface PerformanceMetricsProps {
  showCharts?: boolean;
}

export function PerformanceMetrics({ showCharts = false }: PerformanceMetricsProps) {
  const { data: dailyMetrics, isLoading } = useSWR(
    `${API_BASE_URL}/monitoring/metrics/daily`,
    fetcher,
    { refreshInterval: 60000 }
  );
  
  const { data: executionMetrics } = useSWR(
    `${API_BASE_URL}/monitoring/metrics/execution?days=7`,
    fetcher,
    { refreshInterval: 60000 }
  );
  
  const { data: mazoMetrics } = useSWR(
    `${API_BASE_URL}/monitoring/metrics/mazo?days=30`,
    fetcher,
    { refreshInterval: 60000 }
  );
  
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <Card key={i}>
            <CardContent className="pt-6">
              <div className="animate-pulse space-y-2">
                <div className="h-4 bg-muted rounded w-1/2" />
                <div className="h-8 bg-muted rounded w-3/4" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }
  
  const winRate = dailyMetrics?.win_rate || 0;
  const pipelineLatency = dailyMetrics?.avg_pipeline_latency_ms || 0;
  const llmLatency = dailyMetrics?.avg_llm_latency_ms || 0;
  const fillRate = executionMetrics?.fill_rate || 0;
  const avgSlippage = executionMetrics?.avg_slippage_bps || 0;
  const mazoAgreement = mazoMetrics?.pm_agreement_rate || 0;
  
  return (
    <div className="space-y-4">
      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Workflows Run"
          value={dailyMetrics?.workflows_run || 0}
          subtitle="Today"
          icon={<Activity className="h-6 w-6 text-primary" />}
        />
        
        <MetricCard
          title="Signals Generated"
          value={dailyMetrics?.signals_generated || 0}
          subtitle="Today"
          icon={<Zap className="h-6 w-6 text-primary" />}
        />
        
        <MetricCard
          title="Trades Executed"
          value={dailyMetrics?.trades_executed || 0}
          subtitle="Today"
          icon={<Target className="h-6 w-6 text-primary" />}
        />
        
        <MetricCard
          title="Win Rate"
          value={`${(winRate * 100).toFixed(0)}%`}
          subtitle="Today"
          icon={
            winRate >= 0.5 ? 
            <TrendingUp className="h-6 w-6 text-green-500" /> : 
            <TrendingDown className="h-6 w-6 text-red-500" />
          }
          trend={winRate >= 0.5 ? 'up' : 'down'}
        />
      </div>
      
      {/* Extended Metrics */}
      {showCharts && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            title="Pipeline Latency"
            value={pipelineLatency > 0 ? `${(pipelineLatency / 1000).toFixed(1)}s` : '--'}
            subtitle="Average"
            icon={<Clock className="h-6 w-6 text-primary" />}
          />
          
          <MetricCard
            title="LLM Latency"
            value={llmLatency > 0 ? `${(llmLatency / 1000).toFixed(1)}s` : '--'}
            subtitle="Average"
            icon={<Clock className="h-6 w-6 text-primary" />}
          />
          
          <MetricCard
            title="Fill Rate"
            value={`${(fillRate * 100).toFixed(0)}%`}
            subtitle="7-day average"
            icon={<Target className="h-6 w-6 text-primary" />}
          />
          
          <MetricCard
            title="Avg Slippage"
            value={`${avgSlippage.toFixed(1)} bps`}
            subtitle="7-day average"
            icon={<Activity className="h-6 w-6 text-primary" />}
          />
        </div>
      )}
      
      {/* Mazo Effectiveness */}
      {showCharts && mazoMetrics && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Mazo Research Effectiveness</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold">
                  {((mazoMetrics.success_rate || 0) * 100).toFixed(0)}%
                </p>
                <p className="text-sm text-muted-foreground">Success Rate</p>
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {((mazoMetrics.pm_agreement_rate || 0) * 100).toFixed(0)}%
                </p>
                <p className="text-sm text-muted-foreground">PM Agreement</p>
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {((mazoMetrics.avg_latency_ms || 0) / 1000).toFixed(1)}s
                </p>
                <p className="text-sm text-muted-foreground">Avg Latency</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default PerformanceMetrics;
