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
 * WithTooltip - Wrap any element with a tooltip
 * Use this to add tooltips to buttons, cards, tabs, etc.
 */
interface WithTooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  asChild?: boolean;
}

export function WithTooltip({
  content,
  children,
  side = "top",
  asChild = true,
}: WithTooltipProps) {
  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild={asChild}>
          {children}
        </TooltipTrigger>
        <TooltipContent 
          side={side} 
          className="max-w-xs bg-slate-800 text-slate-100 border-slate-700 p-3 text-sm z-50"
        >
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * MetricCard tooltip wrapper - for stat tiles
 */
interface MetricTooltipProps {
  title: string;
  description: string;
  example?: string;
}

export function MetricTooltip({ title, description, example }: MetricTooltipProps) {
  return (
    <div className="space-y-1">
      <p className="font-semibold">{title}</p>
      <p className="text-xs">{description}</p>
      {example && <p className="text-xs text-slate-400 italic">{example}</p>}
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
  
  // ===== TRADING DASHBOARD =====
  totalEquity: "Your total account value including cash and positions. Updates in real-time from Alpaca.",
  dayPnL: "Profit or loss for today. Includes both realized (closed trades) and unrealized (open positions).",
  buyingPower: "Available funds for new trades. Margin accounts may show 2x or 4x leverage.",
  cashBalance: "Liquid cash in your account, not invested in any positions.",
  openPositions: "Number of stocks you currently hold. Click to see details.",
  
  // Scheduler
  schedulerStatus: "Background task scheduler that runs automated trading cycles. Green = running, Grey = paused.",
  scheduledTasks: "Automated jobs like position monitoring, trade syncing, and AI trading cycles.",
  
  // Watchlist
  watchlist: "Stocks you're monitoring for potential trades. Add tickers to track opportunities.",
  
  // Buttons
  refreshButton: "Reload all data from the server. Data auto-refreshes every 30 seconds.",
  runAiCycle: "Runs the full AI trading pipeline: scan → research → analyze → decide → execute.",
  dryRunButton: "Simulates a trading cycle without placing real orders. Safe for testing.",
  toggleScheduler: "Start or stop the background scheduler. When running, automated tasks execute on schedule.",
  
  // ===== COMMAND CENTER =====
  commandCenterOverview: "Quick glance at your portfolio performance and recent AI activity.",
  tradeHistory: "Complete log of all trades executed by the AI team with entry/exit prices and P&L.",
  agentLeaderboard: "Rankings of all 18 AI analysts by accuracy and performance metrics.",
  scheduledTasksTab: "View and manage all background jobs and their execution status.",
  recentWorkflows: "History of recent AI trading cycles with step-by-step progress.",
  
  // Agent metrics
  totalSignals: "Total number of buy/sell/hold signals this agent has generated.",
  correctPredictions: "Signals that resulted in profitable trades when followed.",
  avgReturnWhenFollowed: "Average profit/loss from trades that followed this agent's signal.",
  bestCall: "This agent's most profitable trade recommendation.",
  worstCall: "This agent's least profitable trade recommendation.",
  
  // ===== MONITORING DASHBOARD =====
  monitoringOverview: "System health, API status, and key performance indicators at a glance.",
  alertsTab: "Active warnings and issues requiring attention. Resolve or acknowledge to clear.",
  performanceTab: "Detailed execution quality metrics and trade statistics.",
  tradeJournalTab: "Full audit trail of all trading activity with agent signals and reasoning.",
  
  // System status
  databaseStatus: "Connection status to PostgreSQL/TimescaleDB. Stores all trade history and metrics.",
  redisStatus: "In-memory cache for fast data access. Speeds up API responses.",
  alpacaStatus: "Connection to Alpaca brokerage for trading and market data.",
  
  // ===== PORTFOLIO HEALTH =====
  portfolioGrade: "Overall portfolio health score (A-F) based on diversification, risk, and performance.",
  riskLevel: "Estimated risk exposure: Low, Moderate, High, or Critical.",
  sectorExposure: "Breakdown of your holdings by market sector. Helps identify concentration risk.",
  topHoldings: "Your largest positions by market value. High concentration may increase risk.",
  mazoAnalysis: "AI-generated portfolio assessment with specific recommendations for improvement.",
  
  // ===== AI TEAM =====
  mazoResearch: "Mazo performs deep research using web search, financial data, and news analysis.",
  aiAnalysts: "18 AI agents modeled after famous investors (Buffett, Lynch, etc.) analyze each opportunity.",
  portfolioManager: "Makes final trade decisions based on agent consensus, risk limits, and portfolio state.",
  
  // ===== COMMON ACTIONS =====
  addToWatchlist: "Add this ticker to your monitoring list for future analysis.",
  removeFromWatchlist: "Remove this ticker from your watchlist.",
  viewDetails: "See full details including agent signals, research, and trade history.",
  exportData: "Download this data as CSV or JSON for external analysis.",
  
  // ===== SCHEDULED TASKS =====
  // Command Center shows "Next Scheduled Actions" - a quick glance at upcoming jobs
  // Trading Dashboard shows "Full Schedule" - complete list with cadence info for editing
  nextScheduledActions: "Shows the next 4-5 imminent scheduled jobs for a quick at-a-glance view. For the full schedule with editing options, see the Trading Dashboard.",
  fullSchedule: "Complete list of all scheduled jobs with trigger details (cron/interval). This is the authoritative source for managing automated tasks.",
  addScheduleButton: "Adds the default set of automated jobs: AI Trading Cycle, Position Monitor, Trade Sync, and Accuracy Backfill.",
};

/**
 * Descriptions for each scheduled task type.
 * Used in both Command Center (Next Actions) and Trading Dashboard (Full Schedule).
 * 
 * Why two views?
 * - Command Center "Next Scheduled Actions": Quick glance at what's running soon
 * - Trading Dashboard "Scheduled Tasks": Full schedule with cadence info for operators
 */
export const SCHEDULE_DESCRIPTIONS: Record<string, string> = {
  // Core trading jobs
  "AI Trading Cycle": "Runs the full autonomous pipeline every 30 minutes during market hours: scans tickers → Mazo validates → agents analyze → PM decides → Alpaca executes.",
  "Position Monitor": "Checks open positions every 5 minutes. Exits trades if stop-loss or take-profit levels are hit. Critical for risk management.",
  "Trade Sync": "Syncs executed Alpaca orders with local trade history every 10 minutes. Ensures P&L and metrics stay accurate.",
  "Accuracy Backfill": "Runs daily to mark agent predictions as correct/incorrect based on closed trade outcomes. Powers the agent accuracy metrics.",
  
  // Monitoring jobs
  "Scheduler Heartbeat": "Emits a heartbeat event every 5 minutes so the monitoring dashboard knows the scheduler is alive.",
  "Daily Performance": "Calculates and stores daily P&L snapshots at market close. Used for historical performance charts.",
  
  // Fallback for unknown jobs
  "default": "Automated background task managed by the scheduler.",
};

/**
 * Get the description for a scheduled task by name.
 * Falls back to a generic description if the task name is not recognized.
 */
export function getScheduleDescription(taskName: string): string {
  return SCHEDULE_DESCRIPTIONS[taskName] || SCHEDULE_DESCRIPTIONS["default"];
}

export default InfoTooltip;
