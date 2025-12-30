/**
 * AlertFeed
 * 
 * Displays active alerts with priority color-coding and actions.
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  AlertTriangle, 
  Bell, 
  Check, 
  CheckCheck,
  Clock,
  XCircle
} from 'lucide-react';
import useSWR, { mutate } from 'swr';
import { formatDistanceToNow } from 'date-fns';
import { API_BASE_URL } from '@/lib/api-config';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface Alert {
  id: string;
  timestamp: string;
  priority: 'P0' | 'P1' | 'P2';
  category: string;
  title: string;
  details?: Record<string, any>;
  acknowledged: boolean;
  resolved: boolean;
}

interface AlertFeedProps {
  limit?: number;
  compact?: boolean;
}

function getPriorityStyles(priority: string) {
  switch (priority) {
    case 'P0':
      return {
        badge: 'bg-red-500 text-white',
        border: 'border-l-4 border-l-red-500',
        icon: <XCircle className="h-4 w-4 text-red-500" />,
      };
    case 'P1':
      return {
        badge: 'bg-yellow-500 text-black',
        border: 'border-l-4 border-l-yellow-500',
        icon: <AlertTriangle className="h-4 w-4 text-yellow-500" />,
      };
    case 'P2':
    default:
      return {
        badge: 'bg-blue-500 text-white',
        border: 'border-l-4 border-l-blue-500',
        icon: <Bell className="h-4 w-4 text-blue-500" />,
      };
  }
}

function AlertItem({ 
  alert, 
  compact,
  onAcknowledge,
  onResolve,
}: { 
  alert: Alert; 
  compact?: boolean;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
}) {
  const styles = getPriorityStyles(alert.priority);
  const timeAgo = formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true });
  
  return (
    <div className={`p-3 bg-card rounded-lg ${styles.border} ${alert.acknowledged ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          {styles.icon}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={styles.badge}>{alert.priority}</Badge>
              <Badge variant="outline" className="text-xs">
                {alert.category}
              </Badge>
              {alert.acknowledged && (
                <Badge variant="secondary" className="text-xs">
                  <Check className="h-3 w-3 mr-1" />
                  ACK
                </Badge>
              )}
            </div>
            <p className="font-medium mt-1 truncate">{alert.title}</p>
            {!compact && alert.details && (
              <pre className="text-xs text-muted-foreground mt-1 bg-muted p-2 rounded overflow-auto max-h-20">
                {JSON.stringify(alert.details, null, 2)}
              </pre>
            )}
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {timeAgo}
            </p>
          </div>
        </div>
        
        {!compact && !alert.resolved && (
          <div className="flex flex-col gap-1">
            {!alert.acknowledged && (
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => onAcknowledge(alert.id)}
              >
                <Check className="h-3 w-3" />
              </Button>
            )}
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => onResolve(alert.id)}
            >
              <CheckCheck className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export function AlertFeed({ limit = 50, compact = false }: AlertFeedProps) {
  const { data: alerts, error, isLoading } = useSWR<Alert[]>(
    `${API_BASE_URL}/monitoring/alerts?resolved=false&limit=${limit}`,
    fetcher,
    { refreshInterval: 10000 }
  );
  
  const handleAcknowledge = async (alertId: string) => {
    try {
      await fetch(`${API_BASE_URL}/monitoring/alerts/${alertId}/acknowledge`, {
        method: 'POST',
      });
      mutate(`${API_BASE_URL}/monitoring/alerts?resolved=false&limit=${limit}`);
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    }
  };
  
  const handleResolve = async (alertId: string) => {
    try {
      await fetch(`${API_BASE_URL}/monitoring/alerts/${alertId}/resolve`, {
        method: 'POST',
      });
      mutate(`${API_BASE_URL}/monitoring/alerts?resolved=false&limit=${limit}`);
    } catch (error) {
      console.error('Failed to resolve alert:', error);
    }
  };
  
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Alerts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-3">
            <div className="h-16 bg-muted rounded" />
            <div className="h-16 bg-muted rounded" />
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
            <AlertTriangle className="h-5 w-5" />
            Alerts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-center text-muted-foreground py-4">
            Failed to load alerts
          </p>
        </CardContent>
      </Card>
    );
  }
  
  const sortedAlerts = [...(alerts || [])].sort((a, b) => {
    // Sort by priority first, then by time
    const priorityOrder = { P0: 0, P1: 1, P2: 2 };
    const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
    if (priorityDiff !== 0) return priorityDiff;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Alerts
          </span>
          {alerts && alerts.length > 0 && (
            <Badge variant="secondary">{alerts.length} active</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {sortedAlerts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Bell className="h-12 w-12 mx-auto mb-2 opacity-50" />
            <p>No active alerts</p>
            <p className="text-sm">System is running normally</p>
          </div>
        ) : (
          <ScrollArea className={compact ? "h-[300px]" : "h-[500px]"}>
            <div className="space-y-2">
              {sortedAlerts.map(alert => (
                <AlertItem 
                  key={alert.id} 
                  alert={alert} 
                  compact={compact}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                />
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

export default AlertFeed;
