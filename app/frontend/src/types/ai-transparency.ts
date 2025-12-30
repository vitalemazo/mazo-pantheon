/**
 * AI Transparency Types
 * 
 * Types for the real-time agent activity feed and intelligence panel
 * that provide visibility into AI hedge fund decision-making.
 */

// ==================== AGENT DEFINITIONS ====================

export type AgentCategory = 'analyst' | 'research' | 'manager' | 'execution';

export interface AgentDefinition {
  id: string;
  name: string;
  shortName: string;
  category: AgentCategory;
  description: string;
  icon?: string;
}

// The 20 agents in the AI Hedge Fund
export const AGENT_ROSTER: AgentDefinition[] = [
  // Analyst Agents (18)
  { id: 'warren_buffett', name: 'Warren Buffett', shortName: 'Buffett', category: 'analyst', description: 'Value investing, economic moats' },
  { id: 'charlie_munger', name: 'Charlie Munger', shortName: 'Munger', category: 'analyst', description: 'Mental models, quality businesses' },
  { id: 'ben_graham', name: 'Ben Graham', shortName: 'Graham', category: 'analyst', description: 'Margin of safety, intrinsic value' },
  { id: 'peter_lynch', name: 'Peter Lynch', shortName: 'Lynch', category: 'analyst', description: 'Growth at reasonable price' },
  { id: 'phil_fisher', name: 'Phil Fisher', shortName: 'Fisher', category: 'analyst', description: 'Scuttlebutt, quality growth' },
  { id: 'cathie_wood', name: 'Cathie Wood', shortName: 'Wood', category: 'analyst', description: 'Disruptive innovation' },
  { id: 'michael_burry', name: 'Michael Burry', shortName: 'Burry', category: 'analyst', description: 'Contrarian, deep value' },
  { id: 'bill_ackman', name: 'Bill Ackman', shortName: 'Ackman', category: 'analyst', description: 'Activist investing' },
  { id: 'stanley_druckenmiller', name: 'Stanley Druckenmiller', shortName: 'Druck', category: 'analyst', description: 'Macro trends, risk management' },
  { id: 'aswath_damodaran', name: 'Aswath Damodaran', shortName: 'Damodaran', category: 'analyst', description: 'Valuation expert' },
  { id: 'mohnish_pabrai', name: 'Mohnish Pabrai', shortName: 'Pabrai', category: 'analyst', description: 'Cloning, low-risk bets' },
  { id: 'rakesh_jhunjhunwala', name: 'Rakesh Jhunjhunwala', shortName: 'Rakesh', category: 'analyst', description: 'Emerging markets' },
  { id: 'fundamentals', name: 'Fundamentals Agent', shortName: 'Fundamentals', category: 'analyst', description: 'Financial statement analysis' },
  { id: 'technicals', name: 'Technical Agent', shortName: 'Technicals', category: 'analyst', description: 'Chart patterns, momentum' },
  { id: 'sentiment', name: 'Sentiment Agent', shortName: 'Sentiment', category: 'analyst', description: 'Market sentiment, social signals' },
  { id: 'valuation', name: 'Valuation Agent', shortName: 'Valuation', category: 'analyst', description: 'DCF, multiples analysis' },
  { id: 'risk_manager', name: 'Risk Manager', shortName: 'Risk', category: 'analyst', description: 'Position sizing, risk limits' },
  { id: 'news_sentiment', name: 'News Sentiment', shortName: 'News', category: 'analyst', description: 'News analysis, event detection' },
  
  // Research Agent
  { id: 'mazo', name: 'Mazo Research', shortName: 'Mazo', category: 'research', description: 'Deep web research, comprehensive analysis' },
  
  // Portfolio Manager
  { id: 'portfolio_manager', name: 'Portfolio Manager', shortName: 'PM', category: 'manager', description: 'Final decision maker, signal consolidation' },
];

// ==================== ACTIVITY TYPES ====================

export type ActivityType = 
  | 'ticker_input'      // Ticker brought in for analysis
  | 'agent_start'       // Agent started analyzing
  | 'agent_complete'    // Agent finished with signal
  | 'mazo_query'        // Query sent to Mazo
  | 'mazo_response'     // Mazo research received
  | 'pm_consolidating'  // PM reviewing signals
  | 'pm_decision'       // PM made final decision
  | 'trade_attempt'     // Trade being placed
  | 'trade_executed'    // Trade confirmed
  | 'trade_failed'      // Trade failed
  | 'workflow_start'    // Workflow started
  | 'workflow_complete' // Workflow finished
  | 'error';            // Error occurred

export type SignalType = 'bullish' | 'bearish' | 'neutral' | 'strong_buy' | 'strong_sell';

