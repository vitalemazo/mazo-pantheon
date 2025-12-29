import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { Keyboard, PanelBottom, PanelLeft, PanelRight, Settings } from 'lucide-react';
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
}

export function TopBar({
  isLeftCollapsed,
  isRightCollapsed,
  isBottomCollapsed,
  onToggleLeft,
  onToggleRight,
  onToggleBottom,
  onSettingsClick,
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