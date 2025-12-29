/**
 * Research Tab Component
 *
 * Chat interface for interacting with Mazo research agent.
 */

import { useResearch, ResearchMessage } from '@/contexts/research-context';
import { ResearchDepth } from '@/services/mazo-api';
import { cn } from '@/lib/utils';
import { Send, Loader2, Trash2, Search, TrendingUp, GitCompare, AlertCircle } from 'lucide-react';
import { useState, useRef, useEffect, FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface ResearchTabProps {
  className?: string;
}

function MessageBubble({ message }: { message: ResearchMessage }) {
  const isUser = message.type === 'user';
  const isError = message.type === 'error';

  return (
    <div
      className={cn(
        'flex w-full mb-4',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div
        className={cn(
          'max-w-[80%] rounded-lg px-4 py-3',
          isUser
            ? 'bg-primary text-primary-foreground'
            : isError
            ? 'bg-destructive/10 text-destructive border border-destructive/20'
            : 'bg-muted'
        )}
      >
        {/* Message content */}
        <div className="text-sm whitespace-pre-wrap">{message.content}</div>

        {/* Metadata for assistant messages */}
        {message.type === 'assistant' && (
          <div className="mt-2 pt-2 border-t border-border/50 flex items-center gap-2 flex-wrap">
            {message.confidence !== undefined && (
              <Badge variant="outline" className="text-xs">
                {message.confidence}% confidence
              </Badge>
            )}
            {message.ticker && (
              <Badge variant="secondary" className="text-xs">
                {message.ticker}
              </Badge>
            )}
          </div>
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 pt-2 border-t border-border/50">
            <span className="text-xs text-muted-foreground">Sources:</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {message.sources.map((source, index) => (
                <Badge key={index} variant="outline" className="text-xs">
                  {source}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Timestamp */}
        <div className="mt-1 text-xs text-muted-foreground/70">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

export function ResearchTab({ className }: ResearchTabProps) {
  const {
    state,
    sendQuery,
    analyzeCompany,
    compareCompanies,
    setDepth,
    clearHistory,
  } = useResearch();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || state.isLoading) return;

    const query = input.trim();
    setInput('');
    await sendQuery(query);
  };

  const handleQuickAction = async (action: 'analyze' | 'compare') => {
    const tickerInput = prompt(
      action === 'analyze'
        ? 'Enter ticker symbol (e.g., AAPL):'
        : 'Enter ticker symbols separated by commas (e.g., AAPL, MSFT, GOOGL):'
    );

    if (!tickerInput) return;

    if (action === 'analyze') {
      await analyzeCompany(tickerInput.trim().toUpperCase());
    } else {
      const tickers = tickerInput.split(',').map(t => t.trim().toUpperCase());
      await compareCompanies(tickers);
    }
  };

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header with controls */}
      <div className="flex items-center justify-between pb-3 border-b mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Research Depth:</span>
          <select
            value={state.currentDepth}
            onChange={(e) => setDepth(e.target.value as ResearchDepth)}
            className="text-sm bg-background border rounded px-2 py-1"
            disabled={state.isLoading}
          >
            <option value="quick">Quick</option>
            <option value="standard">Standard</option>
            <option value="deep">Deep</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick actions */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleQuickAction('analyze')}
            disabled={state.isLoading}
          >
            <TrendingUp size={14} className="mr-1" />
            Analyze
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleQuickAction('compare')}
            disabled={state.isLoading}
          >
            <GitCompare size={14} className="mr-1" />
            Compare
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearHistory}
            disabled={state.isLoading || state.messages.length === 0}
          >
            <Trash2 size={14} />
          </Button>
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-2">
        {state.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <Search size={48} className="mb-4 opacity-50" />
            <p className="text-sm">Ask Mazo anything about the markets</p>
            <p className="text-xs mt-1">Try: "What's driving NVDA's growth?"</p>
          </div>
        ) : (
          <>
            {state.messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}

        {/* Loading indicator */}
        {state.isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground mb-4">
            <Loader2 size={16} className="animate-spin" />
            <span className="text-sm">Researching...</span>
          </div>
        )}
      </div>

      {/* Health warning */}
      {!state.isHealthy && (
        <div className="flex items-center gap-2 text-destructive text-sm py-2 px-3 bg-destructive/10 rounded mb-2">
          <AlertCircle size={14} />
          <span>Mazo service unavailable. Check configuration.</span>
        </div>
      )}

      {/* Input area */}
      <form onSubmit={handleSubmit} className="flex gap-2 pt-3 border-t mt-auto">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a research question..."
          className="flex-1 bg-background border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          disabled={state.isLoading}
        />
        <Button
          type="submit"
          size="sm"
          disabled={!input.trim() || state.isLoading}
        >
          {state.isLoading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Send size={16} />
          )}
        </Button>
      </form>
    </div>
  );
}
