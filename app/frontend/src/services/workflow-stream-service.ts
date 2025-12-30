/**
 * Workflow Stream Service
 * 
 * Connects to the unified-workflow SSE stream and populates:
 * - Agent Activity Feed (left sidebar)
 * - Intelligence Panel (right sidebar)
 * - Console Logs
 * 
 * Provides real-time visibility into AI decision-making.
 */

import { API_BASE_URL } from '@/lib/api-config';
import { useDataStore } from './data-hydration-service';
import { AGENT_ROSTER } from '@/types/ai-transparency';
import type { 
  AgentActivityEntry, 
  WorkflowProgress,
  SignalType,
  ActivityType,
} from '@/types/ai-transparency';

// ==================== STREAM PARSING ====================

interface SSEEvent {
  event: string;
  data: any;
}

function parseSSELine(line: string): SSEEvent | null {
  if (line.startsWith('data:')) {
    try {
      const jsonStr = line.slice(5).trim();
      const data = JSON.parse(jsonStr);
      return {
        event: data.event || 'message',
        data: data.data || data,
      };
    } catch {
      return null;
    }
  }
  return null;
}

// ==================== WORKFLOW STREAM CLASS ====================

export class WorkflowStreamService {
  private abortController: AbortController | null = null;
  private currentWorkflowId: string | null = null;

