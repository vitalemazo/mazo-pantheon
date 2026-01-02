import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { Keyboard, PanelBottom, PanelLeft, PanelRight, Settings, Bot, Activity, BarChart3, Crosshair, Sparkles, Gauge, Users, Rocket } from 'lucide-react';
import { useState, useEffect } from 'react';
import { KeyboardShortcutsDialog } from './keyboard-shortcuts-dialog';
import { API_BASE_URL } from '@/lib/api-config';

// Feature flag for UI consolidation
const USE_CONTROL_TOWER = true;

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
  onMonitoringClick: () => void;
  onRoundTableClick: () => void;
  onControlTowerClick?: () => void;
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
  onMonitoringClick,
  onRoundTableClick,
  onControlTowerClick,
}: TopBarProps) {
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [isAutonomousActive, setIsAutonomousActive] = useState(false);
  
  // Check autonomous mode status periodically
  useEffect(() => {
    const checkStatus = async () => {
      try {
        // First check localStorage for quick response
        const localState = localStorage.getItem('aiHedgeFund_autonomous') === 'true';
        setIsAutonomousActive(localState);
        
        // Then verify with backend
        const response = await fetch(`${API_BASE_URL}/trading/scheduler/status`);
        if (response.ok) {
          const data = await response.json();
          setIsAutonomousActive(data.is_running || false);
        }
      } catch (e) {
        // Fall back to localStorage
        const localState = localStorage.getItem('aiHedgeFund_autonomous') === 'true';
        setIsAutonomousActive(localState);
      }
    };
    
    checkStatus();
    const interval = setInterval(checkStatus, 15000); // Check every 15 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <TooltipProvider delayDuration={300}>
      <div className="absolute top-0 right-0 z-40 flex items-center gap-0 py-1 px-2 bg-panel/80">
        {/* Autonomous Mode Indicator */}
        {isAutonomousActive && (
          <Tooltip>
            <TooltipTrigger asChild>
              <div 
                className="flex items-center gap-1.5 px-2 py-1 mr-2 rounded-full bg-emerald-500/20 border border-emerald-500/50 cursor-pointer hover:bg-emerald-500/30 transition-colors"
                onClick={USE_CONTROL_TOWER && onControlTowerClick ? onControlTowerClick : onUnifiedWorkflowClick}
              >
                <Sparkles className="w-3 h-3 text-emerald-400 animate-pulse" />
                <span className="text-xs font-medium text-emerald-400">AI LIVE</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <span className="font-medium">Autonomous Trading Active</span>
              <p className="text-xs text-muted-foreground">AI team is managing your portfolio</p>
            </TooltipContent>
          </Tooltip>
        )}
        
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

        {/* Control Tower (NEW - replaces AI Hedge Fund + Command Center) */}
        {USE_CONTROL_TOWER && onControlTowerClick && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={onControlTowerClick}
                className="h-8 w-8 p-0 text-indigo-400 hover:text-indigo-300 hover:bg-ramp-grey-700 transition-colors"
                aria-label="Open Control Tower"
              >
                <Rocket size={16} />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="flex flex-col gap-0.5">
              <span className="font-medium">Control Tower</span>
              <span className="text-xs text-muted-foreground">Unified command center • Autopilot • AI team</span>
            </TooltipContent>
          </Tooltip>
        )}

        {/* AI Hedge Fund (Legacy - hidden when Control Tower is enabled) */}
        {!USE_CONTROL_TOWER && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={onUnifiedWorkflowClick}
                className="h-8 w-8 p-0 text-purple-400 hover:text-purple-300 hover:bg-ramp-grey-700 transition-colors"
                aria-label="Open AI Hedge Fund"
              >
                <Bot size={16} />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="flex flex-col gap-0.5">
              <span className="font-medium">AI Hedge Fund</span>
              <span className="text-xs text-muted-foreground">Autonomous trading • Budget control</span>
            </TooltipContent>
          </Tooltip>
        )}

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

        {/* Command Center (Legacy - hidden when Control Tower is enabled) */}
        {!USE_CONTROL_TOWER && (
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
        )}

        {/* Monitoring Dashboard */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onMonitoringClick}
              className="h-8 w-8 p-0 text-cyan-400 hover:text-cyan-300 hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open monitoring dashboard"
            >
              <Gauge size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Monitoring</span>
            <span className="text-xs text-muted-foreground">System health • Alerts • Performance metrics</span>
          </TooltipContent>
        </Tooltip>

        {/* Round Table */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onRoundTableClick}
              className="h-8 w-8 p-0 text-emerald-400 hover:text-emerald-300 hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open Round Table"
            >
              <Users size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Round Table</span>
            <span className="text-xs text-muted-foreground">Full AI decision transparency • Audit pipeline</span>
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