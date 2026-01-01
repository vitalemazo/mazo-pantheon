/**
 * AgentPerformanceTable
 * 
 * Displays agent performance metrics in a sortable table.
 * Shows stale indicators when agent data is outdated.
 */

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { 
  ArrowUpDown, 
  TrendingUp, 
  TrendingDown,
  Users,
  Clock,
  AlertTriangle
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import useSWR from 'swr';
import { API_BASE_URL } from '@/lib/api-config';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface AgentPerformance {
  agent_id: string;
  total_signals: number;
  accuracy: number;
  avg_confidence: number;
  bullish_signals: number;
  bearish_signals: number;
  last_signal_at?: string;
  is_stale?: boolean;
}

/**
 * Format relative time (e.g., "5m ago", "2h ago")
 */
function formatRelativeTime(isoString?: string | null): string {
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

type SortKey = 'agent_id' | 'total_signals' | 'accuracy' | 'avg_confidence';
type SortOrder = 'asc' | 'desc';

export function AgentPerformanceTable() {
  const [sortKey, setSortKey] = useState<SortKey>('accuracy');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  
  const { data: agents, isLoading, error } = useSWR<AgentPerformance[]>(
    `${API_BASE_URL}/monitoring/metrics/agents?days=30`,
    fetcher,
    { refreshInterval: 60000 }
  );
  
  const sortedAgents = useMemo(() => {
    if (!agents) return [];
    
    return [...agents].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortOrder === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      
      return sortOrder === 'asc' ? 
        (aVal as number) - (bVal as number) : 
        (bVal as number) - (aVal as number);
    });
  }, [agents, sortKey, sortOrder]);
  
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };
  
  const SortHeader = ({ column, label }: { column: SortKey; label: string }) => (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-3"
      onClick={() => handleSort(column)}
    >
      {label}
      <ArrowUpDown className="ml-1 h-3 w-3" />
    </Button>
  );
  
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Agent Performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-2">
            <div className="h-10 bg-muted rounded" />
            <div className="h-10 bg-muted rounded" />
            <div className="h-10 bg-muted rounded" />
          </div>
        </CardContent>
      </Card>
    );
  }
  
  if (error || !agents) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Agent Performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-center text-muted-foreground py-8">
            No agent performance data available yet
          </p>
        </CardContent>
      </Card>
    );
  }
  
  // Count stale agents
  const staleCount = sortedAgents.filter(a => a.is_stale).length;
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Agent Performance
          </span>
          <div className="flex items-center gap-2">
            {staleCount > 0 && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="text-amber-600 border-amber-400 bg-amber-50 gap-1">
                      <Clock className="h-3 w-3" />
                      {staleCount} stale
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{staleCount} agent(s) have no recent signals</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
            <Badge variant="secondary">{agents.length} agents</Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <TooltipProvider>
        {sortedAgents.length === 0 ? (
          <p className="text-center text-muted-foreground py-8">
            No agent performance data available yet.
            <br />
            Data will appear after trading cycles run.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <SortHeader column="agent_id" label="Agent" />
                </TableHead>
                <TableHead className="text-right">
                  <SortHeader column="total_signals" label="Signals" />
                </TableHead>
                <TableHead className="text-right">
                  <SortHeader column="accuracy" label="Accuracy" />
                </TableHead>
                <TableHead className="text-right">
                  <SortHeader column="avg_confidence" label="Confidence" />
                </TableHead>
                <TableHead className="text-center">Bias</TableHead>
                <TableHead className="text-center">Last Signal</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedAgents.map((agent) => {
                const bias = agent.bullish_signals > agent.bearish_signals ? 'bullish' : 
                             agent.bearish_signals > agent.bullish_signals ? 'bearish' : 'neutral';
                
                return (
                  <TableRow 
                    key={agent.agent_id}
                    className={agent.is_stale ? 'bg-amber-50/50' : ''}
                  >
                    <TableCell className="font-medium capitalize">
                      <div className="flex items-center gap-2">
                        {agent.agent_id.replace(/_/g, ' ')}
                        {agent.is_stale && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Clock className="h-3 w-3 text-amber-500 cursor-help" />
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>No signals in over 1 hour</p>
                              {agent.last_signal_at && (
                                <p className="text-xs">Last: {formatRelativeTime(agent.last_signal_at)}</p>
                              )}
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      {agent.total_signals}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={
                        agent.accuracy >= 0.6 ? 'text-green-500' :
                        agent.accuracy >= 0.4 ? 'text-yellow-500' :
                        'text-red-500'
                      }>
                        {(agent.accuracy * 100).toFixed(0)}%
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {agent.avg_confidence.toFixed(0)}%
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge 
                        variant={
                          bias === 'bullish' ? 'default' :
                          bias === 'bearish' ? 'destructive' :
                          'secondary'
                        }
                        className="gap-1"
                      >
                        {bias === 'bullish' && <TrendingUp className="h-3 w-3" />}
                        {bias === 'bearish' && <TrendingDown className="h-3 w-3" />}
                        {bias}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center text-xs text-muted-foreground">
                      {agent.last_signal_at ? formatRelativeTime(agent.last_signal_at) : 'never'}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
        </TooltipProvider>
      </CardContent>
    </Card>
  );
}

export default AgentPerformanceTable;
