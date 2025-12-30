/**
 * Decision Tree
 * 
 * Visual breakdown of how the final trading decision was reached.
 * Shows agent signals, PM reasoning, and confidence scores.
 * Part of the Intelligence Panel (right sidebar).
 */

import { cn } from '@/lib/utils';
import { useDataStore } from '@/services/data-hydration-service';
import {
  AGENT_ROSTER,
  getSignalColor,
  getSignalBgColor,
} from '@/types/ai-transparency';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Bot,
  Brain,
  Target,
  ChevronRight,
  Users,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface DecisionTreeProps {
  className?: string;
}

export function DecisionTree({ className }: DecisionTreeProps) {
  const workflowProgress = useDataStore((state) => state.liveWorkflowProgress);
  const signals = workflowProgress?.signals || {};
  const finalDecision = workflowProgress?.finalDecision;

  // Count signals by type
  const signalCounts = {
    bullish: 0,
    bearish: 0,
    neutral: 0,
  };

  const agentSignals = Object.entries(signals).map(([agentId, signal]) => {
    const agent = AGENT_ROSTER.find((a) => a.id === agentId);
    if (signal.signal === 'bullish' || signal.signal === 'strong_buy') {
      signalCounts.bullish++;
    } else if (signal.signal === 'bearish' || signal.signal === 'strong_sell') {
      signalCounts.bearish++;
    } else {
      signalCounts.neutral++;
    }
    return { agent, signal };
  });

  if (Object.keys(signals).length === 0 && !finalDecision) {
    return (
      <div className={cn('flex flex-col items-center justify-center h-full text-muted-foreground p-6', className)}>
        <Target className="w-12 h-12 mb-3 opacity-30" />
        <p className="text-sm text-center font-medium">No Decisions Yet</p>
        <p className="text-xs text-center mt-1 opacity-70">
          Decision tree will appear after running an analysis
        </p>
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full overflow-y-auto', className)}>
      {/* Final Decision */}
      {finalDecision && (
        <div className="p-3 border-b border-border/50">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-medium">Final Decision</span>
          </div>
          <div
            className={cn(
              'p-3 rounded-lg border text-center',
              finalDecision.action === 'BUY' && 'bg-green-500/10 border-green-500/50',
              finalDecision.action === 'SELL' && 'bg-red-500/10 border-red-500/50',
              finalDecision.action === 'HOLD' && 'bg-slate-500/10 border-slate-500/50'
            )}
          >
            <div className="flex items-center justify-center gap-2 mb-1">
              {finalDecision.action === 'BUY' && <TrendingUp className="w-5 h-5 text-green-400" />}
              {finalDecision.action === 'SELL' && <TrendingDown className="w-5 h-5 text-red-400" />}
              {finalDecision.action === 'HOLD' && <Minus className="w-5 h-5 text-slate-400" />}
              <span
                className={cn(
                  'text-xl font-bold',
                  finalDecision.action === 'BUY' && 'text-green-400',
                  finalDecision.action === 'SELL' && 'text-red-400',
                  finalDecision.action === 'HOLD' && 'text-slate-400'
                )}
              >
                {finalDecision.action}
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              {finalDecision.confidence}% confidence
            </div>
          </div>
          {finalDecision.reasoning && (
            <div className="mt-2 text-xs text-muted-foreground bg-background/50 p-2 rounded border border-border/30">
              <span className="text-foreground/70 font-medium">PM Reasoning: </span>
              {finalDecision.reasoning}
            </div>
          )}
        </div>
      )}

      {/* Signal Summary */}
      <div className="p-3 border-b border-border/50">
        <div className="flex items-center gap-2 mb-2">
          <Users className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium">Agent Signals</span>
          <Badge variant="secondary" className="text-xs ml-auto">
            {Object.keys(signals).length} agents
          </Badge>
        </div>

        {/* Signal breakdown bars */}
        <div className="space-y-2">
          <SignalBar
            label="Bullish"
            count={signalCounts.bullish}
            total={Object.keys(signals).length}
            color="bg-green-500"
            textColor="text-green-400"
            icon={<TrendingUp className="w-3 h-3" />}
          />
          <SignalBar
            label="Neutral"
            count={signalCounts.neutral}
            total={Object.keys(signals).length}
            color="bg-slate-500"
            textColor="text-slate-400"
            icon={<Minus className="w-3 h-3" />}
          />
          <SignalBar
            label="Bearish"
            count={signalCounts.bearish}
            total={Object.keys(signals).length}
            color="bg-red-500"
            textColor="text-red-400"
            icon={<TrendingDown className="w-3 h-3" />}
          />
        </div>
      </div>

      {/* Individual Agent Signals */}
      <div className="flex-1 p-3">
        <div className="text-xs text-muted-foreground mb-2">Individual Signals</div>
        <div className="space-y-1">
          {agentSignals
            .sort((a, b) => (b.signal.confidence || 0) - (a.signal.confidence || 0))
            .map(({ agent, signal }) => (
              <div
                key={agent?.id || 'unknown'}
                className={cn(
                  'flex items-center gap-2 p-2 rounded border text-xs',
                  getSignalBgColor(signal.signal)
                )}
              >
                <div className="flex-1 min-w-0">
                  <span className="font-medium truncate">
                    {agent?.shortName || 'Unknown'}
                  </span>
                </div>
                <div className={cn('flex items-center gap-1', getSignalColor(signal.signal))}>
                  {signal.signal === 'bullish' || signal.signal === 'strong_buy' ? (
                    <TrendingUp className="w-3 h-3" />
                  ) : signal.signal === 'bearish' || signal.signal === 'strong_sell' ? (
                    <TrendingDown className="w-3 h-3" />
                  ) : (
                    <Minus className="w-3 h-3" />
                  )}
                  <span className="font-mono">{signal.confidence}%</span>
                </div>
              </div>
            ))}
        </div>
      </div>

      {/* Decision Flow */}
      <div className="p-3 border-t border-border/50 bg-background/30">
        <div className="text-xs text-muted-foreground mb-2">Decision Flow</div>
        <div className="flex items-center justify-center gap-1 text-[10px]">
          <div className="flex items-center gap-1 px-2 py-1 rounded bg-cyan-500/20 text-cyan-400">
            <Bot className="w-3 h-3" />
            <span>18 Agents</span>
          </div>
          <ChevronRight className="w-3 h-3 text-muted-foreground" />
          <div className="flex items-center gap-1 px-2 py-1 rounded bg-purple-500/20 text-purple-400">
            <Brain className="w-3 h-3" />
            <span>Mazo</span>
          </div>
          <ChevronRight className="w-3 h-3 text-muted-foreground" />
          <div className="flex items-center gap-1 px-2 py-1 rounded bg-yellow-500/20 text-yellow-400">
            <Target className="w-3 h-3" />
            <span>PM</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Signal bar component
function SignalBar({
  label,
  count,
  total,
  color,
  textColor,
  icon,
}: {
  label: string;
  count: number;
  total: number;
  color: string;
  textColor: string;
  icon: React.ReactNode;
}) {
  const percentage = total > 0 ? (count / total) * 100 : 0;

  return (
    <div className="flex items-center gap-2">
      <div className={cn('flex items-center gap-1 w-16', textColor)}>
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className="flex-1 h-2 bg-background/50 rounded-full overflow-hidden">
        <div
          className={cn('h-full transition-all', color)}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground w-8 text-right">{count}</span>
    </div>
  );
}
