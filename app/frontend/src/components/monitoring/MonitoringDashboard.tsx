/**
 * MonitoringDashboard
 * 
 * Main monitoring dashboard with tabs for different views:
 * - Overview: Key metrics and system status
 * - Alerts: Active and historical alerts
 * - Performance: P&L charts and agent performance
 * - Trades: Trade journal with decision chain
 */

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { RefreshCw, AlertTriangle, Activity, TrendingUp, History, Loader2 } from 'lucide-react';
import useSWR, { useSWRConfig } from 'swr';

import { SystemStatusPanel } from './SystemStatusPanel';
import { AlertFeed } from './AlertFeed';
import { PerformanceMetrics } from './PerformanceMetrics';
import { AgentPerformanceTable } from './AgentPerformanceTable';
import { TradeJournal } from './TradeJournal';
import { API_BASE_URL } from '@/lib/api-config';
import { useToastManager } from '@/hooks/use-toast-manager';
import { InfoTooltip, TOOLTIP_CONTENT, WithTooltip } from '@/components/ui/info-tooltip';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function MonitoringDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { mutate } = useSWRConfig();
  const { success: toastSuccess } = useToastManager();
  
  // Fetch alerts for badge count
  const { data: alerts } = useSWR(
    `${API_BASE_URL}/monitoring/alerts?resolved=false&limit=10`,
    fetcher,
    { refreshInterval: 30000 }
  );
  
  const activeAlertCount = alerts?.length || 0;
  const hasP0 = alerts?.some((a: any) => a.priority === 'P0');
  
  // Refresh all monitoring data without page reload
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      // Revalidate all SWR caches that match monitoring endpoints
      await mutate(
        (key) => typeof key === 'string' && key.includes('/monitoring/'),
        undefined,
        { revalidate: true }
      );
      // Also revalidate trading endpoints used by this dashboard
      await mutate(
        (key) => typeof key === 'string' && key.includes('/trading/'),
        undefined,
        { revalidate: true }
      );
      toastSuccess("Dashboard refreshed", "refresh-success");
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setIsRefreshing(false);
    }
  }, [mutate, toastSuccess]);
  
  return (
    <div className="h-full overflow-auto p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Monitoring Dashboard</h2>
          <p className="text-muted-foreground">
            System health, alerts, and performance metrics
          </p>
        </div>
        <WithTooltip content={TOOLTIP_CONTENT.refreshButton}>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </WithTooltip>
      </div>
      
      {/* P0 Alert Banner */}
      {hasP0 && (
        <Card className="border-red-500 bg-red-50 dark:bg-red-950">
          <CardContent className="py-3 flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <span className="font-medium text-red-700 dark:text-red-300">
              Critical alert(s) require immediate attention
            </span>
            <Button 
              variant="destructive" 
              size="sm" 
              className="ml-auto"
              onClick={() => setActiveTab('alerts')}
            >
              View Alerts
            </Button>
          </CardContent>
        </Card>
      )}
      
      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <WithTooltip content={TOOLTIP_CONTENT.monitoringOverview}>
            <TabsTrigger value="overview" className="gap-2">
              <Activity className="h-4 w-4" />
              Overview
            </TabsTrigger>
          </WithTooltip>
          <WithTooltip content={TOOLTIP_CONTENT.alertsTab}>
            <TabsTrigger value="alerts" className="gap-2">
              <AlertTriangle className="h-4 w-4" />
              Alerts
              {activeAlertCount > 0 && (
                <Badge 
                  variant={hasP0 ? "destructive" : "secondary"} 
                  className="ml-1"
                >
                  {activeAlertCount}
                </Badge>
              )}
            </TabsTrigger>
          </WithTooltip>
          <WithTooltip content={TOOLTIP_CONTENT.performanceTab}>
            <TabsTrigger value="performance" className="gap-2">
              <TrendingUp className="h-4 w-4" />
              Performance
            </TabsTrigger>
          </WithTooltip>
          <WithTooltip content={TOOLTIP_CONTENT.tradeJournalTab}>
            <TabsTrigger value="trades" className="gap-2">
              <History className="h-4 w-4" />
              Trade Journal
            </TabsTrigger>
          </WithTooltip>
        </TabsList>
        
        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SystemStatusPanel />
            <AlertFeed limit={5} compact />
          </div>
          <PerformanceMetrics />
        </TabsContent>
        
        {/* Alerts Tab */}
        <TabsContent value="alerts">
          <AlertFeed />
        </TabsContent>
        
        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-4">
          <PerformanceMetrics showCharts />
          <AgentPerformanceTable />
        </TabsContent>
        
        {/* Trade Journal Tab */}
        <TabsContent value="trades">
          <TradeJournal />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default MonitoringDashboard;
