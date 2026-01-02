/**
 * Mazo Research Viewer
 * 
 * Displays Mazo research output with formatting, sources, and key findings.
 * Part of the Intelligence Panel (right sidebar).
 */

import { cn } from '@/lib/utils';
import { useDataStore } from '@/services/data-hydration-service';
import {
  Brain,
  ExternalLink,
  FileText,
  Search,
  Copy,
  Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

interface MazoResearchViewerProps {
  className?: string;
}

export function MazoResearchViewer({ className }: MazoResearchViewerProps) {
  const workflowProgress = useDataStore((state) => state.liveWorkflowProgress);
  const research = workflowProgress?.mazoResearch;
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    if (research?.response) {
      navigator.clipboard.writeText(research.response);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!research) {
    return (
      <div className={cn('flex flex-col items-center justify-center h-full text-muted-foreground p-6', className)}>
        <Brain className="w-12 h-12 mb-3 opacity-30" />
        <p className="text-sm text-center font-medium">No Research Available</p>
        <p className="text-xs text-center mt-1 opacity-70">
          Mazo research will appear here when you run an analysis
        </p>
      </div>
    );
  }

  const hasContent = typeof research.response === 'string' && research.response.trim().length > 0;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="p-3 border-b border-border/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium">Mazo Research</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2"
          onClick={copyToClipboard}
          disabled={!hasContent}
          title={hasContent ? "Copy to clipboard" : "No content to copy"}
        >
          {copied ? (
            <Check className="w-3 h-3 text-green-400" />
          ) : (
            <Copy className="w-3 h-3" />
          )}
        </Button>
      </div>

      {/* Query */}
      {research.query && (
        <div className="p-3 border-b border-border/50 bg-purple-500/5">
          <div className="flex items-center gap-1.5 text-xs text-purple-400 mb-1">
            <Search className="w-3 h-3" />
            <span>Query</span>
          </div>
          <p className="text-sm text-foreground/90">{research.query}</p>
        </div>
      )}

      {/* Research Content */}
      <div className="flex-1 overflow-y-auto p-3">
        <div className="prose prose-sm prose-invert max-w-none">
          <ResearchContent content={hasContent ? research.response : undefined} />
        </div>
      </div>

      {/* Sources */}
      {research.sources && research.sources.length > 0 && (
        <div className="border-t border-border/50 p-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
            <FileText className="w-3 h-3" />
            <span>Sources ({research.sources.length})</span>
          </div>
          <div className="space-y-1 max-h-24 overflow-y-auto">
            {research.sources.map((source, i) => {
              // Handle both string URLs and {type, title} objects
              const isObject = typeof source === 'object' && source !== null;
              const displayText = isObject 
                ? (source as { type?: string; title?: string }).title || (source as { type?: string; title?: string }).type || 'Source'
                : String(source);
              const href = isObject ? undefined : String(source);
              
              return (
                <div
                  key={i}
                  className="flex items-center gap-1.5 text-xs text-cyan-400 truncate"
                >
                  <ExternalLink className="w-3 h-3 flex-shrink-0" />
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-cyan-300 truncate"
                    >
                      {displayText}
                    </a>
                  ) : (
                    <span className="truncate">
                      {isObject && (source as { type?: string }).type && (
                        <span className="text-muted-foreground mr-1">[{(source as { type?: string }).type}]</span>
                      )}
                      {displayText}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// Research content with basic markdown-like formatting
function ResearchContent({ content }: { content?: string }) {
  if (!content || !content.trim()) {
    return (
      <p className="text-xs text-muted-foreground text-center py-6">
        Research metadata was received but no written summary is available yet.
      </p>
    );
  }
  // Split content into sections
  const sections = content.split(/\n\n+/);

  return (
    <div className="space-y-3">
      {sections.map((section, i) => {
        // Headers
        if (section.startsWith('# ')) {
          return (
            <h1 key={i} className="text-lg font-bold text-foreground border-b border-border/30 pb-1">
              {section.slice(2)}
            </h1>
          );
        }
        if (section.startsWith('## ')) {
          return (
            <h2 key={i} className="text-base font-semibold text-foreground mt-4">
              {section.slice(3)}
            </h2>
          );
        }
        if (section.startsWith('### ')) {
          return (
            <h3 key={i} className="text-sm font-medium text-foreground/90 mt-3">
              {section.slice(4)}
            </h3>
          );
        }

        // Lists
        if (section.match(/^[-•*]\s/m)) {
          const items = section.split(/\n/).filter(Boolean);
          return (
            <ul key={i} className="space-y-1 pl-4">
              {items.map((item, j) => (
                <li key={j} className="text-xs text-foreground/80 list-disc">
                  {item.replace(/^[-•*]\s/, '')}
                </li>
              ))}
            </ul>
          );
        }

        // Numbered lists
        if (section.match(/^\d+\.\s/m)) {
          const items = section.split(/\n/).filter(Boolean);
          return (
            <ol key={i} className="space-y-1 pl-4">
              {items.map((item, j) => (
                <li key={j} className="text-xs text-foreground/80 list-decimal">
                  {item.replace(/^\d+\.\s/, '')}
                </li>
              ))}
            </ol>
          );
        }

        // Key findings (highlighted)
        if (section.toLowerCase().includes('key finding') || 
            section.toLowerCase().includes('conclusion') ||
            section.toLowerCase().includes('summary')) {
          return (
            <div key={i} className="bg-cyan-500/10 border border-cyan-500/30 rounded p-2">
              <p className="text-xs text-foreground/90">{section}</p>
            </div>
          );
        }

        // Regular paragraphs
        return (
          <p key={i} className="text-xs text-foreground/80 leading-relaxed">
            {section}
          </p>
        );
      })}
    </div>
  );
}
