import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { Keyboard, PanelBottom, PanelLeft, PanelRight, Settings, Workflow, Activity, BarChart3, Crosshair } from 'lucide-react';
import { useState } from 'react';
import { KeyboardShortcutsDialog } from './keyboard-shortcuts-dialog';

interface TopBarProps {
  isLeftCollapsed: boolean;
  isRightCollapsed: boolean;
  isBottomCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onToggleBottom: () => void;
  onSettingsClick: () => void;
  onUnifiedWorkflowClick: () => void;
  onPortfolioClick: () => void;
  onTradingClick: () => void;
  onCommandCenterClick: () => void;
}

export function TopBar({
  isLeftCollapsed,
  isRightCollapsed,
  isBottomCollapsed,
  onToggleLeft,
  onToggleRight,
  onToggleBottom,
  onSettingsClick,
  onUnifiedWorkflowClick,
  onPortfolioClick,
  onTradingClick,
  onCommandCenterClick,
}: TopBarProps) {
  const [showShortcuts, setShowShortcuts] = useState(false);

  return (
    <TooltipProvider delayDuration={300}>
      <div className="absolute top-0 right-0 z-40 flex items-center gap-0 py-1 px-2 bg-panel/80">
        {/* Left Sidebar Toggle */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleLeft}
              className={cn(
                "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
                !isLeftCollapsed && "text-foreground"
              )}
              aria-label="Toggle left sidebar"
            >
              <PanelLeft size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Flows Panel</span>
            <span className="text-xs text-muted-foreground">
              {isLeftCollapsed ? 'Show' : 'Hide'} flow list • ⌘B
            </span>
          </TooltipContent>
        </Tooltip>

        {/* Bottom Panel Toggle */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleBottom}
              className={cn(
                "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
                !isBottomCollapsed && "text-foreground"
              )}
              aria-label="Toggle bottom panel"
            >
              <PanelBottom size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Output & Research</span>
            <span className="text-xs text-muted-foreground">
              {isBottomCollapsed ? 'Show' : 'Hide'} output and Mazo research • ⌘J
            </span>
          </TooltipContent>
        </Tooltip>

        {/* Right Sidebar Toggle */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleRight}
              className={cn(
                "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
                !isRightCollapsed && "text-foreground"
              )}
              aria-label="Toggle right sidebar"
            >
              <PanelRight size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Components Panel</span>
            <span className="text-xs text-muted-foreground">
              {isRightCollapsed ? 'Show' : 'Hide'} drag & drop components • ⌘I
            </span>
          </TooltipContent>
        </Tooltip>

        {/* Divider */}
        <div className="w-px h-5 bg-ramp-grey-700 mx-1" />

        {/* Unified Workflow */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onUnifiedWorkflowClick}
              className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open unified workflow"
            >
              <Workflow size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Unified Workflow</span>
            <span className="text-xs text-muted-foreground">Mazo Pantheon</span>
          </TooltipContent>
        </Tooltip>

        {/* Portfolio Health */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onPortfolioClick}
              className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open portfolio health"
            >
              <Activity size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Portfolio Health</span>
            <span className="text-xs text-muted-foreground">AI-powered portfolio analysis • ⌘P</span>
          </TooltipContent>
        </Tooltip>

        {/* Trading Dashboard */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onTradingClick}
              className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open trading dashboard"
            >
              <BarChart3 size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Trading Dashboard</span>
            <span className="text-xs text-muted-foreground">Performance & strategies • ⌘T</span>
          </TooltipContent>
        </Tooltip>

        {/* Command Center */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onCommandCenterClick}
              className="h-8 w-8 p-0 text-amber-400 hover:text-amber-300 hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open command center"
            >
              <Crosshair size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Command Center</span>
            <span className="text-xs text-muted-foreground">Unified view • Trade history • Agent leaderboard</span>
          </TooltipContent>
        </Tooltip>

        {/* Keyboard Shortcuts */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowShortcuts(true)}
              className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
              aria-label="Keyboard shortcuts"
            >
              <Keyboard size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            <span>Keyboard Shortcuts • ⌘/</span>
          </TooltipContent>
        </Tooltip>

        {/* Settings */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onSettingsClick}
              className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open settings"
            >
              <Settings size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Settings</span>
            <span className="text-xs text-muted-foreground">API keys and preferences • ⌘,</span>
          </TooltipContent>
        </Tooltip>
      </div>

      {/* Keyboard Shortcuts Dialog */}
      <KeyboardShortcutsDialog
        open={showShortcuts}
        onOpenChange={setShowShortcuts}
      />
    </TooltipProvider>
  );
} 