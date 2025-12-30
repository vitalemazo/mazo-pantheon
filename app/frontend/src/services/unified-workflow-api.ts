/**
 * Unified Workflow API Service
 * 
 * Handles API calls to the unified workflow endpoint with streaming support.
 */

import { API_BASE_URL } from '@/lib/api-config';

export interface UnifiedWorkflowRequest {
  tickers: string[];
  mode: 'signal' | 'research' | 'pre-research' | 'post-research' | 'full';
  depth: 'quick' | 'standard' | 'deep';
  model_name?: string;
  model_provider?: string;
  execute_trades?: boolean;
  dry_run?: boolean;
  force_refresh?: boolean;  // Force fresh data, bypass cache
}

export interface UnifiedWorkflowResult {
  ticker: string;
  signal: string;
  confidence: number;
  agent_signals: Array<{
    agent_name: string;
    signal: string;
    confidence: number;
    reasoning: string;
  }>;
  research_report?: string;
  recommendations: string[];
  trade?: {
    action: string;
    quantity: number;
    executed: boolean;
    order_id?: string;
    filled_price?: number;
    error?: string;
  };
  workflow_mode: string;
  execution_time: number;
  timestamp: string;
}

export type WorkflowEventType = 'start' | 'progress' | 'complete' | 'error';

export interface WorkflowEvent {
  type: WorkflowEventType;
  data?: any;
  agent?: string;
  ticker?: string;
  status?: string;
  message?: string;
}

/**
 * Run unified workflow with streaming progress updates
 */
export async function runUnifiedWorkflow(
  request: UnifiedWorkflowRequest,
  onEvent: (event: WorkflowEvent) => void,
  signal?: AbortSignal
): Promise<UnifiedWorkflowResult[]> {
  const response = await fetch(`${API_BASE_URL}/unified-workflow/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      tickers: request.tickers,
      mode: request.mode,
      depth: request.depth,
      model_name: request.model_name,
      model_provider: request.model_provider || 'OpenAI',
      execute_trades: request.execute_trades || false,
      dry_run: request.dry_run || false,
      force_refresh: request.force_refresh || false,
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error('No response body');
  }

  let buffer = '';
  let results: UnifiedWorkflowResult[] = [];

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      let currentEvent: { type?: string; data?: string } = {};
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
          // Empty line indicates end of event, process it
          if (currentEvent.data) {
            try {
              const data = JSON.parse(currentEvent.data);
              
              // Debug logging for progress events
              if (data.type === 'progress') {
                console.log('[SSE Progress]', {
                  agent: data.agent,
                  status: data.status,
                  ticker: data.ticker,
                  hasAnalysis: !!data.analysis
                });
              }

              if (data.type === 'start') {
                onEvent({ type: 'start' });
              } else if (data.type === 'progress') {
                // Parse analysis JSON string if present
                let analysisData = null;
                if (data.analysis) {
                  try {
                    analysisData = typeof data.analysis === 'string' 
                      ? JSON.parse(data.analysis) 
                      : data.analysis;
                  } catch (e) {
                    // If parsing fails, use as string
                    analysisData = data.analysis;
                  }
                }
                onEvent({
                  type: 'progress',
                  agent: data.agent,
                  ticker: data.ticker,
                  status: data.status,
                  data: analysisData,
                });
              } else if (data.type === 'complete') {
                results = data.data.results || [];
                onEvent({
                  type: 'complete',
                  data: { results },
                });
              } else if (data.type === 'error') {
                onEvent({
                  type: 'error',
                  message: data.message,
                });
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e, 'Raw data:', currentEvent.data);
            }
          }
          // Reset for next event
          currentEvent = {};
        } else if (trimmed.startsWith('event: ')) {
          currentEvent.type = trimmed.slice(7).trim();
        } else if (trimmed.startsWith('data: ')) {
          // Handle multi-line data (append if data already exists)
          const dataLine = trimmed.slice(6).trim();
          if (currentEvent.data) {
            currentEvent.data += '\n' + dataLine;
          } else {
            currentEvent.data = dataLine;
          }
        }
      }
    }
  } catch (err: any) {
    if (err.name !== 'AbortError') {
      throw err;
    }
  }

  return results;
}
