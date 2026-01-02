/**
 * SystemStatusPanel
 * 
 * Displays real-time system status including:
 * - Service health (scheduler, redis, database)
 * - Rate limit gauges for each API
 * - Stale data indicators with timestamps
 * - Recent pipeline latency
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  AlertTriangle,
  Clock,
  Database, 
  Server, 
  Cpu,
  Gauge,
  ChevronDown,
  ChevronUp,
  Activity
} from 'lucide-react';
import useSWR from 'swr';
import { API_BASE_URL } from '@/lib/api-config';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { InfoTooltip, TOOLTIP_CONTENT } from '@/components/ui/info-tooltip';

// Activity data types
interface CallActivityData {
  window_minutes: number;
  total_calls: number;
  providers: Record<string, {
    total: number;
    by_type: Record<string, number>;
    errors: number;
    display: string;
  }>;
  recent_events: Array<{
    api: string;
    type: string;
    time: string;
    timestamp: string;
    success: boolean;
    latency_ms?: number;
  }>;
}

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface ServiceStatus {
  status: 'healthy' | 'degraded' | 'down' | 'stale' | 'unknown';
  message?: string;
  latency_ms?: number;
  last_heartbeat?: string;
  minutes_since?: number;
  last_updated?: string;
}

interface RateLimitData {
  utilization_pct?: number;
  calls_remaining?: number;
  last_call_at?: string;
  minutes_since_update?: number;
  is_stale?: boolean;
}

/**
 * Format relative time (e.g., "5m ago", "2h ago")
 */
function formatRelativeTime(isoString?: string | null, minutesSince?: number | null): string {
  if (minutesSince !== undefined && minutesSince !== null) {
    if (minutesSince < 1) return 'just now';
    if (minutesSince < 60) return `${minutesSince}m ago`;
    const hours = Math.floor(minutesSince / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }
  
  if (!isoString) return 'never';
  
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const hours = Math.floor(diffMins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return 'unknown';
  }
}

function StatusIcon({ status, showTooltip = false, tooltipContent = '' }: { 
  status: string; 
  showTooltip?: boolean;
  tooltipContent?: string;
}) {
  const getIcon = () => {
    switch (status) {
      case 'healthy':
      case 'pass':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'degraded':
      case 'warn':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case 'stale':
        return <Clock className="h-4 w-4 text-amber-500" />;
      case 'down':
      case 'fail':
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'no_heartbeats':
        return <AlertTriangle className="h-4 w-4 text-orange-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  if (showTooltip && tooltipContent) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help">{getIcon()}</span>
        </TooltipTrigger>
        <TooltipContent>
          <p>{tooltipContent}</p>
        </TooltipContent>
      </Tooltip>
    );
  }
  
  return getIcon();
}

function StaleWarningBadge({ isStale, lastUpdate }: { isStale: boolean; lastUpdate?: string }) {
  if (!isStale) return null;
  
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="ml-2 text-amber-600 border-amber-400 bg-amber-50 text-xs gap-1">
          <Clock className="h-3 w-3" />
          Stale
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        <p>Data last updated: {formatRelativeTime(lastUpdate)}</p>
      </TooltipContent>
    </Tooltip>
  );
}

