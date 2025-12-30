/**
 * TradeJournal
 * 
 * Displays trade history with full decision chain context.
 */

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { 
  History, 
  Search, 
  TrendingUp, 
  TrendingDown,
  ExternalLink,
  Clock
} from 'lucide-react';
import useSWR from 'swr';
import { formatDistanceToNow } from 'date-fns';
import { API_BASE_URL_URL } from '@/lib/api-config';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface Trade {
  order_id: string;
  timestamp: string;
  ticker: string;
  side: string;
  quantity: number;
  filled_avg_price: number;
  status: string;
  slippage_bps: number;
  fill_latency_ms: number;
}

export function TradeJournal() {
  const [searchTicker, setSearchTicker] = useState('');
  
  const { data, isLoading, error } = useSWR(
    `${API_BASE_URL}/monitoring/trades?limit=50${searchTicker ? `&ticker=${searchTicker}` : ''}`,
    fetcher,
    { refreshInterval: 30000 }
  );
  
  const trades = data?.trades || [];
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Trade Journal
          </CardTitle>
          <div className="relative w-48">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search ticker..."
              value={searchTicker}
              onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
              className="pl-8"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-10 bg-muted rounded" />
            <div className="h-10 bg-muted rounded" />
            <div className="h-10 bg-muted rounded" />
          </div>
        ) : trades.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <History className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No trades recorded yet</p>
            <p className="text-sm mt-2">
              Trade history will appear here once the monitoring system starts 
              logging executions.
            </p>
          </div>
        ) : (
          <ScrollArea className="h-[500px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Ticker</TableHead>
                  <TableHead>Side</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Slippage</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.map((trade: Trade) => (
                  <TableRow key={trade.order_id}>
                    <TableCell className="text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDistanceToNow(new Date(trade.timestamp), { addSuffix: true })}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">
                      {trade.ticker}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={trade.side === 'buy' ? 'default' : 'destructive'}
                        className="gap-1"
                      >
                        {trade.side === 'buy' ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        {trade.side.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {trade.quantity}
                    </TableCell>
                    <TableCell className="text-right">
                      ${trade.filled_avg_price?.toFixed(2) || '--'}
                    </TableCell>
                    <TableCell className="text-right">
                      {trade.slippage_bps !== undefined && trade.slippage_bps !== null ? (
                        <span className={
                          trade.slippage_bps > 25 ? 'text-red-500' :
                          trade.slippage_bps > 10 ? 'text-yellow-500' :
                          'text-green-500'
                        }>
                          {trade.slippage_bps.toFixed(1)} bps
                        </span>
                      ) : '--'}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          trade.status === 'filled' ? 'default' :
                          trade.status === 'rejected' ? 'destructive' :
                          'secondary'
                        }
                      >
                        {trade.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm">
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

export default TradeJournal;
