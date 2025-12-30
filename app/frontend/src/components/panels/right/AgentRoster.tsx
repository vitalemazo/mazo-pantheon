/**
 * Agent Roster
 * 
 * Displays all 20 AI agents with their current status and last signal.
 * Part of the Intelligence Panel (right sidebar).
 */

import { cn } from '@/lib/utils';
import {
  AGENT_ROSTER,
  getSignalBgColor,
  getSignalColor,
} from '@/types/ai-transparency';
import { useDataStore } from '@/services/data-hydration-service';
import {
  Bot,
  Brain,
  CheckCircle2,
  Clock,
  AlertCircle,
  Users,
  Briefcase,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface AgentRosterProps {
  className?: string;
}

export function AgentRoster({ className }: AgentRosterProps) {
  // Get agent statuses from global store
  const agentStatuses = useDataStore((state) => state.agentStatuses);
  const selectedAgentId = useDataStore((state) => state.selectedAgentId);
  const setSelectedAgentId = useDataStore((state) => state.setSelectedAgentId);
  const workflowProgress = useDataStore((state) => state.liveWorkflowProgress);

  // Group agents by category
  const analysts = AGENT_ROSTER.filter((a) => a.category === 'analyst');
  const research = AGENT_ROSTER.filter((a) => a.category === 'research');
  const managers = AGENT_ROSTER.filter((a) => a.category === 'manager');

  // Calculate signal distribution
  const signals = workflowProgress?.signals || {};
  const signalCounts = {
    bullish: 0,
    bearish: 0,
    neutral: 0,
  };

  Object.values(signals).forEach((s) => {
    if (s.signal === 'bullish' || s.signal === 'strong_buy') {
      signalCounts.bullish++;
    } else if (s.signal === 'bearish' || s.signal === 'strong_sell') {
      signalCounts.bearish++;
    } else {
      signalCounts.neutral++;
    }
  });

  const totalSignals = Object.values(signals).length;

  return (
    <TooltipProvider delayDuration={300}>
      <div className={cn('flex flex-col h-full', className)}>
        {/* Signal Distribution */}
        {totalSignals > 0 && (
          <div className="p-3 border-b border-border/50">
            <div className="text-xs text-muted-foreground mb-2">Signal Consensus</div>
            <div className="flex gap-1 h-2 rounded-full overflow-hidden bg-background/50">
              {signalCounts.bullish > 0 && (
                <div
                  className="bg-green-500 transition-all"
                  style={{ width: `${(signalCounts.bullish / totalSignals) * 100}%` }}
                />
              )}
              {signalCounts.neutral > 0 && (
                <div
                  className="bg-slate-500 transition-all"
                  style={{ width: `${(signalCounts.neutral / totalSignals) * 100}%` }}
                />
              )}
              {signalCounts.bearish > 0 && (
                <div
                  className="bg-red-500 transition-all"
                  style={{ width: `${(signalCounts.bearish / totalSignals) * 100}%` }}
                />
              )}
            </div>
            <div className="flex justify-between mt-1 text-[10px] text-muted-foreground">
              <span className="text-green-400">{signalCounts.bullish} Bullish</span>
              <span className="text-slate-400">{signalCounts.neutral} Neutral</span>
              <span className="text-red-400">{signalCounts.bearish} Bearish</span>
            </div>
          </div>
        )}

        {/* Agent List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-3">
          {/* Analysts */}
          <AgentGroup
            title="Analyst Agents"
            icon={<Users className="w-3 h-3" />}
            agents={analysts}
            agentStatuses={agentStatuses}
            signals={signals}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
          />

          {/* Research */}
          <AgentGroup
            title="Research"
            icon={<Brain className="w-3 h-3" />}
            agents={research}
            agentStatuses={agentStatuses}
            signals={signals}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
          />

          {/* Management */}
          <AgentGroup
            title="Management"
            icon={<Briefcase className="w-3 h-3" />}
            agents={managers}
            agentStatuses={agentStatuses}
            signals={signals}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
          />
        </div>

        {/* Selected Agent Detail */}
        {selectedAgentId && (
          <SelectedAgentDetail
            agentId={selectedAgentId}
            signal={signals[selectedAgentId]}
            onClose={() => setSelectedAgentId(null)}
          />
        )}
      </div>
    </TooltipProvider>
  );
}

// Agent group component
function AgentGroup({
  title,
  icon,
  agents,
  agentStatuses,
  signals,
  selectedAgentId,
  onSelectAgent,
}: {
  title: string;
  icon: React.ReactNode;
  agents: typeof AGENT_ROSTER;
  agentStatuses: Record<string, string>;
  signals: Record<string, any>;
  selectedAgentId: string | null;
  onSelectAgent: (id: string | null) => void;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5 px-1">
        {icon}
        <span>{title}</span>
        <Badge variant="secondary" className="text-[10px] px-1 py-0 ml-auto">
          {agents.length}
        </Badge>
      </div>
      <div className="grid grid-cols-2 gap-1">
        {agents.map((agent) => {
          const status = agentStatuses[agent.id] || 'idle';
          const signal = signals[agent.id];

          return (
            <Tooltip key={agent.id}>
              <TooltipTrigger asChild>
                <button
                  onClick={() => onSelectAgent(selectedAgentId === agent.id ? null : agent.id)}
                  className={cn(
                    'flex items-center gap-1.5 p-1.5 rounded text-left transition-all',
                    'hover:bg-background/50 border border-transparent',
                    selectedAgentId === agent.id && 'border-cyan-500/50 bg-cyan-500/10',
                    signal && getSignalBgColor(signal.signal)
                  )}
                >
                  <StatusIndicator status={status} />
                  <span className="text-xs truncate flex-1">{agent.shortName}</span>
                  {signal && (
                    <span className={cn('text-[10px]', getSignalColor(signal.signal))}>
                      {signal.confidence}%
                    </span>
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent side="left">
                <div className="text-xs">
                  <div className="font-medium">{agent.name}</div>
                  <div className="text-muted-foreground">{agent.description}</div>
                  {signal && (
                    <div className={cn('mt-1', getSignalColor(signal.signal))}>
                      Signal: {signal.signal} ({signal.confidence}%)
                    </div>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}

// Status indicator
function StatusIndicator({ status }: { status: string }) {
  switch (status) {
    case 'analyzing':
      return <Clock className="w-3 h-3 text-cyan-400 animate-spin" />;
    case 'complete':
      return <CheckCircle2 className="w-3 h-3 text-green-400" />;
    case 'error':
      return <AlertCircle className="w-3 h-3 text-red-400" />;
    default:
      return <div className="w-3 h-3 rounded-full bg-slate-600" />;
  }
}

// Selected agent detail
function SelectedAgentDetail({
  agentId,
  signal,
  onClose,
}: {
  agentId: string;
  signal?: any;
  onClose: () => void;
}) {
  const agent = AGENT_ROSTER.find((a) => a.id === agentId);
  if (!agent) return null;

  return (
    <div className="border-t border-border/50 p-3 bg-background/30">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium">{agent.name}</span>
        </div>
        <button onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">
          Close
        </button>
      </div>
      <p className="text-xs text-muted-foreground mb-2">{agent.description}</p>
      {signal ? (
        <div className="space-y-2">
          <div
            className={cn(
              'flex items-center justify-between p-2 rounded border',
              getSignalBgColor(signal.signal)
            )}
          >
            <span className={cn('text-sm font-medium', getSignalColor(signal.signal))}>
              {signal.signal.toUpperCase()}
            </span>
            <span className="text-sm">{signal.confidence}% confidence</span>
          </div>
          {signal.reasoning && (
            <div className="text-xs text-muted-foreground bg-background/50 p-2 rounded">
              {signal.reasoning}
            </div>
          )}
        </div>
      ) : (
        <div className="text-xs text-muted-foreground italic">No signal yet</div>
      )}
    </div>
  );
}