function RateLimitGauge({
  name,
  utilization,
  remaining,
  lastCallAt,
  isStale,
  activityData,
}: {
  name: string;
  utilization: number;
  remaining?: number;
  lastCallAt?: string;
  isStale?: boolean;
  activityData?: {
    total: number;
    by_type: Record<string, number>;
    errors: number;
    display: string;
  };
}) {
  const getColor = (pct: number) => {
    if (pct >= 90) return 'bg-red-500';
    if (pct >= 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  // Friendly display names for API services
  const getDisplayName = (apiName: string) => {
    const displayNames: Record<string, string> = {
      'fmp_data': 'FMP Ultimate',
      'openai_proxy': 'OpenAI Proxy (xcmfai)',
      'openai': 'OpenAI Direct',
      'financial_datasets': 'Financial Datasets',
      'alpaca': 'Alpaca Trading',
      'alpaca_data': 'Alpaca Market Data',
      'anthropic': 'Anthropic',
      'groq': 'Groq',
    };
    return displayNames[apiName] || apiName.replace(/_/g, ' ');
  };

  // Build breakdown string for tooltip
  const getBreakdownString = () => {
    if (!activityData?.by_type || Object.keys(activityData.by_type).length === 0) {
      return null;
    }
    const sorted = Object.entries(activityData.by_type)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4); // Top 4 call types
    return sorted.map(([type, count]) => `${type}: ${count}`).join(', ');
  };

  const breakdown = getBreakdownString();

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="capitalize flex items-center gap-1">
          {getDisplayName(name)}
          {isStale && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Clock className="h-3 w-3 text-amber-500 cursor-help" />
              </TooltipTrigger>
              <TooltipContent>
                <p>Rate limit data not updated for &gt;1 hour</p>
                {lastCallAt && <p className="text-xs">Last: {formatRelativeTime(lastCallAt)}</p>}
              </TooltipContent>
            </Tooltip>
          )}
        </span>
        <span className={utilization >= 80 ? 'text-red-500 font-medium' : 'text-muted-foreground'}>
          {utilization.toFixed(0)}%
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div 
          className={`h-full transition-all ${isStale ? 'bg-gray-400' : getColor(utilization)}`}
          style={{ width: `${Math.min(utilization, 100)}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        {remaining !== undefined && remaining !== null ? (
          <span>{remaining.toLocaleString()} remaining</span>
        ) : (
          <span />
        )}
        {activityData && activityData.total > 0 && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-cyan-500 cursor-help">
                {activityData.total} calls/hr
              </span>
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-xs">
              <p className="font-medium">{getDisplayName(name)}</p>
              <p className="text-xs">{activityData.total} calls in last hour</p>
              {breakdown && (
                <p className="text-xs text-slate-400 mt-1">{breakdown}</p>
              )}
              {activityData.errors > 0 && (
                <p className="text-xs text-red-400 mt-1">{activityData.errors} errors</p>
              )}
            </TooltipContent>
          </Tooltip>
        )}
      </div>
    </div>
  );
}

export function SystemStatusPanel() {
  const [showActivityLog, setShowActivityLog] = React.useState(false);
  
  const { data: systemStatus, error, isLoading } = useSWR(
    `${API_BASE_URL}/monitoring/system/status`,
    fetcher,
    { refreshInterval: 10000 }
  );
  
  const { data: healthData } = useSWR(
    `${API_BASE_URL}/monitoring/health`,
    fetcher,
    { refreshInterval: 30000 }
  );
  
  const { data: freshnessData } = useSWR(
    `${API_BASE_URL}/monitoring/metrics/freshness`,
    fetcher,
    { refreshInterval: 30000 }
  );
  
  // Fetch call activity data for the Rate Limits section
  const { data: activityData } = useSWR<CallActivityData>(
    `${API_BASE_URL}/monitoring/rate-limits/activity?window_minutes=60&limit=15`,
    fetcher,
    { refreshInterval: 15000 }
  );
  
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            System Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-muted rounded w-3/4" />
            <div className="h-4 bg-muted rounded w-1/2" />
            <div className="h-4 bg-muted rounded w-2/3" />
          </div>
        </CardContent>
      </Card>
    );
  }
  
  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            System Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center text-muted-foreground py-4">
            <XCircle className="h-8 w-8 mx-auto mb-2 text-red-500" />
            <p>Failed to load system status</p>
          </div>
        </CardContent>
      </Card>
    );
  }
  
  const overallStatus = healthData?.overall_status || 'unknown';
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            System Status
          </span>
          <Badge 
            variant={
              overallStatus === 'READY' ? 'default' : 
              overallStatus === 'DEGRADED' ? 'secondary' : 
              'destructive'
            }
          >
            {overallStatus}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <TooltipProvider>
        {/* Data Freshness Alert */}
        {freshnessData?.is_stale && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800">
            <AlertTriangle className="h-4 w-4" />
            <div className="flex-1">
              <p className="text-sm font-medium">Data may be stale</p>
              <p className="text-xs">
                Last workflow: {formatRelativeTime(freshnessData.last_workflow_at, freshnessData.minutes_since_workflow)}
                {freshnessData.last_signal_at && ` • Last signal: ${formatRelativeTime(freshnessData.last_signal_at, freshnessData.minutes_since_signal)}`}
              </p>
            </div>
          </div>
        )}

        {/* Service Status */}
        <div>
          <h4 className="text-sm font-medium mb-3">Services</h4>
          <div className="grid grid-cols-3 gap-4">
            {/* Scheduler */}
            <div className={`flex items-center gap-2 p-2 rounded-lg ${
              systemStatus?.scheduler?.status === 'stale' ? 'bg-amber-50 border border-amber-200' :
              systemStatus?.scheduler?.status === 'no_heartbeats' ? 'bg-orange-50 border border-orange-200' :
              'bg-muted/50'
            }`}>
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <div className="flex-1">
                <p className="text-sm font-medium">Scheduler</p>
                <div className="flex items-center gap-1">
                  <StatusIcon 
                    status={systemStatus?.scheduler?.status || 'unknown'} 
                    showTooltip={systemStatus?.scheduler?.status === 'stale'}
                    tooltipContent={systemStatus?.scheduler?.message || 'Scheduler heartbeat is stale'}
                  />
                  <span className="text-xs text-muted-foreground">
                    {systemStatus?.scheduler?.status || 'Unknown'}
                  </span>
                </div>
                {systemStatus?.scheduler?.last_heartbeat && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Last: {formatRelativeTime(systemStatus.scheduler.last_heartbeat, systemStatus.scheduler.minutes_since)}
                  </p>
                )}
              </div>
            </div>
            
            {/* Redis */}
            <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/50">
              <Database className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Redis</p>
                <div className="flex items-center gap-1">
                  <StatusIcon status={systemStatus?.redis?.status || 'unknown'} />
                  <span className="text-xs text-muted-foreground">
                    {systemStatus?.redis?.backend || 'Unknown'}
                  </span>
                </div>
              </div>
            </div>
            
            {/* Database */}
            <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/50">
              <Database className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Database</p>
                <div className="flex items-center gap-1">
                  <StatusIcon status={systemStatus?.database?.status || 'unknown'} />
                  <span className="text-xs text-muted-foreground">
                    {systemStatus?.database?.status || 'Unknown'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* Rate Limits */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium flex items-center gap-2">
              <Gauge className="h-4 w-4" />
              Rate Limits
              <InfoTooltip content={TOOLTIP_CONTENT.rateLimit} />
            </h4>
            {activityData && activityData.total_calls > 0 && (
              <span className="text-xs text-cyan-500">
                {activityData.total_calls} calls/hr
              </span>
            )}
          </div>
          <div className="space-y-3">
            {systemStatus?.rate_limits && Object.entries(systemStatus.rate_limits).map(([name, data]: [string, RateLimitData]) => (
              <RateLimitGauge 
                key={name}
                name={name}
                utilization={data.utilization_pct || 0}
                remaining={data.calls_remaining}
                lastCallAt={data.last_call_at}
                isStale={data.is_stale}
                activityData={activityData?.providers?.[name]}
              />
            ))}
            {(!systemStatus?.rate_limits || Object.keys(systemStatus.rate_limits).length === 0) && (
              <p className="text-sm text-muted-foreground text-center py-2">
                No rate limit data available
              </p>
            )}
          </div>
          
          {/* Collapsible Activity Log */}
          {activityData?.recent_events && activityData.recent_events.length > 0 && (
            <div className="mt-4 pt-3 border-t border-border/50">
              <button
                onClick={() => setShowActivityLog(!showActivityLog)}
                className="flex items-center justify-between w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <span className="flex items-center gap-1">
                  <Activity className="h-3 w-3" />
                  Recent API Activity ({activityData.recent_events.length} events)
                </span>
                {showActivityLog ? (
                  <ChevronUp className="h-3 w-3" />
                ) : (
                  <ChevronDown className="h-3 w-3" />
                )}
              </button>
              
              {showActivityLog && (
                <div className="mt-2 max-h-40 overflow-y-auto space-y-1">
                  {activityData.recent_events.map((event, idx) => (
                    <div 
                      key={idx}
                      className={`flex items-center justify-between text-xs py-1 px-2 rounded ${
                        event.success ? 'bg-muted/30' : 'bg-red-500/10'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        {event.success ? (
                          <CheckCircle2 className="h-3 w-3 text-green-500" />
                        ) : (
                          <XCircle className="h-3 w-3 text-red-500" />
                        )}
                        <span className="font-medium">{event.api}</span>
                        <span className="text-muted-foreground">→ {event.type}</span>
                      </span>
                      <span className="text-muted-foreground flex items-center gap-2">
                        {event.latency_ms && (
                          <span className="text-[10px]">{event.latency_ms}ms</span>
                        )}
                        {event.time}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* Health Check Details */}
        {healthData?.checks && Object.keys(healthData.checks).length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-3">Health Checks</h4>
            <div className="space-y-2">
              {Object.entries(healthData.checks).map(([name, check]: [string, any]) => (
                <div 
                  key={name} 
                  className="flex items-center justify-between text-sm py-1 border-b border-border/50 last:border-0"
                >
                  <span className="capitalize">{name.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    <StatusIcon status={check.status} />
                    {check.latency_ms && (
                      <span className="text-xs text-muted-foreground">
                        {check.latency_ms}ms
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Last Updated Footer */}
        {systemStatus?.last_updated && (
          <div className="pt-2 border-t border-border/50">
            <p className="text-xs text-muted-foreground text-right">
              Last updated: {formatRelativeTime(systemStatus.last_updated)}
            </p>
          </div>
        )}
        </TooltipProvider>
      </CardContent>
    </Card>
  );
}

export default SystemStatusPanel;
