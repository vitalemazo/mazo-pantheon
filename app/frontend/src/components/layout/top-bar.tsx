/**
 * TopBar
 * 
 * Application top bar with navigation and controls.
 * 
 * Navigation (5 main tabs):
 * 1. Control Tower (rocket) - Unified command center
 * 2. Trading Workspace (briefcase) - Positions, performance, health
 * 3. Round Table (users) - AI decision transparency
 * 4. Monitoring (gauge) - System health & alerts
 * 5. Settings (gear) - Configuration
 * 
 * Plus panel toggles and keyboard shortcuts.
 */

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { 
  Keyboard, 
  PanelBottom, 
  PanelLeft, 
  PanelRight, 
  Settings, 
  Sparkles, 
  Gauge, 
  Users, 
  Rocket, 
  Briefcase,
  Info
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { KeyboardShortcutsDialog } from './keyboard-shortcuts-dialog';
import { API_BASE_URL } from '@/lib/api-config';

interface TopBarProps {
  isLeftCollapsed: boolean;
  isRightCollapsed: boolean;
  isBottomCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onToggleBottom: () => void;
  onControlTowerClick: () => void;
  onTradingWorkspaceClick: () => void;
  onRoundTableClick: () => void;
  onMonitoringClick: () => void;
  onSettingsClick: () => void;
}

export function TopBar({
  isLeftCollapsed,
  isRightCollapsed,
  isBottomCollapsed,
  onToggleLeft,
  onToggleRight,
  onToggleBottom,
  onControlTowerClick,
  onTradingWorkspaceClick,
  onRoundTableClick,
  onMonitoringClick,
  onSettingsClick,
}: TopBarProps) {
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [isAutonomousActive, setIsAutonomousActive] = useState(false);
  const [showNewLayoutBadge, setShowNewLayoutBadge] = useState(() => {
    // Show badge until user dismisses it
    return localStorage.getItem('mazo_new_layout_dismissed') !== 'true';
  });
  
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
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const dismissNewLayoutBadge = () => {
    localStorage.setItem('mazo_new_layout_dismissed', 'true');
    setShowNewLayoutBadge(false);
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div className="absolute top-0 right-0 z-40 flex items-center gap-0 py-1 px-2 bg-panel/80">
        {/* New Layout Badge */}
        {showNewLayoutBadge && (
          <Tooltip>
            <TooltipTrigger asChild>
              <div 
                className="flex items-center gap-1.5 px-2 py-1 mr-2 rounded-full bg-indigo-500/20 border border-indigo-500/50 cursor-pointer hover:bg-indigo-500/30 transition-colors"
                onClick={dismissNewLayoutBadge}
              >
                <Info className="w-3 h-3 text-indigo-400" />
                <span className="text-xs font-medium text-indigo-400">New Layout</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs">
              <div className="space-y-1">
                <span className="font-medium">Simplified Navigation</span>
                <p className="text-xs text-muted-foreground">
                  5 core views: Control Tower, Trading Workspace, Round Table, Monitoring, Settings.
                  Click to dismiss.
                </p>
              </div>
            </TooltipContent>
          </Tooltip>
        )}

        {/* Autonomous Mode Indicator */}
        {isAutonomousActive && (
          <Tooltip>
            <TooltipTrigger asChild>
              <div 
                className="flex items-center gap-1.5 px-2 py-1 mr-2 rounded-full bg-emerald-500/20 border border-emerald-500/50 cursor-pointer hover:bg-emerald-500/30 transition-colors"
                onClick={onControlTowerClick}
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
        
        {/* Panel Toggles */}
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
            <span className="font-medium">AI Activity Panel</span>
            <span className="text-xs text-muted-foreground">
              {isLeftCollapsed ? 'Show' : 'Hide'} activity feed • ⌘B
            </span>
          </TooltipContent>
        </Tooltip>

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
              {isBottomCollapsed ? 'Show' : 'Hide'} output panel • ⌘J
            </span>
          </TooltipContent>
        </Tooltip>

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
            <span className="font-medium">Intelligence Panel</span>
            <span className="text-xs text-muted-foreground">
              {isRightCollapsed ? 'Show' : 'Hide'} components • ⌘I
            </span>
          </TooltipContent>
        </Tooltip>

        {/* Divider */}
        <div className="w-px h-5 bg-ramp-grey-700 mx-1" />

        {/* Main Navigation - 5 Core Views */}
        
        {/* 1. Control Tower */}
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
            <span className="text-xs text-muted-foreground">Autopilot • AI team • Positions</span>
          </TooltipContent>
        </Tooltip>

        {/* 2. Trading Workspace */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onTradingWorkspaceClick}
              className="h-8 w-8 p-0 text-emerald-400 hover:text-emerald-300 hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open Trading Workspace"
            >
              <Briefcase size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Trading Workspace</span>
            <span className="text-xs text-muted-foreground">Performance • Health • Research</span>
          </TooltipContent>
        </Tooltip>

        {/* 3. Round Table */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onRoundTableClick}
              className="h-8 w-8 p-0 text-purple-400 hover:text-purple-300 hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open Round Table"
            >
              <Users size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Round Table</span>
            <span className="text-xs text-muted-foreground">AI decision transparency • Pipeline audit</span>
          </TooltipContent>
        </Tooltip>

        {/* 4. Monitoring */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={onMonitoringClick}
              className="h-8 w-8 p-0 text-cyan-400 hover:text-cyan-300 hover:bg-ramp-grey-700 transition-colors"
              aria-label="Open Monitoring"
            >
              <Gauge size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="flex flex-col gap-0.5">
            <span className="font-medium">Monitoring</span>
            <span className="text-xs text-muted-foreground">System health • Rate limits • Alerts</span>
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

        {/* 5. Settings */}
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
            <span className="text-xs text-muted-foreground">API keys • Preferences • ⌘,</span>
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
