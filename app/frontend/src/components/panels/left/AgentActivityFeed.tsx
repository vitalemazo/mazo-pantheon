/**
 * Agent Activity Feed
 * 
 * Real-time timeline showing AI agent activities, decisions, and execution events.
 * Replaces the old "Flows" sidebar with a transparency-focused activity log.
 */

import { useResizable } from '@/hooks/use-resizable';
import { cn } from '@/lib/utils';
import { 
  AgentActivityEntry, 
  ActivityFilters,
  getActivityColor,
  getSignalColor,
} from '@/types/ai-transparency';
import { 
  Activity, 
  Bot, 
  Brain, 
  ChevronDown, 
  ChevronRight, 
  Filter, 
  Pin, 
  Search,
  TrendingUp,
  Zap,
  AlertCircle,
  CheckCircle2,
  Clock,
  Trash2,
  Download
} from 'lucide-react';
import { ReactNode, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useDataStore } from '@/services/data-hydration-service';

interface AgentActivityFeedProps {
  children?: ReactNode;
  isCollapsed: boolean;
  onCollapse: () => void;
  onExpand: () => void;
  onWidthChange?: (width: number) => void;
}

export function AgentActivityFeed({
  isCollapsed,
  onWidthChange,
}: AgentActivityFeedProps) {
  const { width, isDragging, elementRef, startResize } = useResizable({
    defaultWidth: 320,
    minWidth: 280,
    maxWidth: window.innerWidth * 0.5,
    side: 'left',
  });

  // Get activity log from global store
  const activities = useDataStore((state) => state.agentActivityLog);
  const clearActivities = useDataStore((state) => state.clearAgentActivityLog);
  const togglePinActivity = useDataStore((state) => state.togglePinActivity);

  // Local UI state
  const [filters, setFilters] = useState<ActivityFilters>({
    showAgents: true,
    showMazo: true,
    showPM: true,
    showExecution: true,
    showErrors: true,
    searchQuery: '',
  });
  const [showFilters, setShowFilters] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const isHovering = useRef(false);

  // Notify parent of width changes
  useEffect(() => {
    onWidthChange?.(width);
  }, [width, onWidthChange]);

  // Auto-scroll when new activities arrive
  useEffect(() => {
    if (autoScroll && !isHovering.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activities, autoScroll]);

  // Filter activities
  const filteredActivities = activities.filter((activity) => {
    // Search filter
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      if (
        !activity.message.toLowerCase().includes(query) &&
        !activity.ticker?.toLowerCase().includes(query) &&
        !activity.agentName?.toLowerCase().includes(query)
      ) {
        return false;
      }
    }

    // Category filters
    const isAgent = activity.type.startsWith('agent_');
    const isMazo = activity.type.startsWith('mazo_');
    const isPM = activity.type.startsWith('pm_');
    const isExecution = activity.type.startsWith('trade_');
    const isError = activity.type === 'error';

    if (isAgent && !filters.showAgents) return false;
    if (isMazo && !filters.showMazo) return false;
    if (isPM && !filters.showPM) return false;
    if (isExecution && !filters.showExecution) return false;
    if (isError && !filters.showErrors) return false;

    return true;
  });

  // Toggle expanded state
  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Export activities as JSON
  const exportActivities = () => {
    const data = JSON.stringify(activities, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ai-activity-log-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Get icon for activity type
  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'ticker_input':
        return <TrendingUp className="w-3 h-3" />;
      case 'agent_start':
        return <Clock className="w-3 h-3 animate-spin" />;
      case 'agent_complete':
        return <CheckCircle2 className="w-3 h-3" />;
      case 'mazo_query':
      case 'mazo_response':
        return <Brain className="w-3 h-3" />;
      case 'pm_consolidating':
      case 'pm_decision':
        return <Bot className="w-3 h-3" />;
      case 'trade_attempt':
        return <Zap className="w-3 h-3" />;
      case 'trade_executed':
        return <CheckCircle2 className="w-3 h-3" />;
      case 'trade_failed':
      case 'error':
        return <AlertCircle className="w-3 h-3" />;
      default:
        return <Activity className="w-3 h-3" />;
    }
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div
        ref={elementRef}
        className={cn(
          'h-full bg-panel flex flex-col relative pt-5 border-r',
          isCollapsed ? 'shadow-lg' : ''
        )}
        style={{ width: `${width}px` }}
      >
        {/* Header */}
        <div className="px-3 pb-3 border-b border-border/50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium">AI Activity</span>
              {activities.length > 0 && (
                <Badge variant="secondary" className="text-xs px-1.5 py-0">
                  {activities.length}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setShowFilters(!showFilters)}
                  >
                    <Filter className={cn('w-3 h-3', showFilters && 'text-cyan-400')} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Toggle filters</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={exportActivities}
                  >
                    <Download className="w-3 h-3" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Export log</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={clearActivities}
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Clear log</TooltipContent>
              </Tooltip>
            </div>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
            <Input
              placeholder="Search activities..."
              value={filters.searchQuery}
              onChange={(e) => setFilters({ ...filters, searchQuery: e.target.value })}
              className="h-7 pl-7 text-xs bg-background/50"
            />
          </div>

          {/* Filters */}
          {showFilters && (
            <div className="mt-2 p-2 bg-background/50 rounded-md border border-border/50 space-y-1.5">
              <FilterCheckbox
                label="Agents"
                checked={filters.showAgents}
                onChange={(checked) => setFilters({ ...filters, showAgents: checked })}
                color="text-cyan-400"
              />
              <FilterCheckbox
                label="Mazo Research"
                checked={filters.showMazo}
                onChange={(checked) => setFilters({ ...filters, showMazo: checked })}
                color="text-purple-400"
              />
              <FilterCheckbox
                label="Portfolio Manager"
                checked={filters.showPM}
                onChange={(checked) => setFilters({ ...filters, showPM: checked })}
                color="text-yellow-400"
              />
              <FilterCheckbox
                label="Execution"
                checked={filters.showExecution}
                onChange={(checked) => setFilters({ ...filters, showExecution: checked })}
                color="text-emerald-400"
              />
              <FilterCheckbox
                label="Errors"
                checked={filters.showErrors}
                onChange={(checked) => setFilters({ ...filters, showErrors: checked })}
                color="text-red-400"
              />
            </div>
          )}
        </div>

        {/* Activity List */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto"
          onMouseEnter={() => (isHovering.current = true)}
          onMouseLeave={() => (isHovering.current = false)}
        >
          {filteredActivities.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-4">
              <Activity className="w-8 h-8 mb-2 opacity-50" />
              <p className="text-sm text-center">No activity yet</p>
              <p className="text-xs text-center mt-1 opacity-70">
                Run an analysis to see AI decisions in real-time
              </p>
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {filteredActivities.map((activity) => (
                <ActivityItem
                  key={activity.id}
                  activity={activity}
                  isExpanded={expandedIds.has(activity.id)}
                  onToggleExpand={() => toggleExpanded(activity.id)}
                  onTogglePin={() => togglePinActivity(activity.id)}
                  getIcon={getActivityIcon}
                />
              ))}
            </div>
          )}
        </div>

        {/* Auto-scroll indicator */}
        <div className="px-3 py-2 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={cn(
              'flex items-center gap-1 hover:text-foreground transition-colors',
              autoScroll && 'text-cyan-400'
            )}
          >
            <div className={cn('w-1.5 h-1.5 rounded-full', autoScroll ? 'bg-cyan-400' : 'bg-muted')} />
            Auto-scroll
          </button>
          <span>{filteredActivities.length} events</span>
        </div>

        {/* Resize handle */}
        {!isDragging && (
          <div
            className="absolute top-0 right-0 h-full w-1 cursor-ew-resize transition-all duration-150 z-10 hover:bg-cyan-500/50"
            onMouseDown={startResize}
          />
        )}
      </div>
    </TooltipProvider>
  );
}

