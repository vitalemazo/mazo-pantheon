/**
 * MonitoringDashboard
 * 
 * Infrastructure-focused monitoring dashboard.
 * Answers "is the system healthy?" rather than duplicating trading UI.
 * 
 * What belongs here:
 * - System status (services, scheduler, database)
 * - Rate limits and API health
 * - Trading guardrails (PDT, position limits)
 * - Alerts feed
 * - Execution quality metrics (latency, fill rate, slippage)
 * 
 * What moved elsewhere:
 * - Trading data → Control Tower / Trading Workspace
 * - Agent leaderboards → Round Table
 * - Trade journal → Trading Workspace
 */

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  RefreshCw, 
  AlertTriangle, 
  Activity, 
  Gauge, 
  Loader2, 
  Rocket, 
  Briefcase,
  Info,
  ExternalLink,
  Layers,
  Users
} from 'lucide-react';
import useSWR, { useSWRConfig } from 'swr';

import { SystemStatusPanel } from './SystemStatusPanel';
import { AlertFeed } from './AlertFeed';
import { PerformanceMetrics } from './PerformanceMetrics';
import { API_BASE_URL } from '@/lib/api-config';
import { useToastManager } from '@/hooks/use-toast-manager';
import { WithTooltip, TOOLTIP_CONTENT } from '@/components/ui/info-tooltip';
import { useTabsContext } from '@/contexts/tabs-context';
import { TabService } from '@/services/tab-service';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function MonitoringDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showInfoBanner, setShowInfoBanner] = useState(true);
  const { mutate } = useSWRConfig();
  const { success: toastSuccess } = useToastManager();
  const { openTab } = useTabsContext();
  
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
      await mutate(
        (key) => typeof key === 'string' && key.includes('/monitoring/'),
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

  // Navigation handlers
  const openControlTower = () => {
    const tabData = TabService.createControlTowerTab();
    openTab(tabData);
  };

  const openTradingWorkspace = () => {
    const tabData = TabService.createTradingWorkspaceTab();
    openTab(tabData);
  };

  const openRoundTable = () => {
    const tabData = TabService.createRoundTableTab();
    openTab(tabData);
  };
  
  return (
    <div className="h-full overflow-auto p-4 space-y-4 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Info Banner */}
      {showInfoBanner && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Info className="w-5 h-5 text-slate-400" />
            <div>
              <span className="text-slate-300 font-medium">Monitoring = Infrastructure</span>
              <span className="text-slate-400 ml-2">
                System health, rate limits, and alerts. Trading data moved to Control Tower & Trading Workspace.
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={openControlTower}
              className="text-indigo-400 hover:text-indigo-300"
            >
              <Rocket className="w-4 h-4 mr-1" />
              Control Tower
            </Button>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={openTradingWorkspace}
              className="text-emerald-400 hover:text-emerald-300"
            >
              <Briefcase className="w-4 h-4 mr-1" />
              Trading Workspace
            </Button>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setShowInfoBanner(false)}
              className="text-slate-500"
            >
              Dismiss
            </Button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Monitoring Dashboard</h2>
          <p className="text-slate-400">
            System health • Rate limits • Alerts • Execution quality
          </p>
        </div>
        <WithTooltip content={TOOLTIP_CONTENT.refreshButton}>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="border-slate-600"
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
        <Card className="border-red-500 bg-red-500/10">
          <CardContent className="py-3 flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <span className="font-medium text-red-400">
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
      
      {/* Main Tabs - Simplified to 2 tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-slate-800 border border-slate-700">
          <WithTooltip content="System health, services, rate limits, and guardrails">
            <TabsTrigger value="overview" className="gap-2 data-[state=active]:bg-slate-700">
              <Activity className="h-4 w-4" />
              System Status
            </TabsTrigger>
          </WithTooltip>
          <WithTooltip content="Active and historical system alerts">
            <TabsTrigger value="alerts" className="gap-2 data-[state=active]:bg-slate-700">
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
          <WithTooltip content="Pipeline latency, fill rates, and Mazo effectiveness">
            <TabsTrigger value="metrics" className="gap-2 data-[state=active]:bg-slate-700">
              <Gauge className="h-4 w-4" />
              Execution Quality
            </TabsTrigger>
          </WithTooltip>
        </TabsList>
        
        {/* System Status Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SystemStatusPanel />
            <AlertFeed limit={5} compact />
          </div>
        </TabsContent>
        
        {/* Alerts Tab */}
        <TabsContent value="alerts">
          <AlertFeed />
        </TabsContent>
        
        {/* Execution Quality Tab */}
        <TabsContent value="metrics" className="space-y-4">
          <PerformanceMetrics showCharts />
          
          {/* CTA to trading pages */}
          <Card className="bg-slate-800/30 border-slate-700">
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Info className="w-5 h-5 text-slate-400" />
                  <span className="text-slate-400">
                    Looking for trading data, positions, or agent performance?
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={openControlTower}
                    className="border-indigo-500/50 text-indigo-400 hover:bg-indigo-500/10"
                  >
                    <Rocket className="w-4 h-4 mr-1" />
                    Control Tower
                    <ExternalLink className="w-3 h-3 ml-1" />
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={openTradingWorkspace}
                    className="border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/10"
                  >
                    <Briefcase className="w-4 h-4 mr-1" />
                    Trading Workspace
                    <ExternalLink className="w-3 h-3 ml-1" />
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={openRoundTable}
                    className="border-purple-500/50 text-purple-400 hover:bg-purple-500/10"
                  >
                    <Layers className="w-4 h-4 mr-1" />
                    Round Table
                    <ExternalLink className="w-3 h-3 ml-1" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default MonitoringDashboard;
