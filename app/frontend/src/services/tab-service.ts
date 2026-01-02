import { Settings } from '@/components/settings/settings';
import { FlowTabContent } from '@/components/tabs/flow-tab-content';
import { AutonomousTradingHub } from '@/components/autonomous/AutonomousTradingHub';
import { PortfolioHealthView } from '@/components/portfolio/PortfolioHealthView';
import { TradingDashboard } from '@/components/trading/TradingDashboard';
import { CommandCenter } from '@/components/command-center/CommandCenter';
import { MonitoringDashboard } from '@/components/monitoring';
import { RoundTable } from '@/components/round-table';
import { ControlTower } from '@/components/control-tower';
import { Flow } from '@/types/flow';
import { ReactNode, createElement } from 'react';

// Feature flag for UI consolidation - set to true to use new Control Tower
const USE_CONTROL_TOWER = true;

export interface TabData {
  type: 'flow' | 'settings' | 'unified-workflow' | 'portfolio' | 'trading' | 'command-center' | 'monitoring' | 'round-table' | 'control-tower';
  title: string;
  flow?: Flow;
  metadata?: Record<string, any>;
}

export class TabService {
  static createTabContent(tabData: TabData): ReactNode {
    switch (tabData.type) {
      case 'flow':
        if (!tabData.flow) {
          throw new Error('Flow tab requires flow data');
        }
        return createElement(FlowTabContent, { flow: tabData.flow });
      
      case 'settings':
        return createElement(Settings);
      
      case 'unified-workflow':
        // If Control Tower is enabled, redirect to it
        if (USE_CONTROL_TOWER) {
          return createElement(ControlTower);
        }
        return createElement(AutonomousTradingHub);
      
      case 'portfolio':
        return createElement(PortfolioHealthView);
      
      case 'trading':
        return createElement(TradingDashboard);
      
      case 'command-center':
        // If Control Tower is enabled, redirect to it
        if (USE_CONTROL_TOWER) {
          return createElement(ControlTower);
        }
        return createElement(CommandCenter);
      
      case 'monitoring':
        return createElement(MonitoringDashboard);
      
      case 'round-table':
        return createElement(RoundTable);
      
      case 'control-tower':
        return createElement(ControlTower);
      
      default:
        throw new Error(`Unsupported tab type: ${tabData.type}`);
    }
  }

  static createFlowTab(flow: Flow): TabData & { content: ReactNode } {
    return {
      type: 'flow',
      title: flow.name,
      flow: flow,
      content: TabService.createTabContent({ type: 'flow', title: flow.name, flow }),
    };
  }

  static createSettingsTab(): TabData & { content: ReactNode } {
    return {
      type: 'settings',
      title: 'Settings',
      content: TabService.createTabContent({ type: 'settings', title: 'Settings' }),
    };
  }

  static createUnifiedWorkflowTab(): TabData & { content: ReactNode } {
    return {
      type: 'unified-workflow',
      title: 'AI Hedge Fund',
      content: TabService.createTabContent({ type: 'unified-workflow', title: 'AI Hedge Fund' }),
    };
  }

  static createPortfolioTab(): TabData & { content: ReactNode } {
    return {
      type: 'portfolio',
      title: 'Portfolio Health',
      content: TabService.createTabContent({ type: 'portfolio', title: 'Portfolio Health' }),
    };
  }

  static createTradingTab(): TabData & { content: ReactNode } {
    return {
      type: 'trading',
      title: 'Trading Dashboard',
      content: TabService.createTabContent({ type: 'trading', title: 'Trading Dashboard' }),
    };
  }

  static createCommandCenterTab(): TabData & { content: ReactNode } {
    return {
      type: 'command-center',
      title: 'Command Center',
      content: TabService.createTabContent({ type: 'command-center', title: 'Command Center' }),
    };
  }

  static createMonitoringTab(): TabData & { content: ReactNode } {
    return {
      type: 'monitoring',
      title: 'Monitoring',
      content: TabService.createTabContent({ type: 'monitoring', title: 'Monitoring' }),
    };
  }

  static createRoundTableTab(): TabData & { content: ReactNode } {
    return {
      type: 'round-table',
      title: 'Round Table',
      content: TabService.createTabContent({ type: 'round-table', title: 'Round Table' }),
    };
  }

  static createControlTowerTab(): TabData & { content: ReactNode } {
    return {
      type: 'control-tower',
      title: 'Control Tower',
      content: TabService.createTabContent({ type: 'control-tower', title: 'Control Tower' }),
    };
  }

  // Restore tab content for persisted tabs (used when loading from localStorage)
  static restoreTabContent(tabData: TabData): ReactNode {
    return TabService.createTabContent(tabData);
  }

  // Helper method to restore a complete tab from saved data
  static restoreTab(savedTab: TabData): TabData & { content: ReactNode } {
    switch (savedTab.type) {
      case 'flow':
        if (!savedTab.flow) {
          throw new Error('Flow tab requires flow data for restoration');
        }
        return TabService.createFlowTab(savedTab.flow);
      
      case 'settings':
        return TabService.createSettingsTab();
      
      case 'unified-workflow':
        // Redirect to Control Tower if enabled
        if (USE_CONTROL_TOWER) {
          return TabService.createControlTowerTab();
        }
        return TabService.createUnifiedWorkflowTab();
      
      case 'portfolio':
        return TabService.createPortfolioTab();
      
      case 'trading':
        return TabService.createTradingTab();
      
      case 'command-center':
        // Redirect to Control Tower if enabled
        if (USE_CONTROL_TOWER) {
          return TabService.createControlTowerTab();
        }
        return TabService.createCommandCenterTab();
      
      case 'monitoring':
        return TabService.createMonitoringTab();
      
      case 'round-table':
        return TabService.createRoundTableTab();
      
      case 'control-tower':
        return TabService.createControlTowerTab();
      
      default:
        throw new Error(`Cannot restore unsupported tab type: ${savedTab.type}`);
    }
  }
} 