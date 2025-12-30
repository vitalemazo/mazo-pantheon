/**
 * AgentPerformanceTable
 * 
 * Displays agent performance metrics in a sortable table.
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
  Users
} from 'lucide-react';
import useSWR from 'swr';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface AgentPerformance {
  agent_id: string;
  total_signals: number;
  accuracy: number;
  avg_confidence: number;
  bullish_signals: number;
  bearish_signals: number;
}

type SortKey = 'agent_id' | 'total_signals' | 'accuracy' | 'avg_confidence';
type SortOrder = 'asc' | 'desc';

export function AgentPerformanceTable() {
  const [sortKey, setSortKey] = useState<SortKey>('accuracy');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  
  const { data: agents, isLoading, error } = useSWR<AgentPerformance[]>(
    `${API_BASE}/monitoring/metrics/agents?days=30`,
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
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Agent Performance
          </span>
          <Badge variant="secondary">{agents.length} agents</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
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
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedAgents.map((agent) => {
                const bias = agent.bullish_signals > agent.bearish_signals ? 'bullish' : 
                             agent.bearish_signals > agent.bullish_signals ? 'bearish' : 'neutral';
                
                return (
                  <TableRow key={agent.agent_id}>
                    <TableCell className="font-medium capitalize">
                      {agent.agent_id.replace(/_/g, ' ')}
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
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

export default AgentPerformanceTable;