// Filter checkbox component
function FilterCheckbox({
  label,
  checked,
  onChange,
  color,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  color: string;
}) {
  return (
    <label className="flex items-center gap-2 text-xs cursor-pointer hover:bg-background/50 p-1 rounded">
      <Checkbox
        checked={checked}
        onCheckedChange={onChange}
        className="h-3 w-3"
      />
      <span className={cn(checked ? color : 'text-muted-foreground')}>{label}</span>
    </label>
  );
}

// Activity item component
function ActivityItem({
  activity,
  isExpanded,
  onToggleExpand,
  onTogglePin,
  getIcon,
}: {
  activity: AgentActivityEntry;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onTogglePin: () => void;
  getIcon: (type: string) => ReactNode;
}) {
  const hasDetails = activity.details && Object.keys(activity.details).length > 0;
  const colorClass = getActivityColor(activity.type);
  const time = new Date(activity.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <div
      className={cn(
        'group rounded-md border border-transparent hover:border-border/50 transition-all',
        activity.isPinned && 'border-yellow-500/30 bg-yellow-500/5',
        isExpanded && 'bg-background/50'
      )}
    >
      {/* Main row */}
      <div
        className="flex items-start gap-2 p-2 cursor-pointer"
        onClick={hasDetails ? onToggleExpand : undefined}
      >
        {/* Expand indicator */}
        <div className="w-3 pt-0.5">
          {hasDetails ? (
            isExpanded ? (
              <ChevronDown className="w-3 h-3 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-3 h-3 text-muted-foreground" />
            )
          ) : null}
        </div>

        {/* Icon */}
        <div className={cn('pt-0.5', colorClass)}>{getIcon(activity.type)}</div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {activity.ticker && (
              <Badge variant="outline" className="text-[10px] px-1 py-0 font-mono">
                {activity.ticker}
              </Badge>
            )}
            {activity.agentName && (
              <span className="text-xs text-muted-foreground truncate">
                {activity.agentName}
              </span>
            )}
          </div>
          <p className="text-xs text-foreground/90 mt-0.5 line-clamp-2">{activity.message}</p>
          
          {/* Signal badge */}
          {activity.details?.signal && (
            <Badge
              variant="outline"
              className={cn(
                'mt-1 text-[10px] px-1.5 py-0',
                getSignalColor(activity.details.signal.signal)
              )}
            >
              {activity.details.signal.signal.toUpperCase()} ({activity.details.signal.confidence}%)
            </Badge>
          )}
        </div>

        {/* Time & actions */}
        <div className="flex flex-col items-end gap-1">
          <span className="text-[10px] text-muted-foreground">{time}</span>
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              'h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity',
              activity.isPinned && 'opacity-100 text-yellow-400'
            )}
            onClick={(e) => {
              e.stopPropagation();
              onTogglePin();
            }}
          >
            <Pin className="w-2.5 h-2.5" />
          </Button>
        </div>
      </div>

      {/* Expanded details */}
      {isExpanded && hasDetails && (
        <div className="px-4 pb-2 pl-8 space-y-2">
          {activity.details?.reasoning && (
            <div className="text-xs text-muted-foreground bg-background/50 p-2 rounded border border-border/30">
              <span className="text-foreground/70 font-medium">Reasoning: </span>
              {activity.details.reasoning}
            </div>
          )}
          {activity.details?.research && (
            <div className="text-xs text-muted-foreground bg-purple-500/5 p-2 rounded border border-purple-500/20">
              <span className="text-purple-400 font-medium">Research: </span>
              {activity.details.research.slice(0, 500)}
              {activity.details.research.length > 500 && '...'}
            </div>
          )}
          {activity.details?.duration && (
            <div className="text-[10px] text-muted-foreground">
              Duration: {activity.details.duration}ms
            </div>
          )}
          {activity.details?.error && (
            <div className="text-xs text-red-400 bg-red-500/10 p-2 rounded border border-red-500/20">
              {activity.details.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
