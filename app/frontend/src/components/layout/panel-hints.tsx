import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { ChevronRight, ChevronLeft, ChevronUp, PanelLeft, PanelRight, PanelBottom } from 'lucide-react';

interface PanelHintProps {
  position: 'left' | 'right' | 'bottom';
  isCollapsed: boolean;
  onClick: () => void;
  label: string;
  shortcut: string;
}

export function PanelHint({
  position,
  isCollapsed,
  onClick,
  label,
  shortcut,
}: PanelHintProps) {
  if (!isCollapsed) return null;

  const positionClasses = {
    left: 'left-0 top-1/2 -translate-y-1/2 h-24 w-6 rounded-r-md',
    right: 'right-0 top-1/2 -translate-y-1/2 h-24 w-6 rounded-l-md',
    bottom: 'bottom-0 left-1/2 -translate-x-1/2 w-24 h-6 rounded-t-md',
  };

  const Icon = position === 'left' ? ChevronRight : position === 'right' ? ChevronLeft : ChevronUp;
  const PanelIcon = position === 'left' ? PanelLeft : position === 'right' ? PanelRight : PanelBottom;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            onClick={onClick}
            className={cn(
              'absolute z-30 flex items-center justify-center',
              'bg-muted/60 hover:bg-muted border border-border/50',
              'text-muted-foreground hover:text-foreground',
              'transition-all duration-200 hover:scale-105',
              'backdrop-blur-sm',
              positionClasses[position],
              // Animation
              'animate-in fade-in-0 slide-in-from-left-2',
              position === 'right' && 'slide-in-from-right-2',
              position === 'bottom' && 'slide-in-from-bottom-2'
            )}
            aria-label={`Open ${label}`}
          >
            <Icon size={14} className="opacity-70" />
          </button>
        </TooltipTrigger>
        <TooltipContent side={position === 'bottom' ? 'top' : position === 'left' ? 'right' : 'left'}>
          <div className="flex items-center gap-2">
            <PanelIcon size={14} />
            <span>{label}</span>
            <kbd className="ml-1 px-1.5 py-0.5 text-xs bg-muted rounded">{shortcut}</kbd>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface PanelHintsProps {
  isLeftCollapsed: boolean;
  isRightCollapsed: boolean;
  isBottomCollapsed: boolean;
  onOpenLeft: () => void;
  onOpenRight: () => void;
  onOpenBottom: () => void;
}

export function PanelHints({
  isLeftCollapsed,
  isRightCollapsed,
  isBottomCollapsed,
  onOpenLeft,
  onOpenRight,
  onOpenBottom,
}: PanelHintsProps) {
  return (
    <>
      <PanelHint
        position="left"
        isCollapsed={isLeftCollapsed}
        onClick={onOpenLeft}
        label="Flows"
        shortcut="⌘B"
      />
      <PanelHint
        position="right"
        isCollapsed={isRightCollapsed}
        onClick={onOpenRight}
        label="Components"
        shortcut="⌘I"
      />
      <PanelHint
        position="bottom"
        isCollapsed={isBottomCollapsed}
        onClick={onOpenBottom}
        label="Output & Research"
        shortcut="⌘J"
      />
    </>
  );
}
