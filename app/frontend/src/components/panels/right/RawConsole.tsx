/**
 * Raw Console
 * 
 * Technical log output similar to browser dev tools.
 * Filterable by log level, searchable, and exportable.
 * Part of the Intelligence Panel (right sidebar).
 */

import { cn } from '@/lib/utils';
import { useDataStore } from '@/services/data-hydration-service';
import { ConsoleLogEntry, LogLevel } from '@/types/ai-transparency';
import {
  Terminal,
  Search,
  Trash2,
  Download,
  Filter,
  AlertCircle,
  AlertTriangle,
  Info,
  Bug,
  Copy,
  Check,
} from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';

interface RawConsoleProps {
  className?: string;
}

export function RawConsole({ className }: RawConsoleProps) {
  const logs = useDataStore((state) => state.consoleLogs);
  const clearLogs = useDataStore((state) => state.clearConsoleLogs);

  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [levelFilters, setLevelFilters] = useState<Record<LogLevel, boolean>>({
    debug: true,
    info: true,
    warn: true,
    error: true,
  });
  const [autoScroll, setAutoScroll] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const isHovering = useRef(false);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && !isHovering.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Filter logs
  const filteredLogs = logs.filter((log) => {
    if (!levelFilters[log.level]) return false;
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        log.message.toLowerCase().includes(query) ||
        log.source.toLowerCase().includes(query)
      );
    }
    return true;
  });

  // Export logs
  const exportLogs = () => {
    const data = logs
      .map((log) => `[${log.timestamp}] [${log.level.toUpperCase()}] [${log.source}] ${log.message}`)
      .join('\n');
    const blob = new Blob([data], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `console-log-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Copy single log
  const copyLog = (log: ConsoleLogEntry) => {
    navigator.clipboard.writeText(
      `[${log.timestamp}] [${log.level.toUpperCase()}] [${log.source}] ${log.message}`
    );
    setCopiedId(log.id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  // Get log level icon
  const getLevelIcon = (level: LogLevel) => {
    switch (level) {
      case 'error':
        return <AlertCircle className="w-3 h-3 text-red-400" />;
      case 'warn':
        return <AlertTriangle className="w-3 h-3 text-yellow-400" />;
      case 'info':
        return <Info className="w-3 h-3 text-blue-400" />;
      case 'debug':
        return <Bug className="w-3 h-3 text-slate-400" />;
    }
  };

  // Get log level color
  const getLevelColor = (level: LogLevel) => {
    switch (level) {
      case 'error':
        return 'text-red-400 bg-red-500/10';
      case 'warn':
        return 'text-yellow-400 bg-yellow-500/10';
      case 'info':
        return 'text-blue-400';
      case 'debug':
        return 'text-slate-500';
    }
  };

  return (
    <div className={cn('flex flex-col h-full font-mono text-xs', className)}>
      {/* Header */}
      <div className="p-2 border-b border-border/50 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-medium font-sans">Console</span>
            {logs.length > 0 && (
              <Badge variant="secondary" className="text-[10px] px-1 py-0">
                {logs.length}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className={cn('w-3 h-3', showFilters && 'text-cyan-400')} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={exportLogs}
            >
              <Download className="w-3 h-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={clearLogs}
            >
              <Trash2 className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
          <Input
            placeholder="Filter logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-6 pl-7 text-xs bg-background/50 font-mono"
          />
        </div>

        {/* Level Filters */}
        {showFilters && (
          <div className="flex items-center gap-3 font-sans">
            {(['error', 'warn', 'info', 'debug'] as LogLevel[]).map((level) => (
              <label key={level} className="flex items-center gap-1.5 cursor-pointer">
                <Checkbox
                  checked={levelFilters[level]}
                  onCheckedChange={(checked) =>
                    setLevelFilters({ ...levelFilters, [level]: !!checked })
                  }
                  className="h-3 w-3"
                />
                <span
                  className={cn(
                    'text-[10px] uppercase',
                    levelFilters[level] ? getLevelColor(level).split(' ')[0] : 'text-muted-foreground'
                  )}
                >
                  {level}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Log List */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-black/30"
        onMouseEnter={() => (isHovering.current = true)}
        onMouseLeave={() => (isHovering.current = false)}
      >
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-6 font-sans">
            <Terminal className="w-8 h-8 mb-2 opacity-30" />
            <p className="text-xs">No logs to display</p>
          </div>
        ) : (
          <div className="p-1">
            {filteredLogs.map((log) => (
              <div
                key={log.id}
                className={cn(
                  'group flex items-start gap-2 px-2 py-1 hover:bg-white/5 rounded',
                  getLevelColor(log.level)
                )}
              >
                {/* Level icon */}
                <div className="pt-0.5">{getLevelIcon(log.level)}</div>

                {/* Timestamp */}
                <span className="text-slate-600 flex-shrink-0">
                  {new Date(log.timestamp).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                  })}
                </span>

                {/* Source */}
                <span className="text-cyan-600 flex-shrink-0">[{log.source}]</span>

                {/* Message */}
                <span className="flex-1 break-all">{log.message}</span>

                {/* Copy button */}
                <button
                  onClick={() => copyLog(log)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:bg-white/10 rounded"
                >
                  {copiedId === log.id ? (
                    <Check className="w-3 h-3 text-green-400" />
                  ) : (
                    <Copy className="w-3 h-3 text-muted-foreground" />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-2 py-1 border-t border-border/50 flex items-center justify-between text-[10px] text-muted-foreground font-sans">
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={cn(
            'flex items-center gap-1 hover:text-foreground',
            autoScroll && 'text-cyan-400'
          )}
        >
          <div className={cn('w-1.5 h-1.5 rounded-full', autoScroll ? 'bg-cyan-400' : 'bg-muted')} />
          Auto-scroll
        </button>
        <span>{filteredLogs.length} logs</span>
      </div>
    </div>
  );
}
