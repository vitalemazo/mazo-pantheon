/**
 * SystemStatusPanel
 * 
 * Displays real-time system status including:
 * - Service health (scheduler, redis, database)
 * - Rate limit gauges for each API
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
  Database, 
  Server, 
  Cpu,
  Gauge
} from 'lucide-react';
import useSWR from 'swr';
import { API_BASE_URL_URL } from '@/lib/api-config';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface ServiceStatus {
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  message?: string;
  latency_ms?: number;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'healthy':
    case 'pass':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'degraded':
    case 'warn':
      return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    case 'down':
    case 'fail':
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <AlertCircle className="h-4 w-4 text-gray-500" />;
  }
}

function RateLimitGauge({ 
  name, 
  utilization, 
  remaining 
}: { 
  name: string; 
  utilization: number; 
  remaining?: number;
}) {
  const getColor = (pct: number) => {
    if (pct >= 90) return 'bg-red-500';
    if (pct >= 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };
  
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="capitalize">{name.replace(/_/g, ' ')}</span>
        <span className={utilization >= 80 ? 'text-red-500 font-medium' : 'text-muted-foreground'}>
          {utilization.toFixed(0)}%
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div 
          className={`h-full transition-all ${getColor(utilization)}`}
          style={{ width: `${Math.min(utilization, 100)}%` }}
        />
      </div>
      {remaining !== undefined && remaining !== null && (
        <p className="text-xs text-muted-foreground">
          {remaining.toLocaleString()} calls remaining
        </p>
      )}
    </div>
  );
}

export function SystemStatusPanel() {
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
        {/* Service Status */}
        <div>
          <h4 className="text-sm font-medium mb-3">Services</h4>
          <div className="grid grid-cols-3 gap-4">
            {/* Scheduler */}
            <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/50">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Scheduler</p>
                <div className="flex items-center gap-1">
                  <StatusIcon status={systemStatus?.scheduler?.status || 'unknown'} />
                  <span className="text-xs text-muted-foreground">
                    {systemStatus?.scheduler?.status || 'Unknown'}
                  </span>
                </div>
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
          <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
            <Gauge className="h-4 w-4" />
            Rate Limits
          </h4>
          <div className="space-y-3">
            {systemStatus?.rate_limits && Object.entries(systemStatus.rate_limits).map(([name, data]: [string, any]) => (
              <RateLimitGauge 
                key={name}
                name={name}
                utilization={data.utilization_pct || 0}
                remaining={data.calls_remaining}
              />
            ))}
            {(!systemStatus?.rate_limits || Object.keys(systemStatus.rate_limits).length === 0) && (
              <p className="text-sm text-muted-foreground text-center py-2">
                No rate limit data available
              </p>
            )}
          </div>
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
      </CardContent>
    </Card>
  );
}

export default SystemStatusPanel;