export interface AgentSignal {
  signal: SignalType;
  confidence: number; // 0-100
  reasoning: string;
}

export interface AgentActivityEntry {
  id: string;
  timestamp: string;
  type: ActivityType;
  agentId?: string;
  agentName?: string;
  ticker?: string;
  message: string;
  details?: {
    signal?: AgentSignal;
    reasoning?: string;
    duration?: number;
    error?: string;
    tradeAction?: 'BUY' | 'SELL' | 'HOLD';
    quantity?: number;
    price?: number;
    research?: string;
    query?: string;
  };
  isPinned?: boolean;
  isExpanded?: boolean;
}

// ==================== WORKFLOW PROGRESS ====================

export interface WorkflowProgress {
  workflowId: string;
  status: 'idle' | 'running' | 'complete' | 'error';
  startedAt?: string;
  completedAt?: string;
  currentStep?: string;
  ticker?: string;
  
  // Agent progress tracking
  agentsTotal: number;
  agentsComplete: number;
  agentStatuses: Record<string, 'pending' | 'running' | 'complete' | 'error'>;
  
  // Signals collected
  signals: Record<string, AgentSignal>;
  
  // Final decision
  finalDecision?: {
    action: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;
    reasoning: string;
  };
  
  // Mazo research
  mazoResearch?: {
    query: string;
    response: string;
    sources?: string[];
  };
  
  // Execution result
  executionResult?: {
    success: boolean;
    orderId?: string;
    filledQty?: number;
    avgPrice?: number;
    error?: string;
  };
}

// ==================== AGENT ROSTER STATE ====================

export type AgentStatus = 'idle' | 'analyzing' | 'complete' | 'error';

export interface AgentRosterEntry {
  agent: AgentDefinition;
  status: AgentStatus;
  lastSignal?: AgentSignal;
  lastTicker?: string;
  lastUpdated?: string;
}

// ==================== DECISION TREE ====================

export interface DecisionNode {
  id: string;
  type: 'agent' | 'consolidation' | 'decision' | 'execution';
  label: string;
  signal?: SignalType;
  confidence?: number;
  children?: DecisionNode[];
}

// ==================== CONSOLE LOG ====================

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface ConsoleLogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  source: string;
  message: string;
  data?: unknown;
}

// ==================== FILTER OPTIONS ====================

export interface ActivityFilters {
  showAgents: boolean;
  showMazo: boolean;
  showPM: boolean;
  showExecution: boolean;
  showErrors: boolean;
  searchQuery: string;
  tickerFilter?: string;
}

// ==================== HELPER FUNCTIONS ====================

export function getAgentById(id: string): AgentDefinition | undefined {
  return AGENT_ROSTER.find(a => a.id === id);
}

export function getAgentsByCategory(category: AgentCategory): AgentDefinition[] {
  return AGENT_ROSTER.filter(a => a.category === category);
}

export function getActivityColor(type: ActivityType): string {
  switch (type) {
    case 'ticker_input':
      return 'text-blue-400';
    case 'agent_start':
      return 'text-cyan-400';
    case 'agent_complete':
      return 'text-green-400';
    case 'mazo_query':
    case 'mazo_response':
      return 'text-purple-400';
    case 'pm_consolidating':
    case 'pm_decision':
      return 'text-yellow-400';
    case 'trade_attempt':
      return 'text-orange-400';
    case 'trade_executed':
      return 'text-emerald-400';
    case 'trade_failed':
    case 'error':
      return 'text-red-400';
    case 'workflow_start':
    case 'workflow_complete':
      return 'text-slate-400';
    default:
      return 'text-slate-400';
  }
}

export function getSignalColor(signal: SignalType): string {
  switch (signal) {
    case 'strong_buy':
      return 'text-emerald-400';
    case 'bullish':
      return 'text-green-400';
    case 'neutral':
      return 'text-slate-400';
    case 'bearish':
      return 'text-orange-400';
    case 'strong_sell':
      return 'text-red-400';
    default:
      return 'text-slate-400';
  }
}

export function getSignalBgColor(signal: SignalType): string {
  switch (signal) {
    case 'strong_buy':
      return 'bg-emerald-500/20 border-emerald-500/50';
    case 'bullish':
      return 'bg-green-500/20 border-green-500/50';
    case 'neutral':
      return 'bg-slate-500/20 border-slate-500/50';
    case 'bearish':
      return 'bg-orange-500/20 border-orange-500/50';
    case 'strong_sell':
      return 'bg-red-500/20 border-red-500/50';
    default:
      return 'bg-slate-500/20 border-slate-500/50';
  }
}
