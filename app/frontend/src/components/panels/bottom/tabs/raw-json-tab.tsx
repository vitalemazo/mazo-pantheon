/**
 * Raw JSON Tab
 * 
 * Displays the complete workflow data as formatted JSON for easy copying.
 * Shows all steps, results, API calls, agent executions, and more.
 */

import { useWorkflowContext } from '@/contexts/workflow-context';
import { cn } from '@/lib/utils';
import { Copy, Check, Download, FileJson, RefreshCw } from 'lucide-react';
import { useState, useMemo } from 'react';
import { Button } from '@/components/ui/button';

interface RawJsonTabProps {
  className?: string;
}

export function RawJsonTab({ className }: RawJsonTabProps) {
  const {
    config,
    isRunning,
    steps,
    results,
    error,
  } = useWorkflowContext();
  
  const { tickers, mode, depth, executeTrades, dryRun, forceRefresh } = config;
  
  const [copied, setCopied] = useState(false);

  // Build the complete workflow data object
  const workflowData = useMemo(() => {
    return {
      metadata: {
        timestamp: new Date().toISOString(),
        version: '1.0',
      },
      configuration: {
        tickers: (tickers || '').split(',').map(t => t.trim()).filter(Boolean),
        mode,
        depth,
        executeTrades,
        dryRun,
        forceRefresh,
      },
      status: {
        isRunning,
        hasError: !!error,
        error: error || null,
        stepsCompleted: steps.filter(s => s.status === 'completed').length,
        totalSteps: steps.length,
      },
      steps: steps.map(step => ({
        id: step.id,
        name: step.name,
        status: step.status,
        startTime: step.startTime ? new Date(step.startTime).toISOString() : null,
        endTime: step.endTime ? new Date(step.endTime).toISOString() : null,
        durationMs: step.startTime && step.endTime ? step.endTime - step.startTime : null,
        details: step.details || null,
        subSteps: step.subSteps?.map(sub => ({
          id: sub.id,
          name: sub.name,
          status: sub.status,
          details: sub.details || null,
        })) || [],
        apiCalls: step.apiCalls || [],
        agentExecutions: step.agentExecutions || [],
        dataRetrievals: step.dataRetrievals || [],
        mazoResearch: step.mazoResearch || null,
        tradeExecution: step.tradeExecution || null,
      })),
      results: results.map(result => ({
        ticker: result.ticker,
        signal: result.signal,
        confidence: result.confidence,
        agentSignals: result.agentSignals,
        research: result.research,
        trade: result.trade,
        recommendations: result.recommendations,
        executionTime: result.executionTime,
      })),
    };
  }, [tickers, mode, depth, executeTrades, dryRun, forceRefresh, isRunning, steps, results, error]);

  const jsonString = useMemo(() => {
    return JSON.stringify(workflowData, null, 2);
  }, [workflowData]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(jsonString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workflow-${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const hasData = steps.length > 0 || results.length > 0;

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Header with actions */}
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <FileJson className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-primary">Raw Workflow JSON</span>
          {isRunning && (
            <span className="flex items-center gap-1 text-xs text-amber-500">
              <RefreshCw className="h-3 w-3 animate-spin" />
              Updating...
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            disabled={!hasData}
            className="h-7 px-2 text-xs"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 mr-1 text-green-500" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-3 w-3 mr-1" />
                Copy All
              </>
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownload}
            disabled={!hasData}
            className="h-7 px-2 text-xs"
          >
            <Download className="h-3 w-3 mr-1" />
            Download
          </Button>
        </div>
      </div>

      {/* JSON content */}
      <div className="flex-1 min-h-0 overflow-auto bg-background rounded-md border border-border">
        {hasData ? (
          <pre className="p-4 text-xs font-mono text-primary whitespace-pre overflow-x-auto">
            {jsonString}
          </pre>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <FileJson className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm">No workflow data yet</p>
            <p className="text-xs mt-1">Run an analysis to see the raw JSON output</p>
          </div>
        )}
      </div>

      {/* Stats footer */}
      {hasData && (
        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground flex-shrink-0">
          <span>{steps.length} steps</span>
          <span>{results.length} results</span>
          <span>{(jsonString.length / 1024).toFixed(1)} KB</span>
        </div>
      )}
    </div>
  );
}
