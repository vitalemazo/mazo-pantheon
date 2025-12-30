import { Settings } from '@/components/settings/settings';
import { FlowTabContent } from '@/components/tabs/flow-tab-content';
import { AutonomousTradingHub } from '@/components/autonomous/AutonomousTradingHub';
import { PortfolioHealthView } from '@/components/portfolio/PortfolioHealthView';
import { TradingDashboard } from '@/components/trading/TradingDashboard';
import { CommandCenter } from '@/components/command-center/CommandCenter';
import { Flow } from '@/types/flow';
import { ReactNode, createElement } from 'react';

export interface TabData {
  type: 'flow' | 'settings' | 'unified-workflow' | 'portfolio' | 'trading' | 'command-center';
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
        return createElement(AutonomousTradingHub);
      
      case 'portfolio':
        return createElement(PortfolioHealthView);
      
      case 'trading':
        return createElement(TradingDashboard);
      
      case 'command-center':
        return createElement(CommandCenter);
      
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
        return TabService.createUnifiedWorkflowTab();
      
      case 'portfolio':
        return TabService.createPortfolioTab();
      
      case 'trading':
        return TabService.createTradingTab();
      
      case 'command-center':
        return TabService.createCommandCenterTab();
      
      default:
        throw new Error(`Cannot restore unsupported tab type: ${savedTab.type}`);
    }
  }
} 