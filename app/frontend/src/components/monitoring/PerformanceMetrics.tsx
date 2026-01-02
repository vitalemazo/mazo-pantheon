/**
 * PerformanceMetrics (Execution Quality)
 * 
 * Displays infrastructure & execution quality metrics:
 * - Pipeline throughput (workflows, signals)
 * - Latency metrics (pipeline, LLM)
 * - Execution quality (fill rate, slippage)
 * - Mazo research effectiveness
 * 
 * This is NOT about trading P&L - that belongs in Trading Workspace.
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Clock,
  Activity, 
  Target,
  Zap,
  Gauge,
  Server,
  Brain,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import useSWR from 'swr';
import { API_BASE_URL } from '@/lib/api-config';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  status?: 'good' | 'warn' | 'bad' | 'neutral';
}

function MetricCard({ title, value, subtitle, icon, status = 'neutral' }: MetricCardProps) {
  const statusColors = {
    good: 'text-emerald-400',
    warn: 'text-amber-400',
    bad: 'text-red-400',
    neutral: 'text-white'
  };

  return (
    <Card className="bg-slate-800/50 border-slate-700">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-400">{title}</p>
            <p className={`text-2xl font-bold ${statusColors[status]}`}>{value}</p>
            {subtitle && (
              <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
            )}
          </div>
          <div className="h-12 w-12 rounded-full bg-slate-700/50 flex items-center justify-center">
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
          <Card key={i} className="bg-slate-800/50 border-slate-700">
            <CardContent className="pt-6">
              <div className="animate-pulse space-y-2">
                <div className="h-4 bg-slate-700 rounded w-1/2" />
                <div className="h-8 bg-slate-700 rounded w-3/4" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }
  
  const pipelineLatency = dailyMetrics?.avg_pipeline_latency_ms || 0;
  const llmLatency = dailyMetrics?.avg_llm_latency_ms || 0;
  const fillRate = executionMetrics?.fill_rate || 0;
  const avgSlippage = executionMetrics?.avg_slippage_bps || 0;
  
  // Determine status based on thresholds
  const getPipelineStatus = (ms: number) => {
    if (ms === 0) return 'neutral';
    if (ms < 30000) return 'good';
    if (ms < 60000) return 'warn';
    return 'bad';
  };
  
  const getLLMStatus = (ms: number) => {
    if (ms === 0) return 'neutral';
    if (ms < 5000) return 'good';
    if (ms < 10000) return 'warn';
    return 'bad';
  };
  
  const getFillStatus = (rate: number) => {
    if (rate >= 0.95) return 'good';
    if (rate >= 0.85) return 'warn';
    return 'bad';
  };
  
  const getSlippageStatus = (bps: number) => {
    if (bps <= 5) return 'good';
    if (bps <= 15) return 'warn';
    return 'bad';
  };
  
  return (
    <div className="space-y-4">
      {/* Throughput Section */}
      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          Pipeline Throughput (Today)
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            title="Workflows Run"
            value={dailyMetrics?.workflows_run || 0}
            subtitle="AI cycles executed"
            icon={<Server className="h-6 w-6 text-blue-400" />}
          />
          
          <MetricCard
            title="Signals Generated"
            value={dailyMetrics?.signals_generated || 0}
            subtitle="From strategy engine"
            icon={<Zap className="h-6 w-6 text-cyan-400" />}
          />
          
          <MetricCard
            title="Trades Executed"
            value={dailyMetrics?.trades_executed || 0}
            subtitle="Orders submitted"
            icon={<Target className="h-6 w-6 text-purple-400" />}
          />
          
          <MetricCard
            title="Agents Invoked"
            value={dailyMetrics?.agents_invoked || '--'}
            subtitle="LLM calls today"
            icon={<Brain className="h-6 w-6 text-pink-400" />}
          />
        </div>
      </div>
      
      {/* Latency Section */}
      {showCharts && (
        <div>
          <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Latency & Performance
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              title="Pipeline Latency"
              value={pipelineLatency > 0 ? `${(pipelineLatency / 1000).toFixed(1)}s` : '--'}
              subtitle="Full cycle time"
              icon={<Clock className="h-6 w-6 text-blue-400" />}
              status={getPipelineStatus(pipelineLatency)}
            />
            
            <MetricCard
              title="LLM Latency"
              value={llmLatency > 0 ? `${(llmLatency / 1000).toFixed(1)}s` : '--'}
              subtitle="Average per call"
              icon={<Brain className="h-6 w-6 text-purple-400" />}
              status={getLLMStatus(llmLatency)}
            />
            
            <MetricCard
              title="Fill Rate"
              value={fillRate > 0 ? `${(fillRate * 100).toFixed(0)}%` : '--'}
              subtitle="7-day average"
              icon={<CheckCircle2 className="h-6 w-6 text-emerald-400" />}
              status={getFillStatus(fillRate)}
            />
            
            <MetricCard
              title="Avg Slippage"
              value={avgSlippage > 0 ? `${avgSlippage.toFixed(1)} bps` : '--'}
              subtitle="7-day average"
              icon={<Gauge className="h-6 w-6 text-amber-400" />}
              status={getSlippageStatus(avgSlippage)}
            />
          </div>
        </div>
      )}
      
      {/* Mazo Effectiveness */}
      {showCharts && mazoMetrics && (
        <div>
          <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
            <Brain className="w-4 h-4" />
            Mazo Research Effectiveness (30d)
          </h3>
          <Card className="bg-slate-800/50 border-slate-700">
            <CardContent className="py-4">
              <div className="grid grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-emerald-400">
                    {((mazoMetrics.success_rate || 0) * 100).toFixed(0)}%
                  </p>
                  <p className="text-xs text-slate-400">API Success Rate</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-purple-400">
                    {((mazoMetrics.pm_agreement_rate || 0) * 100).toFixed(0)}%
                  </p>
                  <p className="text-xs text-slate-400">PM Agreement</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-cyan-400">
                    {((mazoMetrics.avg_latency_ms || 0) / 1000).toFixed(1)}s
                  </p>
                  <p className="text-xs text-slate-400">Avg Response Time</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">
                    {mazoMetrics.total_calls || 0}
                  </p>
                  <p className="text-xs text-slate-400">Total Calls</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

export default PerformanceMetrics;