  /**
   * Start streaming a workflow execution
   */
  async streamWorkflow(
    tickers: string[],
    options: {
      mode?: 'signal' | 'full';
      depth?: 'quick' | 'standard' | 'deep';
      execute_trades?: boolean;
      dry_run?: boolean;
    } = {}
  ): Promise<void> {
    // Cancel any existing stream
    this.cancel();

    const store = useDataStore.getState();
    const workflowId = `workflow_${Date.now()}`;
    this.currentWorkflowId = workflowId;
    this.abortController = new AbortController();

    // Initialize workflow progress
    const initialProgress: WorkflowProgress = {
      workflowId,
      status: 'running',
      startedAt: new Date().toISOString(),
      ticker: tickers[0],
      agentsTotal: 18,
      agentsComplete: 0,
      agentStatuses: {},
      signals: {},
    };

    store.setLiveWorkflowProgress(initialProgress);
    store.resetAgentStatuses();

    // Add workflow start activity
    store.addAgentActivity({
      timestamp: new Date().toISOString(),
      type: 'workflow_start',
      message: `Starting analysis for ${tickers.join(', ')}`,
      ticker: tickers[0],
    });

    // Add console log
    store.addConsoleLog({
      timestamp: new Date().toISOString(),
      level: 'info',
      source: 'WorkflowStream',
      message: `Initiating workflow for tickers: ${tickers.join(', ')}`,
    });

    try {
      const response = await fetch(`${API_BASE_URL}/unified-workflow/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers,
          mode: options.mode || 'full',
          depth: options.depth || 'standard',
          execute_trades: options.execute_trades ?? false,
          dry_run: options.dry_run ?? true,
        }),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const event = parseSSELine(line);
          if (event) {
            this.handleEvent(event, workflowId);
          }
        }
      }

      // Handle any remaining buffer
      if (buffer) {
        const event = parseSSELine(buffer);
        if (event) {
          this.handleEvent(event, workflowId);
        }
      }

    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('[WorkflowStream] Stream cancelled');
        return;
      }

      const store = useDataStore.getState();
      store.updateWorkflowProgress({ status: 'error' });
      store.addAgentActivity({
        timestamp: new Date().toISOString(),
        type: 'error',
        message: `Workflow failed: ${error.message}`,
        ticker: tickers[0],
        details: { error: error.message },
      });
      store.addConsoleLog({
        timestamp: new Date().toISOString(),
        level: 'error',
        source: 'WorkflowStream',
        message: error.message,
      });

      throw error;
    }
  }

  /**
   * Handle an SSE event
   */
  private handleEvent(event: SSEEvent, workflowId: string): void {
    const store = useDataStore.getState();
    const eventType = event.event;
    const data = event.data;

    // Log to console
    store.addConsoleLog({
      timestamp: new Date().toISOString(),
      level: 'debug',
      source: eventType,
      message: JSON.stringify(data).slice(0, 200),
    });

    switch (eventType) {
      case 'start':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'workflow_start',
          message: data.message || 'Workflow started',
        });
        break;

      case 'progress':
        this.handleProgressEvent(data, store);
        break;

      case 'agent_start':
        this.handleAgentStart(data, store);
        break;

      case 'agent_complete':
        this.handleAgentComplete(data, store);
        break;

      case 'mazo_start':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'mazo_query',
          agentId: 'mazo',
          agentName: 'Mazo Research',
          message: data.message || 'Starting deep research...',
          ticker: data.ticker,
          details: { query: data.query },
        });
        store.setAgentStatus('mazo', 'running');
        break;

      case 'mazo_complete':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'mazo_response',
          agentId: 'mazo',
          agentName: 'Mazo Research',
          message: 'Research complete',
          ticker: data.ticker,
          details: { research: data.research?.slice(0, 500) },
        });
        store.setAgentStatus('mazo', 'complete');
        store.updateWorkflowProgress({
          mazoResearch: {
            query: data.query || '',
            response: data.research || '',
            sources: data.sources || [],
          },
        });
        break;

      case 'pm_start':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'pm_consolidating',
          agentId: 'portfolio_manager',
          agentName: 'Portfolio Manager',
          message: 'Consolidating agent signals...',
        });
        store.setAgentStatus('portfolio_manager', 'running');
        break;

      case 'pm_decision':
        const decision = data.decision || data;
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'pm_decision',
          agentId: 'portfolio_manager',
          agentName: 'Portfolio Manager',
          message: `Decision: ${decision.action || 'HOLD'}`,
          ticker: decision.ticker,
          details: {
            tradeAction: decision.action,
            reasoning: decision.reasoning,
          },
        });
        store.setAgentStatus('portfolio_manager', 'complete');
        store.updateWorkflowProgress({
          finalDecision: {
            action: decision.action || 'HOLD',
            confidence: decision.confidence || 50,
            reasoning: decision.reasoning || '',
          },
        });
        break;

      case 'trade_attempt':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'trade_attempt',
          message: `Attempting ${data.action} order for ${data.ticker}`,
          ticker: data.ticker,
          details: {
            tradeAction: data.action,
            quantity: data.quantity,
          },
        });
        break;

      case 'trade_executed':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'trade_executed',
          message: `Trade executed: ${data.action} ${data.quantity} ${data.ticker}`,
          ticker: data.ticker,
          details: {
            tradeAction: data.action,
            quantity: data.quantity,
            price: data.price,
          },
        });
        store.updateWorkflowProgress({
          executionResult: {
            success: true,
            orderId: data.order_id,
            filledQty: data.quantity,
            avgPrice: data.price,
          },
        });
        break;

      case 'trade_failed':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'trade_failed',
          message: `Trade failed: ${data.error}`,
          ticker: data.ticker,
          details: { error: data.error },
        });
        store.updateWorkflowProgress({
          executionResult: {
            success: false,
            error: data.error,
          },
        });
        break;

      case 'complete':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'workflow_complete',
          message: data.message || 'Workflow complete',
          details: data,
        });
        store.updateWorkflowProgress({
          status: 'complete',
          completedAt: new Date().toISOString(),
        });
        store.addConsoleLog({
          timestamp: new Date().toISOString(),
          level: 'info',
          source: 'WorkflowStream',
          message: 'Workflow completed successfully',
        });
        break;

      case 'error':
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'error',
          message: data.message || 'Error occurred',
          details: { error: data.error || data.message },
        });
        store.updateWorkflowProgress({ status: 'error' });
        store.addConsoleLog({
          timestamp: new Date().toISOString(),
          level: 'error',
          source: 'WorkflowStream',
          message: data.message || data.error || 'Unknown error',
        });
        break;
    }
  }

  /**
   * Handle progress events (agent updates)
   */
  private handleProgressEvent(data: any, store: ReturnType<typeof useDataStore.getState>): void {
    const message = data.message || '';
    const progress = data.progress || {};

    // Try to extract agent info from the message
    const agentMatch = message.match(/Running (\w+)/i) || message.match(/(\w+) agent/i);
    if (agentMatch) {
      const agentName = agentMatch[1];
      const agent = AGENT_ROSTER.find(
        (a) => a.name.toLowerCase().includes(agentName.toLowerCase()) ||
               a.shortName.toLowerCase() === agentName.toLowerCase() ||
               a.id === agentName.toLowerCase()
      );

      if (agent) {
        store.setAgentStatus(agent.id, 'running');
        store.addAgentActivity({
          timestamp: new Date().toISOString(),
          type: 'agent_start',
          agentId: agent.id,
          agentName: agent.name,
          message: `${agent.name} analyzing...`,
          ticker: data.ticker,
        });
      }
    }

    // Update progress count if available
    if (progress.current !== undefined && progress.total !== undefined) {
      store.updateWorkflowProgress({
        agentsComplete: progress.current,
        agentsTotal: progress.total,
      });
    }
  }

  /**
   * Handle agent start event
   */
  private handleAgentStart(data: any, store: ReturnType<typeof useDataStore.getState>): void {
    const agentId = data.agent_id || data.agentId;
    const agent = AGENT_ROSTER.find((a) => a.id === agentId);

    store.setAgentStatus(agentId, 'running');
    store.addAgentActivity({
      timestamp: new Date().toISOString(),
      type: 'agent_start',
      agentId,
      agentName: agent?.name || agentId,
      message: `${agent?.name || agentId} analyzing...`,
      ticker: data.ticker,
    });
  }

  /**
   * Handle agent complete event
   */
  private handleAgentComplete(data: any, store: ReturnType<typeof useDataStore.getState>): void {
    const agentId = data.agent_id || data.agentId || data.agent;
    const agent = AGENT_ROSTER.find((a) => 
      a.id === agentId || 
      a.name.toLowerCase() === agentId?.toLowerCase() ||
      a.shortName.toLowerCase() === agentId?.toLowerCase()
    );

    const signalValue = (data.signal || 'neutral').toLowerCase();
    const signal: SignalType = 
      signalValue.includes('strong') && signalValue.includes('buy') ? 'strong_buy' :
      signalValue.includes('strong') && signalValue.includes('sell') ? 'strong_sell' :
      signalValue.includes('bull') || signalValue === 'buy' ? 'bullish' :
      signalValue.includes('bear') || signalValue === 'sell' ? 'bearish' :
      'neutral';

    const confidence = data.confidence || 50;
    const reasoning = data.reasoning || '';

    const actualAgentId = agent?.id || agentId || 'unknown';

    store.setAgentStatus(actualAgentId, 'complete');
    store.addAgentActivity({
      timestamp: new Date().toISOString(),
      type: 'agent_complete',
      agentId: actualAgentId,
      agentName: agent?.name || agentId,
      message: `${agent?.name || agentId}: ${signal.toUpperCase()} (${confidence}%)`,
      ticker: data.ticker,
      details: {
        signal: { signal, confidence, reasoning },
        reasoning,
      },
    });

    // Update workflow progress with signal
    const currentProgress = store.liveWorkflowProgress;
    if (currentProgress) {
      store.updateWorkflowProgress({
        agentsComplete: (currentProgress.agentsComplete || 0) + 1,
        signals: {
          ...currentProgress.signals,
          [actualAgentId]: { signal, confidence, reasoning },
        },
      });
    }
  }

  /**
   * Cancel the current stream
   */
  cancel(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    this.currentWorkflowId = null;
  }

  /**
   * Check if a stream is currently active
   */
  isActive(): boolean {
    return this.abortController !== null;
  }

  /**
   * Get the current workflow ID
   */
  getCurrentWorkflowId(): string | null {
    return this.currentWorkflowId;
  }
}

// Singleton instance
export const workflowStreamService = new WorkflowStreamService();

// ==================== REACT HOOK ====================

export function useWorkflowStream() {
  return {
    streamWorkflow: (tickers: string[], options?: Parameters<WorkflowStreamService['streamWorkflow']>[1]) =>
      workflowStreamService.streamWorkflow(tickers, options),
    cancel: () => workflowStreamService.cancel(),
    isActive: () => workflowStreamService.isActive(),
  };
}
