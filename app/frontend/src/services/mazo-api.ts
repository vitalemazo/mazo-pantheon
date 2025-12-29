/**
 * Mazo Research API Service
 *
 * Provides frontend methods for interacting with the Mazo research agent backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type ResearchDepth = 'quick' | 'standard' | 'deep';

export interface ResearchResponse {
  success: boolean;
  answer: string | null;
  confidence: number;
  sources: string[];
  error?: string;
}

export interface PreResearchResponse {
  pre_research: Record<string, ResearchResponse>;
}

export interface ResearchRequest {
  query: string;
  depth?: ResearchDepth;
}

export interface CompanyAnalysisRequest {
  ticker: string;
  depth?: ResearchDepth;
}

export interface CompareCompaniesRequest {
  tickers: string[];
  depth?: ResearchDepth;
}

export interface ExplainSignalRequest {
  ticker: string;
  signal: string;
  confidence: number;
  reasoning: string;
}

export interface PreResearchRequest {
  tickers: string[];
  depth?: ResearchDepth;
}

export interface MazoHealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  mazo_path?: string;
  timeout?: number;
  error?: string;
}

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
}

export interface TemplateResponse {
  templates: TemplateInfo[];
}

export interface TemplateResearchRequest {
  ticker: string;
  template_id: string;
  depth?: ResearchDepth;
}

export interface BatchAnalysisRequest {
  tickers: string[];
  template_id?: string;
  depth?: ResearchDepth;
}

export interface BatchAnalysisResponse {
  success: boolean;
  template_id: string;
  template_name: string;
  results: Record<string, ResearchResponse & { template: string; template_name: string }>;
}

export interface StreamEvent {
  type: 'start' | 'progress' | 'complete' | 'error';
  data: {
    query?: string;
    depth?: string;
    timestamp?: string;
    status?: string;
    message?: string;
    success?: boolean;
    answer?: string;
    confidence?: number;
    sources?: string[];
  };
}

export const mazoApi = {
  /**
   * Execute a research query using Mazo
   * @param request The research request
   * @returns Promise resolving to research response
   */
  research: async (request: ResearchRequest): Promise<ResearchResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: request.query,
          depth: request.depth || 'standard',
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo research failed:', error);
      return {
        success: false,
        answer: null,
        confidence: 0,
        sources: [],
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  },

  /**
   * Run comprehensive company analysis
   * @param request The company analysis request
   * @returns Promise resolving to analysis response
   */
  analyzeCompany: async (request: CompanyAnalysisRequest): Promise<ResearchResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ticker: request.ticker,
          depth: request.depth || 'standard',
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo company analysis failed:', error);
      return {
        success: false,
        answer: null,
        confidence: 0,
        sources: [],
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  },

  /**
   * Compare multiple companies
   * @param request The comparison request
   * @returns Promise resolving to comparison response
   */
  compareCompanies: async (request: CompareCompaniesRequest): Promise<ResearchResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/compare`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tickers: request.tickers,
          depth: request.depth || 'standard',
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo company comparison failed:', error);
      return {
        success: false,
        answer: null,
        confidence: 0,
        sources: [],
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  },

  /**
   * Explain a trading signal using Mazo research
   * @param request The signal explanation request
   * @returns Promise resolving to explanation response
   */
  explainSignal: async (request: ExplainSignalRequest): Promise<ResearchResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/explain-signal`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo signal explanation failed:', error);
      return {
        success: false,
        answer: null,
        confidence: 0,
        sources: [],
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  },

  /**
   * Run pre-workflow research for trading context
   * @param request The pre-research request
   * @returns Promise resolving to pre-research response
   */
  preResearch: async (request: PreResearchRequest): Promise<PreResearchResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/pre-research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tickers: request.tickers,
          depth: request.depth || 'standard',
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo pre-research failed:', error);
      return {
        pre_research: {},
      };
    }
  },

  /**
   * Check Mazo service health
   * @returns Promise resolving to health status
   */
  checkHealth: async (): Promise<MazoHealthStatus> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/health`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo health check failed:', error);
      return {
        status: 'unhealthy',
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  },

  /**
   * Get all available research templates
   * @returns Promise resolving to template list
   */
  getTemplates: async (): Promise<TemplateResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/templates`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo get templates failed:', error);
      return {
        templates: [],
      };
    }
  },

  /**
   * Run research using a predefined template
   * @param request The template research request
   * @returns Promise resolving to research response
   */
  researchWithTemplate: async (request: TemplateResearchRequest): Promise<ResearchResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/research/template`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ticker: request.ticker,
          template_id: request.template_id,
          depth: request.depth || 'standard',
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo template research failed:', error);
      return {
        success: false,
        answer: null,
        confidence: 0,
        sources: [],
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  },

  /**
   * Analyze multiple tickers using a template
   * @param request The batch analysis request
   * @returns Promise resolving to batch analysis response
   */
  batchAnalyze: async (request: BatchAnalysisRequest): Promise<BatchAnalysisResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/mazo/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tickers: request.tickers,
          template_id: request.template_id || 'quick_summary',
          depth: request.depth || 'quick',
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Mazo batch analysis failed:', error);
      return {
        success: false,
        template_id: '',
        template_name: '',
        results: {},
      };
    }
  },

  /**
   * Stream research results using Server-Sent Events
   * @param request The research request
   * @param onEvent Callback for each event received
   * @returns AbortController to cancel the stream
   */
  researchStream: (
    request: ResearchRequest,
    onEvent: (event: StreamEvent) => void,
  ): AbortController => {
    const controller = new AbortController();

    // Note: For SSE with POST, we need to use fetch instead of EventSource
    // since EventSource only supports GET requests
    fetch(`${API_BASE_URL}/mazo/research/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: request.query,
        depth: request.depth || 'standard',
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Response body is not readable');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const eventData = JSON.parse(line.slice(6));
                onEvent(eventData);
              } catch (e) {
                console.error('Failed to parse SSE event:', e);
              }
            }
          }
        }
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          console.error('Mazo stream research failed:', error);
          onEvent({
            type: 'error',
            data: {
              message: error instanceof Error ? error.message : 'Unknown error',
            },
          });
        }
      });

    return controller;
  },
};
