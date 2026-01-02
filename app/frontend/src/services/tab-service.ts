/**
 * TabService
 * 
 * Manages tab creation and content for the main application tabs.
 * 
 * Primary tabs (v2 architecture):
 * - control-tower: Unified command center (replaces AI Hedge Fund + Command Center)
 * - trading-workspace: Unified trading view (replaces Trading Dashboard + Portfolio Health)
 * - round-table: AI decision transparency and audit
 * - monitoring: Infrastructure and system health
 * - settings: Configuration and API keys
 * - flow: Custom workflow editor
 * 
 * Legacy tab types are automatically redirected to their new equivalents.
 */

import { Settings } from '@/components/settings/settings';
import { FlowTabContent } from '@/components/tabs/flow-tab-content';
import { MonitoringDashboard } from '@/components/monitoring';
import { RoundTable } from '@/components/round-table';
import { ControlTower } from '@/components/control-tower';
import { TradingWorkspace } from '@/components/trading-workspace';
import { Flow } from '@/types/flow';
import { ReactNode, createElement } from 'react';

/**
 * Canonical tab types for the v2 architecture.
 * Legacy types are still accepted for backward compatibility but redirect to new types.
 */
export type TabType = 
  | 'control-tower'
  | 'trading-workspace'
  | 'round-table'
  | 'monitoring'
  | 'settings'
  | 'flow'
  // Legacy types (redirected)
  | 'unified-workflow'  // → control-tower
  | 'command-center'    // → control-tower
  | 'portfolio'         // → trading-workspace
  | 'trading';          // → trading-workspace

export interface TabData {
  type: TabType;
  title: string;
  flow?: Flow;
  metadata?: Record<string, any>;
  /** For Round Table: auto-select this workflow ID */
  workflowId?: string;
}

/**
 * Maps legacy tab types to their canonical v2 equivalents.
 */
const LEGACY_TAB_REDIRECTS: Record<string, TabType> = {
  'unified-workflow': 'control-tower',
  'command-center': 'control-tower',
  'portfolio': 'trading-workspace',
  'trading': 'trading-workspace',
};

export class TabService {
  /**
   * Creates the React content for a tab based on its type.
   * Automatically redirects legacy tab types to their v2 equivalents.
   */
  static createTabContent(tabData: TabData): ReactNode {
    // Check for legacy redirect
    const canonicalType = LEGACY_TAB_REDIRECTS[tabData.type] || tabData.type;
    
    switch (canonicalType) {
      case 'flow':
        if (!tabData.flow) {
          throw new Error('Flow tab requires flow data');
        }
        return createElement(FlowTabContent, { flow: tabData.flow });
      
      case 'settings':
        return createElement(Settings);
      
      case 'control-tower':
        return createElement(ControlTower);
      
      case 'trading-workspace':
        return createElement(TradingWorkspace);
      
      case 'monitoring':
        return createElement(MonitoringDashboard);
      
      case 'round-table':
        return createElement(RoundTable, { workflowId: tabData.workflowId });
      
      default:
        throw new Error(`Unsupported tab type: ${tabData.type}`);
    }
  }

  // ========================================
  // Primary Tab Creators (v2 Architecture)
  // ========================================

  static createControlTowerTab(): TabData & { content: ReactNode } {
    return {
      type: 'control-tower',
      title: 'Control Tower',
      content: TabService.createTabContent({ type: 'control-tower', title: 'Control Tower' }),
    };
  }

  static createTradingWorkspaceTab(): TabData & { content: ReactNode } {
    return {
      type: 'trading-workspace',
      title: 'Trading Workspace',
      content: TabService.createTabContent({ type: 'trading-workspace', title: 'Trading Workspace' }),
    };
  }

  static createRoundTableTab(workflowId?: string): TabData & { content: ReactNode } {
    return {
      type: 'round-table',
      title: 'Round Table',
      workflowId,
      content: TabService.createTabContent({ type: 'round-table', title: 'Round Table', workflowId }),
    };
  }

  static createMonitoringTab(): TabData & { content: ReactNode } {
    return {
      type: 'monitoring',
      title: 'Monitoring',
      content: TabService.createTabContent({ type: 'monitoring', title: 'Monitoring' }),
    };
  }

  static createSettingsTab(): TabData & { content: ReactNode } {
    return {
      type: 'settings',
      title: 'Settings',
      content: TabService.createTabContent({ type: 'settings', title: 'Settings' }),
    };
  }

  static createFlowTab(flow: Flow): TabData & { content: ReactNode } {
    return {
      type: 'flow',
      title: flow.name,
      flow: flow,
      content: TabService.createTabContent({ type: 'flow', title: flow.name, flow }),
    };
  }

  // ========================================
  // Legacy Tab Creators (Backward Compatible)
  // These redirect to their v2 equivalents
  // ========================================

  /** @deprecated Use createControlTowerTab instead */
  static createUnifiedWorkflowTab(): TabData & { content: ReactNode } {
    return TabService.createControlTowerTab();
  }

  /** @deprecated Use createControlTowerTab instead */
  static createCommandCenterTab(): TabData & { content: ReactNode } {
    return TabService.createControlTowerTab();
  }

  /** @deprecated Use createTradingWorkspaceTab instead */
  static createPortfolioTab(): TabData & { content: ReactNode } {
    return TabService.createTradingWorkspaceTab();
  }

  /** @deprecated Use createTradingWorkspaceTab instead */
  static createTradingTab(): TabData & { content: ReactNode } {
    return TabService.createTradingWorkspaceTab();
  }

  // ========================================
  // Tab Restoration (for localStorage persistence)
  // ========================================

  /**
   * Restores tab content for persisted tabs.
   */
  static restoreTabContent(tabData: TabData): ReactNode {
    return TabService.createTabContent(tabData);
  }

  /**
   * Restores a complete tab from saved data.
   * Handles legacy tab types by redirecting to v2 equivalents.
   */
  static restoreTab(savedTab: TabData): TabData & { content: ReactNode } {
    // Check for legacy redirect
    const canonicalType = LEGACY_TAB_REDIRECTS[savedTab.type] || savedTab.type;
    
    switch (canonicalType) {
      case 'flow':
        if (!savedTab.flow) {
          throw new Error('Flow tab requires flow data for restoration');
        }
        return TabService.createFlowTab(savedTab.flow);
      
      case 'settings':
        return TabService.createSettingsTab();
      
      case 'control-tower':
        return TabService.createControlTowerTab();
      
      case 'trading-workspace':
        return TabService.createTradingWorkspaceTab();
      
      case 'monitoring':
        return TabService.createMonitoringTab();
      
      case 'round-table':
        return TabService.createRoundTableTab(savedTab.workflowId);
      
      default:
        // For any unknown type, default to Control Tower
        console.warn(`Unknown tab type "${savedTab.type}", defaulting to Control Tower`);
        return TabService.createControlTowerTab();
    }
  }
}
