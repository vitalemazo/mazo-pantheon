/**
 * Research Context
 *
 * Manages state for Mazo research interactions across the application.
 */

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { mazoApi, ResearchResponse, ResearchDepth } from '@/services/mazo-api';

export interface ResearchMessage {
  id: string;
  type: 'user' | 'assistant' | 'error';
  content: string;
  timestamp: Date;
  confidence?: number;
  sources?: string[];
  ticker?: string;
}

export interface ResearchState {
  messages: ResearchMessage[];
  isLoading: boolean;
  currentDepth: ResearchDepth;
  isHealthy: boolean;
}

export interface ResearchContextType {
  state: ResearchState;
  sendQuery: (query: string) => Promise<void>;
  analyzeCompany: (ticker: string) => Promise<void>;
  compareCompanies: (tickers: string[]) => Promise<void>;
  explainSignal: (ticker: string, signal: string, confidence: number, reasoning: string) => Promise<void>;
  setDepth: (depth: ResearchDepth) => void;
  clearHistory: () => void;
  checkHealth: () => Promise<void>;
}

const ResearchContext = createContext<ResearchContextType | undefined>(undefined);

export function ResearchProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ResearchState>({
    messages: [],
    isLoading: false,
    currentDepth: 'standard',
    isHealthy: true,
  });

  const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  const addMessage = useCallback((message: Omit<ResearchMessage, 'id' | 'timestamp'>) => {
    setState(prev => ({
      ...prev,
      messages: [
        ...prev.messages,
        {
          ...message,
          id: generateId(),
          timestamp: new Date(),
        },
      ],
    }));
  }, []);

  const sendQuery = useCallback(async (query: string) => {
    // Add user message
    addMessage({
      type: 'user',
      content: query,
    });

    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await mazoApi.research({
        query,
        depth: state.currentDepth,
      });

      if (response.success && response.answer) {
        addMessage({
          type: 'assistant',
          content: response.answer,
          confidence: response.confidence,
          sources: response.sources,
        });
      } else {
        addMessage({
          type: 'error',
          content: response.error || 'Failed to get response from Mazo',
        });
      }
    } catch (error) {
      addMessage({
        type: 'error',
        content: error instanceof Error ? error.message : 'Unknown error occurred',
      });
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [addMessage, state.currentDepth]);

  const analyzeCompany = useCallback(async (ticker: string) => {
    addMessage({
      type: 'user',
      content: `Analyze ${ticker}`,
      ticker,
    });

    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await mazoApi.analyzeCompany({
        ticker,
        depth: state.currentDepth,
      });

      if (response.success && response.answer) {
        addMessage({
          type: 'assistant',
          content: response.answer,
          confidence: response.confidence,
          sources: response.sources,
          ticker,
        });
      } else {
        addMessage({
          type: 'error',
          content: response.error || `Failed to analyze ${ticker}`,
        });
      }
    } catch (error) {
      addMessage({
        type: 'error',
        content: error instanceof Error ? error.message : 'Unknown error occurred',
      });
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [addMessage, state.currentDepth]);

  const compareCompanies = useCallback(async (tickers: string[]) => {
    const tickerStr = tickers.join(', ');
    addMessage({
      type: 'user',
      content: `Compare ${tickerStr}`,
    });

    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await mazoApi.compareCompanies({
        tickers,
        depth: state.currentDepth,
      });

      if (response.success && response.answer) {
        addMessage({
          type: 'assistant',
          content: response.answer,
          confidence: response.confidence,
          sources: response.sources,
        });
      } else {
        addMessage({
          type: 'error',
          content: response.error || `Failed to compare ${tickerStr}`,
        });
      }
    } catch (error) {
      addMessage({
        type: 'error',
        content: error instanceof Error ? error.message : 'Unknown error occurred',
      });
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [addMessage, state.currentDepth]);

  const explainSignal = useCallback(async (
    ticker: string,
    signal: string,
    confidence: number,
    reasoning: string
  ) => {
    addMessage({
      type: 'user',
      content: `Explain ${signal} signal for ${ticker} (${confidence}% confidence)`,
      ticker,
    });

    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await mazoApi.explainSignal({
        ticker,
        signal,
        confidence,
        reasoning,
      });

      if (response.success && response.answer) {
        addMessage({
          type: 'assistant',
          content: response.answer,
          confidence: response.confidence,
          sources: response.sources,
          ticker,
        });
      } else {
        addMessage({
          type: 'error',
          content: response.error || `Failed to explain signal for ${ticker}`,
        });
      }
    } catch (error) {
      addMessage({
        type: 'error',
        content: error instanceof Error ? error.message : 'Unknown error occurred',
      });
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [addMessage]);

  const setDepth = useCallback((depth: ResearchDepth) => {
    setState(prev => ({ ...prev, currentDepth: depth }));
  }, []);

  const clearHistory = useCallback(() => {
    setState(prev => ({ ...prev, messages: [] }));
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const health = await mazoApi.checkHealth();
      setState(prev => ({ ...prev, isHealthy: health.status === 'healthy' }));
    } catch {
      setState(prev => ({ ...prev, isHealthy: false }));
    }
  }, []);

  return (
    <ResearchContext.Provider
      value={{
        state,
        sendQuery,
        analyzeCompany,
        compareCompanies,
        explainSignal,
        setDepth,
        clearHistory,
        checkHealth,
      }}
    >
      {children}
    </ResearchContext.Provider>
  );
}

export function useResearch() {
  const context = useContext(ResearchContext);
  if (context === undefined) {
    throw new Error('useResearch must be used within a ResearchProvider');
  }
  return context;
}
