/**
 * Intelligence Panel
 * 
 * Right sidebar with tabbed views for AI transparency:
 * - Agent Roster: All 20 agents with status
 * - Mazo Research: Full research output
 * - Decision Tree: Visual decision breakdown
 * - Raw Console: Technical logs
 */

import { useResizable } from '@/hooks/use-resizable';
import { cn } from '@/lib/utils';
import { ReactNode, useEffect, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { useDataStore } from '@/services/data-hydration-service';
import {
  Users,
  Brain,
  GitBranch,
  Terminal,
  Sparkles,
} from 'lucide-react';
import { AgentRoster } from './AgentRoster';
import { MazoResearchViewer } from './MazoResearchViewer';
import { DecisionTree } from './DecisionTree';
import { RawConsole } from './RawConsole';

interface IntelligencePanelProps {
  children?: ReactNode;
  isCollapsed: boolean;
  onCollapse: () => void;
  onExpand: () => void;
  onWidthChange?: (width: number) => void;
}

export function IntelligencePanel({
  isCollapsed,
  onWidthChange,
}: IntelligencePanelProps) {
  const { width, isDragging, elementRef, startResize } = useResizable({
    defaultWidth: 340,
    minWidth: 280,
    maxWidth: window.innerWidth * 0.5,
    side: 'right',
  });

  const [activeTab, setActiveTab] = useState('roster');

  // Get counts for badges
  const workflowProgress = useDataStore((state) => state.liveWorkflowProgress);
  const consoleLogs = useDataStore((state) => state.consoleLogs);

  const agentCount = workflowProgress?.agentsComplete || 0;
  const hasResearch = !!workflowProgress?.mazoResearch;
  const hasDecision = !!workflowProgress?.finalDecision;
  const logCount = consoleLogs.length;

  // Notify parent of width changes
  useEffect(() => {
    onWidthChange?.(width);
  }, [width, onWidthChange]);

  return (
    <div
      ref={elementRef}
      className={cn(
        'h-full bg-panel flex flex-col relative pt-5 border-l',
        isCollapsed ? 'shadow-lg' : ''
      )}
      style={{ width: `${width}px` }}
    >
      {/* Header */}
      <div className="px-3 pb-2 border-b border-border/50">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium">Intelligence</span>
          {workflowProgress?.status === 'running' && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-cyan-400 border-cyan-500/50 animate-pulse">
              LIVE
            </Badge>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
        <TabsList className="grid grid-cols-4 mx-2 mt-2 bg-background/50 h-8">
          <TabsTrigger
            value="roster"
            className="text-xs data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-400 px-1"
          >
            <Users className="w-3 h-3 mr-1" />
            <span className="hidden sm:inline">Roster</span>
            {agentCount > 0 && (
              <Badge variant="secondary" className="ml-1 text-[9px] px-1 py-0 h-4">
                {agentCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="research"
            className="text-xs data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-400 px-1"
          >
            <Brain className="w-3 h-3 mr-1" />
            <span className="hidden sm:inline">Research</span>
            {hasResearch && (
              <div className="ml-1 w-1.5 h-1.5 rounded-full bg-purple-400" />
            )}
          </TabsTrigger>
          <TabsTrigger
            value="decision"
            className="text-xs data-[state=active]:bg-yellow-500/20 data-[state=active]:text-yellow-400 px-1"
          >
            <GitBranch className="w-3 h-3 mr-1" />
            <span className="hidden sm:inline">Decision</span>
            {hasDecision && (
              <div className="ml-1 w-1.5 h-1.5 rounded-full bg-yellow-400" />
            )}
          </TabsTrigger>
          <TabsTrigger
            value="console"
            className="text-xs data-[state=active]:bg-slate-500/20 data-[state=active]:text-slate-300 px-1"
          >
            <Terminal className="w-3 h-3 mr-1" />
            <span className="hidden sm:inline">Logs</span>
            {logCount > 0 && (
              <Badge variant="secondary" className="ml-1 text-[9px] px-1 py-0 h-4">
                {logCount > 99 ? '99+' : logCount}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Tab Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <TabsContent value="roster" className="h-full m-0 mt-0">
            <AgentRoster className="h-full" />
          </TabsContent>
          <TabsContent value="research" className="h-full m-0 mt-0">
            <MazoResearchViewer className="h-full" />
          </TabsContent>
          <TabsContent value="decision" className="h-full m-0 mt-0">
            <DecisionTree className="h-full" />
          </TabsContent>
          <TabsContent value="console" className="h-full m-0 mt-0">
            <RawConsole className="h-full" />
          </TabsContent>
        </div>
      </Tabs>

      {/* Resize handle */}
      {!isDragging && (
        <div
          className="absolute top-0 left-0 h-full w-1 cursor-ew-resize transition-all duration-150 z-10 hover:bg-purple-500/50"
          onMouseDown={startResize}
        />
      )}
    </div>
  );
}
