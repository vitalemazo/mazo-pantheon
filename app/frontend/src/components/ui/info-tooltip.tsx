/**
 * InfoTooltip - Reusable help tooltip component
 * 
 * Use this to add contextual help throughout the application.
 * Displays a small info icon that shows a tooltip on hover.
 */

import * as React from "react";
import { HelpCircle, Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface InfoTooltipProps {
  content: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
  iconClassName?: string;
  variant?: "info" | "help";
  size?: "sm" | "md" | "lg";
}

export function InfoTooltip({
  content,
  side = "top",
  className,
  iconClassName,
  variant = "help",
  size = "sm",
}: InfoTooltipProps) {
  const Icon = variant === "help" ? HelpCircle : Info;
  
  const sizeClasses = {
    sm: "h-3.5 w-3.5",
    md: "h-4 w-4",
    lg: "h-5 w-5",
  };

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className={cn("inline-flex cursor-help", className)}>
            <Icon 
              className={cn(
                sizeClasses[size],
                "text-slate-400 hover:text-slate-300 transition-colors",
                iconClassName
              )} 
            />
          </span>
        </TooltipTrigger>
        <TooltipContent 
          side={side} 
          className="max-w-xs bg-slate-800 text-slate-100 border-slate-700 p-3 text-sm"
        >
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * LabelWithTooltip - Label with integrated help tooltip
 */
interface LabelWithTooltipProps {
  label: string;
  tooltip: React.ReactNode;
  className?: string;
  required?: boolean;
}

export function LabelWithTooltip({
  label,
  tooltip,
  className,
  required,
}: LabelWithTooltipProps) {
  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <span>{label}</span>
      {required && <span className="text-red-400">*</span>}
      <InfoTooltip content={tooltip} />
    </div>
  );
}

/**
 * Predefined tooltip content for common concepts
 */
export const TOOLTIP_CONTENT = {
  // Trading concepts
  autonomousMode: (
    <div className="space-y-2">
      <p className="font-semibold">Autonomous Trading Mode</p>
      <p>When enabled, the AI team automatically:</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li>Scans markets every 30 minutes</li>
        <li>Generates trading signals</li>
        <li>Validates with Mazo research</li>
        <li>Executes approved trades</li>
      </ul>
      <p className="text-amber-400 text-xs mt-2">⚠️ Real money will be used for trades</p>
    </div>
  ),
  
  budgetAllocation: (
    <div className="space-y-2">
      <p className="font-semibold">AI Trading Budget</p>
      <p>The percentage of your portfolio the AI can use for new positions.</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li><strong>Conservative (10-20%):</strong> Lower risk</li>
        <li><strong>Balanced (25-35%):</strong> Moderate exposure</li>
        <li><strong>Aggressive (40%+):</strong> Higher risk/reward</li>
      </ul>
    </div>
  ),
  
  tradingPipeline: (
    <div className="space-y-2">
      <p className="font-semibold">5-Stage Trading Pipeline</p>
      <ol className="list-decimal list-inside space-y-1 text-xs">
        <li><strong>Scan:</strong> Strategy engine screens tickers</li>
        <li><strong>Research:</strong> Mazo validates opportunities</li>
        <li><strong>Analyze:</strong> 18 AI analysts evaluate</li>
        <li><strong>Decide:</strong> Portfolio Manager makes final call</li>
        <li><strong>Execute:</strong> Alpaca executes the trade</li>
      </ol>
    </div>
  ),
  
  dryRun: (
    <div className="space-y-2">
      <p className="font-semibold">Dry Run Mode</p>
      <p>Simulates the full trading cycle without placing real orders.</p>
      <p className="text-xs text-emerald-400">✓ Safe for testing and learning</p>
    </div>
  ),
  
  liveActivity: (
    <div className="space-y-2">
      <p className="font-semibold">Live Activity Feed</p>
      <p>Real-time stream of AI team actions:</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li>Workflow events (start/complete)</li>
        <li>Agent signals (bullish/bearish)</li>
        <li>PM decisions (buy/sell/hold)</li>
        <li>Trade executions</li>
      </ul>
    </div>
  ),
  
  positionMonitor: (
    <div className="space-y-2">
      <p className="font-semibold">Position Monitor</p>
      <p>Automatically enforces risk limits every 5 minutes:</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li>Stop-loss: Closes losing positions</li>
        <li>Take-profit: Locks in gains</li>
        <li>Trailing stops: Protects profits</li>
      </ul>
    </div>
  ),
  
  // Agent concepts
  agentAccuracy: (
    <div className="space-y-2">
      <p className="font-semibold">Agent Accuracy</p>
      <p>Percentage of signals that led to profitable trades when followed.</p>
      <p className="text-xs text-slate-400">Calculated from closed trades only.</p>
      <p className="text-xs text-slate-400">Shows "N/A" until trades close.</p>
    </div>
  ),
  
  agentConfidence: (
    <div className="space-y-2">
      <p className="font-semibold">Confidence Score</p>
      <p>How certain the agent is about its signal (0-100%).</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li><strong>80%+:</strong> High conviction</li>
        <li><strong>60-80%:</strong> Moderate confidence</li>
        <li><strong>&lt;60%:</strong> Low confidence</li>
      </ul>
    </div>
  ),
  
  consensus: (
    <div className="space-y-2">
      <p className="font-semibold">Agent Consensus</p>
      <p>Agreement level among the 18 AI analysts.</p>
      <p className="text-xs">Higher consensus = stronger signal.</p>
    </div>
  ),
  
  // Metrics
  winRate: (
    <div className="space-y-2">
      <p className="font-semibold">Win Rate</p>
      <p>Percentage of trades that were profitable.</p>
      <p className="text-xs text-slate-400">Win Rate = Winners ÷ Total Trades</p>
    </div>
  ),
  
  sharpeRatio: (
    <div className="space-y-2">
      <p className="font-semibold">Sharpe Ratio</p>
      <p>Risk-adjusted return measure.</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li><strong>&gt;2:</strong> Excellent</li>
        <li><strong>1-2:</strong> Good</li>
        <li><strong>&lt;1:</strong> Needs improvement</li>
      </ul>
    </div>
  ),
  
  realizedPnL: (
    <div className="space-y-2">
      <p className="font-semibold">Realized P&L</p>
      <p>Profit or loss from closed positions.</p>
      <p className="text-xs text-slate-400">Only updates when trades close.</p>
    </div>
  ),
  
  unrealizedPnL: (
    <div className="space-y-2">
      <p className="font-semibold">Unrealized P&L</p>
      <p>Current profit/loss on open positions.</p>
      <p className="text-xs text-slate-400">Changes with market prices.</p>
    </div>
  ),
  
  // Monitoring
  staleData: (
    <div className="space-y-2">
      <p className="font-semibold">Stale Data Warning</p>
      <p>Data hasn't been updated recently.</p>
      <p className="text-xs text-amber-400">May indicate API issues or market closure.</p>
    </div>
  ),
  
  rateLimit: (
    <div className="space-y-2">
      <p className="font-semibold">API Rate Limit</p>
      <p>Usage of allowed API calls per time window.</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li><strong>Green:</strong> Healthy usage</li>
        <li><strong>Yellow:</strong> Approaching limit</li>
        <li><strong>Red:</strong> Near/at limit</li>
      </ul>
    </div>
  ),
  
  schedulerHeartbeat: (
    <div className="space-y-2">
      <p className="font-semibold">Scheduler Heartbeat</p>
      <p>Background task scheduler status.</p>
      <p className="text-xs">Should update every 5 minutes during market hours.</p>
    </div>
  ),
  
  // Alerts
  alertPriority: (
    <div className="space-y-2">
      <p className="font-semibold">Alert Priority Levels</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li><strong>P0 (Critical):</strong> Immediate action required</li>
        <li><strong>P1 (High):</strong> Important, review soon</li>
        <li><strong>P2 (Medium):</strong> Informational</li>
      </ul>
    </div>
  ),
};

export default InfoTooltip;
