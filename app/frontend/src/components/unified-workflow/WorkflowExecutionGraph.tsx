/**
 * Workflow Execution Graph - Modern Redesign
 * 
 * Visual dependency graph with modern UI/UX:
 * - Card-based node design with gradients and shadows
 * - Side panel for detailed information
 * - Drag-to-pan and smooth zoom
 * - Animated edges with progress indicators
 * - Mini-map for navigation
 * - Click to focus/select nodes
 */

import React, { useMemo, useState, useRef, useEffect, useCallback } from 'react';
import { 
  CheckCircle2, Loader2, AlertCircle, Circle, Database, Brain, FileSearch, 
  DollarSign, Activity, TrendingUp, ZoomIn, ZoomOut, RotateCcw, Info, 
  X, Maximize2, Minimize2, Map, MousePointerClick, ChevronRight
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// Import the DetailedStep type - we'll define it locally to avoid circular dependencies
interface DetailedStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  details?: any;
  startTime?: number;
  endTime?: number;
  expanded?: boolean;
  subSteps?: DetailedStep[];
  apiCalls?: any[];
  agentExecutions?: any[];
  dataRetrievals?: any[];
  mazoResearch?: any;
  tradeExecution?: any;
}

interface WorkflowExecutionGraphProps {
  steps: DetailedStep[];
  mode: string;
}

interface GraphNode {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  x: number;
  y: number;
  icon: React.ReactNode;
  category: 'data' | 'research' | 'analysis' | 'execution';
  description?: string;
  how?: string;
  why?: string;
  color: string;
  bgGradient: string;
}

interface GraphEdge {
  from: string;
  to: string;
  status: 'pending' | 'active' | 'completed';
}

// Node descriptions and explanations
const nodeExplanations: Record<string, { description: string; how: string; why: string }> = {
  'data_aggregation': {
    description: 'Collects financial data from multiple sources including prices, financial metrics, news, and insider trades.',
    how: 'Makes API calls to Financial Datasets API to retrieve historical prices, financial statements, recent news articles, and insider trading data. Data is cached to reduce API calls.',
    why: 'Provides the foundational data needed for all subsequent analysis. Without accurate and comprehensive data, agents cannot make informed decisions.'
  },
  'mazo_initial': {
    description: 'Mazo AI performs comprehensive company research and analysis using advanced financial research capabilities.',
    how: 'Uses Mazo\'s research engine to analyze company fundamentals, financial performance, competitive position, and market outlook. Can use different depth levels (quick, standard, deep) for varying levels of detail.',
    why: 'Provides expert-level research and analysis that complements the AI Hedge Fund agents. Mazo specializes in deep financial research and can uncover insights that individual agents might miss.'
  },
  'ai_hedge_fund': {
    description: 'The AI Hedge Fund system orchestrates multiple specialized AI agents to analyze the stock from different perspectives.',
    how: 'Coordinates 18 different AI agents (Warren Buffett, Peter Lynch, Technical Analyst, etc.) that each analyze the stock using their unique strategies. Agents make API calls to LLMs and process data to generate signals.',
    why: 'Diversifies analysis across multiple investment philosophies and approaches. Each agent brings a different perspective, reducing bias and providing a more comprehensive view.'
  },
  'agents': {
    description: '18 specialized AI agents process the stock data simultaneously, each using their unique investment strategy.',
    how: 'Each agent (e.g., Warren Buffett, Peter Lynch, Technical Analyst) receives the stock data and uses LLM API calls to analyze it according to their specific methodology. Agents generate signals with confidence scores and reasoning.',
    why: 'Multiple perspectives increase the robustness of the analysis. Different agents excel at different aspects (value, growth, technical, sentiment), providing a well-rounded assessment.'
  },
  'portfolio_manager': {
    description: 'The Portfolio Manager aggregates all agent signals and makes the final trading decision.',
    how: 'Takes all agent signals, weights them by confidence, and determines the overall signal (BULLISH/BEARISH/NEUTRAL). Then decides on the specific action (BUY/SELL/HOLD) and quantity based on portfolio constraints and risk management.',
    why: 'Centralizes decision-making and ensures consistency. The Portfolio Manager considers all agent inputs, portfolio constraints, and risk parameters to make the optimal trading decision.'
  },
  'mazo_deep_dive': {
    description: 'Mazo AI provides a detailed explanation of the generated signal, explaining the reasoning behind the trading decision.',
    how: 'Takes the final signal, confidence, and portfolio manager reasoning, then uses Mazo\'s research capabilities to explain why this signal was generated, what factors influenced it, and what risks/opportunities exist.',
    why: 'Provides transparency and validation. After the AI Hedge Fund generates a signal, Mazo explains it in detail, helping users understand the reasoning and build confidence in the decision.'
  },
  'trade_execution': {
    description: 'Executes the trading decision by placing orders with the broker (Alpaca).',
    how: 'Connects to Alpaca API (paper or live trading), calculates position sizes based on portfolio constraints, and places market orders. In dry-run mode, simulates the trade without actually executing.',
    why: 'Completes the workflow by actually implementing the trading decision. Allows users to automate their trading based on the AI analysis, with safety features like dry-run for testing.'
  }
};

// Category colors and styles
const categoryStyles: Record<string, { color: string; bgGradient: string; icon: React.ReactNode }> = {
  'data': {
    color: 'text-blue-600',
    bgGradient: 'from-blue-50 to-blue-100/50 dark:from-blue-950/30 dark:to-blue-900/20',
    icon: <Database className="w-5 h-5" />
  },
  'research': {
    color: 'text-purple-600',
    bgGradient: 'from-purple-50 to-purple-100/50 dark:from-purple-950/30 dark:to-purple-900/20',
    icon: <FileSearch className="w-5 h-5" />
  },
  'analysis': {
    color: 'text-orange-600',
    bgGradient: 'from-orange-50 to-orange-100/50 dark:from-orange-950/30 dark:to-orange-900/20',
    icon: <Brain className="w-5 h-5" />
  },
  'execution': {
    color: 'text-green-600',
    bgGradient: 'from-green-50 to-green-100/50 dark:from-green-950/30 dark:to-green-900/20',
    icon: <DollarSign className="w-5 h-5" />
  }
};

export function WorkflowExecutionGraph({ steps, mode }: WorkflowExecutionGraphProps) {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [showDetailsPanel, setShowDetailsPanel] = useState(false);
  const [showMinimap, setShowMinimap] = useState(true);
  const [minimapZoom, setMinimapZoom] = useState(1);
  const [minimapPan, setMinimapPan] = useState({ x: 0, y: 0 });
  const [isMinimapDragging, setIsMinimapDragging] = useState(false);
  const [minimapDragStart, setMinimapDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const minimapRef = useRef<HTMLDivElement>(null);
  
  // Define workflow structure based on mode
  const workflowStructure = useMemo(() => {
    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];
    
    const nodeWidth = 180;
    const nodeHeight = 100;
    const horizontalSpacing = 240;
    const verticalSpacing = 140;
    let currentX = 100;
    let currentY = 100;
    
    // Helper to get step status
    const getStepStatus = (stepId: string): 'pending' | 'running' | 'completed' | 'error' => {
      const step = steps.find(s => s.id === stepId);
      return step?.status || 'pending';
    };
    
    // Step 1: Data Aggregation (if enabled)
    const dataAggStep = steps.find(s => s.id === 'data_aggregation');
    if (dataAggStep) {
      const explanation = nodeExplanations['data_aggregation'];
      const categoryStyle = categoryStyles['data'];
      nodes.push({
        id: 'data_aggregation',
        name: 'Data Aggregation',
        status: getStepStatus('data_aggregation'),
        x: currentX,
        y: currentY,
        icon: categoryStyle.icon,
        category: 'data',
        description: explanation.description,
        how: explanation.how,
        why: explanation.why,
        color: categoryStyle.color,
        bgGradient: categoryStyle.bgGradient
      });
      currentX += horizontalSpacing;
    }
    
    // Step 2: Mazo Initial Research (for pre-research, full, or research-only)
    if (mode === 'research' || mode === 'pre-research' || mode === 'full') {
      const mazoInitialStep = steps.find(s => s.id === 'mazo_initial');
      if (mazoInitialStep) {
        const explanation = nodeExplanations['mazo_initial'];
        const categoryStyle = categoryStyles['research'];
        nodes.push({
          id: 'mazo_initial',
          name: mode === 'research' ? 'Mazo Research' : 'Mazo Initial Research',
          status: getStepStatus('mazo_initial'),
          x: currentX,
          y: currentY,
          icon: categoryStyle.icon,
          category: 'research',
          description: explanation.description,
          how: explanation.how,
          why: explanation.why,
          color: categoryStyle.color,
          bgGradient: categoryStyle.bgGradient
        });
        
        if (nodes.length > 1) {
          edges.push({
            from: nodes[nodes.length - 2].id,
            to: 'mazo_initial',
            status: getStepStatus('mazo_initial') === 'completed' ? 'completed' : 
                   getStepStatus('mazo_initial') === 'running' ? 'active' : 'pending'
          });
        }
        currentX += horizontalSpacing;
      }
    }
    
    // Step 3: AI Hedge Fund Analysis (for signal, pre-research, post-research, full)
    if (mode === 'signal' || mode === 'pre-research' || mode === 'post-research' || mode === 'full') {
      const aiStep = steps.find(s => s.id === 'ai_hedge_fund');
      if (aiStep) {
        const explanation = nodeExplanations['ai_hedge_fund'];
        const categoryStyle = categoryStyles['analysis'];
        nodes.push({
          id: 'ai_hedge_fund',
          name: 'AI Hedge Fund Analysis',
          status: getStepStatus('ai_hedge_fund'),
          x: currentX,
          y: currentY,
          icon: categoryStyle.icon,
          category: 'analysis',
          description: explanation.description,
          how: explanation.how,
          why: explanation.why,
          color: categoryStyle.color,
          bgGradient: categoryStyle.bgGradient
        });
        
        if (nodes.length > 0) {
          const prevNode = nodes[nodes.length - 1];
          edges.push({
            from: prevNode.id,
            to: 'ai_hedge_fund',
            status: getStepStatus('ai_hedge_fund') === 'completed' ? 'completed' : 
                   getStepStatus('ai_hedge_fund') === 'running' ? 'active' : 'pending'
          });
        }
        currentX += horizontalSpacing;
      }
      
      // Step 3b: Agents Processing
      const agentsStep = steps.find(s => s.id === 'agents');
      if (agentsStep) {
        const explanation = nodeExplanations['agents'];
        const categoryStyle = categoryStyles['analysis'];
        nodes.push({
          id: 'agents',
          name: '18 Agents Processing',
          status: getStepStatus('agents'),
          x: currentX - horizontalSpacing / 2,
          y: currentY + verticalSpacing,
          icon: <Activity className="w-5 h-5" />,
          category: 'analysis',
          description: explanation.description,
          how: explanation.how,
          why: explanation.why,
          color: categoryStyle.color,
          bgGradient: categoryStyle.bgGradient
        });
        
        edges.push({
          from: 'ai_hedge_fund',
          to: 'agents',
          status: getStepStatus('agents') === 'completed' ? 'completed' : 
                 getStepStatus('agents') === 'running' ? 'active' : 'pending'
        });
      }
      
      // Step 3c: Portfolio Manager
      const portfolioStep = steps.find(s => s.id === 'portfolio_manager');
      if (portfolioStep) {
        const explanation = nodeExplanations['portfolio_manager'];
        const categoryStyle = categoryStyles['analysis'];
        nodes.push({
          id: 'portfolio_manager',
          name: 'Portfolio Manager Decision',
          status: getStepStatus('portfolio_manager'),
          x: currentX,
          y: currentY,
          icon: <TrendingUp className="w-5 h-5" />,
          category: 'analysis',
          description: explanation.description,
          how: explanation.how,
          why: explanation.why,
          color: categoryStyle.color,
          bgGradient: categoryStyle.bgGradient
        });
        
        if (agentsStep) {
          edges.push({
            from: 'agents',
            to: 'portfolio_manager',
            status: getStepStatus('portfolio_manager') === 'completed' ? 'completed' : 
                   getStepStatus('portfolio_manager') === 'running' ? 'active' : 'pending'
          });
        } else {
          edges.push({
            from: 'ai_hedge_fund',
            to: 'portfolio_manager',
            status: getStepStatus('portfolio_manager') === 'completed' ? 'completed' : 
                   getStepStatus('portfolio_manager') === 'running' ? 'active' : 'pending'
          });
        }
        currentX += horizontalSpacing;
      }
    }
    
    // Step 4: Mazo Deep Dive
    if (mode === 'post-research' || mode === 'full') {
      const deepDiveStep = steps.find(s => s.id === 'mazo_deep_dive');
      if (deepDiveStep) {
        const explanation = nodeExplanations['mazo_deep_dive'];
        const categoryStyle = categoryStyles['research'];
        nodes.push({
          id: 'mazo_deep_dive',
          name: 'Mazo Deep Dive',
          status: getStepStatus('mazo_deep_dive'),
          x: currentX,
          y: currentY,
          icon: categoryStyle.icon,
          category: 'research',
          description: explanation.description,
          how: explanation.how,
          why: explanation.why,
          color: categoryStyle.color,
          bgGradient: categoryStyle.bgGradient
        });
        
        const prevNodeId = nodes.find(n => n.id === 'portfolio_manager')?.id || 
                          nodes.find(n => n.id === 'ai_hedge_fund')?.id || 
                          nodes[nodes.length - 1]?.id;
        if (prevNodeId) {
          edges.push({
            from: prevNodeId,
            to: 'mazo_deep_dive',
            status: getStepStatus('mazo_deep_dive') === 'completed' ? 'completed' : 
                   getStepStatus('mazo_deep_dive') === 'running' ? 'active' : 'pending'
          });
        }
        currentX += horizontalSpacing;
      }
    }
    
    // Step 5: Trade Execution
    const tradeStep = steps.find(s => s.id === 'trade_execution');
    if (tradeStep) {
      const explanation = nodeExplanations['trade_execution'];
      const categoryStyle = categoryStyles['execution'];
      nodes.push({
        id: 'trade_execution',
        name: 'Trade Execution',
        status: getStepStatus('trade_execution'),
        x: currentX,
        y: currentY,
        icon: categoryStyle.icon,
        category: 'execution',
        description: explanation.description,
        how: explanation.how,
        why: explanation.why,
        color: categoryStyle.color,
        bgGradient: categoryStyle.bgGradient
      });
      
      if (nodes.length > 1) {
        const prevNode = nodes[nodes.length - 2];
        edges.push({
          from: prevNode.id,
          to: 'trade_execution',
          status: getStepStatus('trade_execution') === 'completed' ? 'completed' : 
                 getStepStatus('trade_execution') === 'running' ? 'active' : 'pending'
        });
      }
    }
    
    return { nodes, edges };
  }, [steps, mode]);
  
  const { nodes, edges } = workflowStructure;
  
  // Calculate SVG dimensions
  const svgWidth = Math.max(1000, nodes.length > 0 ? Math.max(...nodes.map(n => n.x)) + 300 : 1000);
  const svgHeight = Math.max(500, nodes.length > 0 ? Math.max(...nodes.map(n => n.y)) + 200 : 500);
  
  // Get status styles
  const getStatusStyles = (status: string) => {
    switch (status) {
      case 'completed':
        return {
          border: 'border-green-500/50',
          bg: 'bg-green-50/80 dark:bg-green-950/20',
          shadow: 'shadow-lg shadow-green-500/20',
          text: 'text-green-700 dark:text-green-400'
        };
      case 'running':
        return {
          border: 'border-blue-500/70',
          bg: 'bg-blue-50/90 dark:bg-blue-950/30',
          shadow: 'shadow-xl shadow-blue-500/30 animate-pulse',
          text: 'text-blue-700 dark:text-blue-400'
        };
      case 'error':
        return {
          border: 'border-red-500/50',
          bg: 'bg-red-50/80 dark:bg-red-950/20',
          shadow: 'shadow-lg shadow-red-500/20',
          text: 'text-red-700 dark:text-red-400'
        };
      default:
        return {
          border: 'border-gray-300/50 dark:border-gray-700/50',
          bg: 'bg-gray-50/50 dark:bg-gray-900/50',
          shadow: 'shadow-md',
          text: 'text-gray-600 dark:text-gray-400'
        };
    }
  };
  
  // Get edge styles
  const getEdgeStyles = (edgeStatus: string) => {
    switch (edgeStatus) {
      case 'completed':
        return { color: '#10b981', width: 3, opacity: 0.8, animated: false };
      case 'active':
        return { color: '#3b82f6', width: 4, opacity: 1, animated: true };
      default:
        return { color: '#9ca3af', width: 2, opacity: 0.4, animated: false };
    }
  };
  
  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Circle className="w-5 h-5 text-gray-400" />;
    }
  };
  
  // Drag handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0 && !selectedNode) { // Left click only, not on a node
      setIsDragging(true);
      setDragStart({ x: e.clientX - panX, y: e.clientY - panY });
    }
  };
  
  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPanX(e.clientX - dragStart.x);
      setPanY(e.clientY - dragStart.y);
    }
  };
  
  const handleMouseUp = () => {
    setIsDragging(false);
  };
  
  // Zoom controls
  const handleZoomIn = () => setZoomLevel(prev => Math.min(prev + 0.15, 2.5));
  const handleZoomOut = () => setZoomLevel(prev => Math.max(prev - 0.15, 0.4));
  const handleReset = () => {
    setZoomLevel(1);
    setPanX(0);
    setPanY(0);
  };
  
  // Node click handler
  const handleNodeClick = (nodeId: string) => {
    setSelectedNode(nodeId);
    setShowDetailsPanel(true);
  };
  
  // Get selected node details
  const selectedNodeData = useMemo(() => {
    if (!selectedNode) return null;
    const node = nodes.find(n => n.id === selectedNode);
    const step = steps.find(s => s.id === selectedNode);
    return node && step ? { node, step } : null;
  }, [selectedNode, nodes, steps]);
  
  // Auto-fit to viewport
  const handleFitToView = () => {
    if (nodes.length === 0 || !containerRef.current) return;
    
    const minX = Math.min(...nodes.map(n => n.x));
    const maxX = Math.max(...nodes.map(n => n.x));
    const minY = Math.min(...nodes.map(n => n.y));
    const maxY = Math.max(...nodes.map(n => n.y));
    
    const width = maxX - minX + 360;
    const height = maxY - minY + 200;
    
    const containerWidth = containerRef.current.clientWidth;
    const containerHeight = containerRef.current.clientHeight;
    
    const scaleX = containerWidth / width;
    const scaleY = containerHeight / height;
    const scale = Math.min(scaleX, scaleY, 1) * 0.9; // 90% to add padding
    
    setZoomLevel(scale);
    setPanX((containerWidth - (minX + maxX) * scale) / 2);
    setPanY((containerHeight - (minY + maxY) * scale) / 2);
  };
  
  if (nodes.length === 0) {
    return (
      <Card className="p-4">
        <h3 className="text-lg font-semibold mb-4">Workflow Execution Graph</h3>
        <div className="text-sm text-muted-foreground text-center py-8">
          Configure and run workflow to see execution graph
        </div>
      </Card>
    );
  }
  
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Workflow Execution Graph</h3>
        <div className="flex items-center gap-2">
          {/* Zoom Controls */}
          <div className="flex items-center gap-1 border rounded-lg p-1 bg-background">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleZoomOut}
              disabled={zoomLevel <= 0.4}
              className="h-7 w-7 p-0"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </Button>
            <span className="text-xs px-2 min-w-[3.5rem] text-center font-medium">
              {Math.round(zoomLevel * 100)}%
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleZoomIn}
              disabled={zoomLevel >= 2.5}
              className="h-7 w-7 p-0"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </Button>
            <div className="w-px h-4 bg-border mx-1" />
            <Button
              variant="ghost"
              size="sm"
              onClick={handleFitToView}
              className="h-7 w-7 p-0"
              title="Fit to View"
            >
              <Maximize2 className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              className="h-7 w-7 p-0"
              title="Reset View"
            >
              <RotateCcw className="w-4 h-4" />
            </Button>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowMinimap(!showMinimap)}
            className="h-7 px-2"
            title="Toggle Mini-map"
          >
            <Map className="w-4 h-4" />
          </Button>
        </div>
      </div>
      
      <div className="mb-3 p-2 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900 rounded-lg">
        <div className="flex items-center gap-2 text-xs text-blue-700 dark:text-blue-300">
          <MousePointerClick className="w-4 h-4" />
          <span className="font-medium">Click any node below to view detailed information</span>
          <ChevronRight className="w-3 h-3 ml-auto" />
        </div>
      </div>
      
      <div className="relative flex gap-4">
        {/* Main Graph Area */}
        <div 
          ref={containerRef}
          className="relative flex-1 overflow-hidden border rounded-lg bg-gradient-to-br from-gray-50 to-gray-100/50 dark:from-gray-950 dark:to-gray-900/50"
          style={{ minHeight: '500px', maxHeight: '700px' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={(e) => {
            if (e.ctrlKey || e.metaKey) {
              e.preventDefault();
              const delta = e.deltaY > 0 ? -0.1 : 0.1;
              setZoomLevel(prev => Math.max(0.4, Math.min(2.5, prev + delta)));
            }
          }}
        >
          <div
            ref={graphContainerRef}
            className="w-full h-full overflow-auto"
            style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
          >
            <svg
              ref={svgRef}
              width={svgWidth * zoomLevel}
              height={svgHeight * zoomLevel}
              className="w-full h-full"
              style={{ minHeight: '500px' }}
            >
              <defs>
                {/* Gradient definitions */}
                <linearGradient id="edgeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.2" />
                </linearGradient>
                {/* Arrow marker */}
                <marker
                  id="arrowhead"
                  markerWidth="10"
                  markerHeight="10"
                  refX="9"
                  refY="3"
                  orient="auto"
                >
                  <polygon points="0 0, 10 3, 0 6" fill="#3b82f6" />
                </marker>
              </defs>
              
              <defs>
                <style>{`
                  @keyframes pulse-ring {
                    0%, 100% { opacity: 0.6; }
                    50% { opacity: 0.3; }
                  }
                `}</style>
              </defs>
              <g transform={`translate(${panX}, ${panY}) scale(${zoomLevel})`}>
                {/* Draw edges first */}
                {edges.map((edge, idx) => {
                  const fromNode = nodes.find(n => n.id === edge.from);
                  const toNode = nodes.find(n => n.id === edge.to);
                  if (!fromNode || !toNode) return null;
                  
                  const fromX = fromNode.x + 90;
                  const fromY = fromNode.y + 50;
                  const toX = toNode.x + 90;
                  const toY = toNode.y + 50;
                  
                  const dx = toX - fromX;
                  const dy = toY - fromY;
                  const distance = Math.sqrt(dx * dx + dy * dy);
                  const angle = Math.atan2(dy, dx);
                  
                  const arrowLength = 12;
                  const arrowAngle = Math.PI / 6;
                  const arrowX = toX - 90 * Math.cos(angle);
                  const arrowY = toY - 90 * Math.sin(angle);
                  
                  const edgeStyles = getEdgeStyles(edge.status);
                  
                  return (
                    <g key={`edge-${idx}`}>
                      {/* Animated edge line */}
                      <line
                        x1={fromX}
                        y1={fromY}
                        x2={arrowX}
                        y2={arrowY}
                        stroke={edgeStyles.color}
                        strokeWidth={edgeStyles.width}
                        opacity={edgeStyles.opacity}
                        strokeDasharray={edge.status === 'pending' ? '8,4' : '0'}
                        markerEnd={edge.status !== 'pending' ? 'url(#arrowhead)' : undefined}
                      >
                        {edgeStyles.animated && (
                          <animate
                            attributeName="stroke-dasharray"
                            values="0,1000;1000,0"
                            dur="2s"
                            repeatCount="indefinite"
                          />
                        )}
                      </line>
                      {/* Arrow head */}
                      {edge.status !== 'pending' && (
                        <path
                          d={`M ${arrowX} ${arrowY} L ${arrowX - arrowLength * Math.cos(angle - arrowAngle)} ${arrowY - arrowLength * Math.sin(angle - arrowAngle)} L ${arrowX - arrowLength * Math.cos(angle + arrowAngle)} ${arrowY - arrowLength * Math.sin(angle + arrowAngle)} Z`}
                          fill={edgeStyles.color}
                          opacity={edgeStyles.opacity}
                        />
                      )}
                    </g>
                  );
                })}
                
                {/* Draw nodes */}
                {nodes.map((node) => {
                  const step = steps.find(s => s.id === node.id);
                  const actualStatus = step?.status || 'pending';
                  const executionTime = step?.startTime 
                    ? step.endTime 
                      ? ((step.endTime - step.startTime) / 1000).toFixed(1) + 's'
                      : ((Date.now() - step.startTime) / 1000).toFixed(1) + 's'
                    : null;
                  
                  const isSelected = selectedNode === node.id;
                  const isHovered = hoveredNode === node.id;
                  const statusStyles = getStatusStyles(actualStatus);
                  
                  return (
                    <g 
                      key={node.id}
                      onMouseEnter={() => setHoveredNode(node.id)}
                      onMouseLeave={() => setHoveredNode(null)}
                    >
                      {/* Click indicator ring (appears on hover) */}
                      {isHovered && !isSelected && (
                        <rect
                          x={node.x - 4}
                          y={node.y - 4}
                          width={188}
                          height={108}
                          rx={16}
                          fill="none"
                          stroke="#3b82f6"
                          strokeWidth={3}
                          strokeDasharray="8,4"
                          opacity={0.6}
                          style={{
                            animation: 'pulse-ring 2s ease-in-out infinite',
                            pointerEvents: 'none'
                          }}
                        />
                      )}
                      
                      {/* Node card with gradient background */}
                      <rect
                        x={node.x}
                        y={node.y}
                        width={180}
                        height={100}
                        rx={12}
                        className={`${statusStyles.border} ${statusStyles.bg} ${statusStyles.shadow} border-2`}
                        fill="white"
                        fillOpacity={actualStatus === 'running' ? 0.95 : 1}
                        style={{
                          cursor: 'pointer',
                          transition: 'all 0.3s ease',
                          transform: isSelected ? 'scale(1.05)' : isHovered ? 'scale(1.03)' : 'scale(1)',
                          filter: isHovered ? 'brightness(1.05)' : 'brightness(1)',
                        }}
                        onClick={() => handleNodeClick(node.id)}
                      />
                      
                      {/* Gradient overlay */}
                      <rect
                        x={node.x}
                        y={node.y}
                        width={180}
                        height={100}
                        rx={12}
                        className={`bg-gradient-to-br ${node.bgGradient}`}
                        fillOpacity={0.3}
                        style={{ pointerEvents: 'none' }}
                      />
                      
                      {/* Node content */}
                      <foreignObject 
                        x={node.x + 12} 
                        y={node.y + 12} 
                        width={156} 
                        height={76}
                        style={{ pointerEvents: 'none' }}
                      >
                        <div className="flex flex-col h-full">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              {getStatusIcon(actualStatus)}
                              <div className={node.color}>{node.icon}</div>
                            </div>
                            <div className="flex items-center gap-1">
                              {executionTime && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                                  {executionTime}
                                </Badge>
                              )}
                              {/* Click indicator icon */}
                              {isHovered && (
                                <MousePointerClick className="w-3.5 h-3.5 text-blue-500 animate-pulse" />
                              )}
                            </div>
                          </div>
                          <div className={`text-sm font-semibold ${statusStyles.text} leading-tight`}>
                            {node.name}
                          </div>
                          <div className="mt-auto flex items-center justify-between">
                            <span className="text-[10px] text-muted-foreground">
                              {node.category.charAt(0).toUpperCase() + node.category.slice(1)}
                            </span>
                            {isHovered && (
                              <span className="text-[10px] text-blue-600 dark:text-blue-400 font-medium flex items-center gap-1">
                                Click for details
                                <ChevronRight className="w-3 h-3" />
                              </span>
                            )}
                          </div>
                        </div>
                      </foreignObject>
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>
        </div>
        
        {/* Details Panel */}
        {showDetailsPanel && selectedNodeData && (
          <Card className="w-80 flex-shrink-0 border-l">
            <div className="p-4 border-b flex items-center justify-between">
              <h4 className="font-semibold text-sm">Step Details</h4>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowDetailsPanel(false);
                  setSelectedNode(null);
                }}
                className="h-6 w-6 p-0"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
            <div className="h-[600px] overflow-y-auto">
              <div className="p-4 space-y-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    {selectedNodeData.node.icon}
                    <h5 className="font-semibold">{selectedNodeData.node.name}</h5>
                  </div>
                  <Badge variant="outline" className="mb-2">
                    {selectedNodeData.step.status}
                  </Badge>
                  {selectedNodeData.step.startTime && (
                    <div className="text-xs text-muted-foreground">
                      {selectedNodeData.step.endTime 
                        ? `Completed in ${((selectedNodeData.step.endTime - selectedNodeData.step.startTime) / 1000).toFixed(1)}s`
                        : `Running for ${((Date.now() - selectedNodeData.step.startTime) / 1000).toFixed(1)}s`}
                    </div>
                  )}
                </div>
                
                <div className="border-t pt-4">
                  <h6 className="font-semibold text-xs mb-1">Description</h6>
                  <p className="text-xs text-muted-foreground">
                    {selectedNodeData.node.description}
                  </p>
                </div>
                
                <div className="border-t pt-4">
                  <h6 className="font-semibold text-xs mb-1">How it works</h6>
                  <p className="text-xs text-muted-foreground">
                    {selectedNodeData.node.how}
                  </p>
                </div>
                
                <div className="border-t pt-4">
                  <h6 className="font-semibold text-xs mb-1">Why it's important</h6>
                  <p className="text-xs text-muted-foreground">
                    {selectedNodeData.node.why}
                  </p>
                </div>
              </div>
            </div>
          </Card>
        )}
      </div>
      
      {/* Enhanced Mini-map */}
      {showMinimap && (
        <Card className="mt-4 p-3">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Map className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-semibold">Workflow Overview</span>
            </div>
            <div className="flex items-center gap-2">
              {/* Mini-map Zoom Controls */}
              <div className="flex items-center gap-1 border rounded-md p-0.5 bg-background">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMinimapZoom(prev => Math.max(0.5, prev - 0.25))}
                  disabled={minimapZoom <= 0.5}
                  className="h-6 w-6 p-0"
                  title="Zoom Out Mini-map"
                >
                  <ZoomOut className="w-3 h-3" />
                </Button>
                <span className="text-[10px] px-1.5 min-w-[2.5rem] text-center font-medium">
                  {Math.round(minimapZoom * 100)}%
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMinimapZoom(prev => Math.min(3, prev + 0.25))}
                  disabled={minimapZoom >= 3}
                  className="h-6 w-6 p-0"
                  title="Zoom In Mini-map"
                >
                  <ZoomIn className="w-3 h-3" />
                </Button>
                <div className="w-px h-3 bg-border mx-0.5" />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setMinimapZoom(1);
                    setMinimapPan({ x: 0, y: 0 });
                  }}
                  className="h-6 w-6 p-0"
                  title="Reset Mini-map View"
                >
                  <RotateCcw className="w-3 h-3" />
                </Button>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowMinimap(false)}
                className="h-6 w-6 p-0"
              >
                <Minimize2 className="w-3 h-3" />
              </Button>
            </div>
          </div>
          
          <div 
            ref={minimapRef}
            className="relative h-40 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 rounded-lg border overflow-hidden"
            style={{ cursor: isMinimapDragging ? 'grabbing' : 'grab' }}
            onMouseDown={(e) => {
              if (e.button === 0 && minimapRef.current) {
                const rect = minimapRef.current.getBoundingClientRect();
                setIsMinimapDragging(true);
                setMinimapDragStart({ 
                  x: e.clientX - rect.left,
                  y: e.clientY - rect.top
                });
              }
            }}
            onMouseMove={(e) => {
              if (isMinimapDragging && minimapRef.current) {
                const rect = minimapRef.current.getBoundingClientRect();
                const deltaX = (e.clientX - rect.left - minimapDragStart.x) * (svgWidth / minimapZoom) / rect.width;
                const deltaY = (e.clientY - rect.top - minimapDragStart.y) * (svgHeight / minimapZoom) / rect.height;
                setMinimapPan({
                  x: minimapPan.x - deltaX,
                  y: minimapPan.y - deltaY
                });
                setMinimapDragStart({
                  x: e.clientX - rect.left,
                  y: e.clientY - rect.top
                });
              }
            }}
            onMouseUp={() => setIsMinimapDragging(false)}
            onMouseLeave={() => setIsMinimapDragging(false)}
            onWheel={(e) => {
              if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                const delta = e.deltaY > 0 ? -0.1 : 0.1;
                setMinimapZoom(prev => Math.max(0.5, Math.min(3, prev + delta)));
              }
            }}
          >
            <svg 
              width="100%" 
              height="100%" 
              viewBox={`${minimapPan.x} ${minimapPan.y} ${svgWidth / minimapZoom} ${svgHeight / minimapZoom}`}
              className="absolute inset-0"
              preserveAspectRatio="xMidYMid meet"
            >
              {/* Draw edges in mini-map */}
              {edges.map((edge, idx) => {
                const fromNode = nodes.find(n => n.id === edge.from);
                const toNode = nodes.find(n => n.id === edge.to);
                if (!fromNode || !toNode) return null;
                
                const fromX = fromNode.x + 90;
                const fromY = fromNode.y + 50;
                const toX = toNode.x + 90;
                const toY = toNode.y + 50;
                
                const edgeStyles = getEdgeStyles(edge.status);
                
                return (
                  <line
                    key={`minimap-edge-${idx}`}
                    x1={fromX}
                    y1={fromY}
                    x2={toX}
                    y2={toY}
                    stroke={edgeStyles.color}
                    strokeWidth={1.5}
                    opacity={edgeStyles.opacity * 0.6}
                  />
                );
              })}
              
              {/* Draw nodes with labels */}
              {nodes.map((node) => {
                const step = steps.find(s => s.id === node.id);
                const status = step?.status || 'pending';
                const isSelected = selectedNode === node.id;
                
                // Status colors
                const statusColor = status === 'completed' 
                  ? '#10b981' 
                  : status === 'running' 
                  ? '#3b82f6' 
                  : status === 'error'
                  ? '#ef4444'
                  : '#9ca3af';
                
                // Category colors for better distinction
                const categoryColors: Record<string, string> = {
                  'data': '#3b82f6',
                  'research': '#a855f7',
                  'analysis': '#f97316',
                  'execution': '#10b981'
                };
                const nodeColor = categoryColors[node.category] || statusColor;
                
                return (
                  <g key={`minimap-node-${node.id}`}>
                    {/* Node rectangle */}
                    <rect
                      x={node.x}
                      y={node.y}
                      width={180}
                      height={100}
                      rx={6}
                      fill={nodeColor}
                      opacity={isSelected ? 0.9 : status === 'running' ? 0.7 : 0.5}
                      stroke={isSelected ? '#3b82f6' : statusColor}
                      strokeWidth={isSelected ? 2 : 1}
                      style={{ cursor: 'pointer' }}
                      onClick={() => {
                        setSelectedNode(node.id);
                        setShowDetailsPanel(true);
                        // Scroll to node in main view
                        if (containerRef.current && graphContainerRef.current) {
                          const nodeCenterX = (node.x + 90) * zoomLevel + panX;
                          const nodeCenterY = (node.y + 50) * zoomLevel + panY;
                          const containerWidth = containerRef.current.clientWidth;
                          const containerHeight = containerRef.current.clientHeight;
                          
                          graphContainerRef.current.scrollTo({
                            left: nodeCenterX - containerWidth / 2,
                            top: nodeCenterY - containerHeight / 2,
                            behavior: 'smooth'
                          });
                        }
                      }}
                    />
                    
                    {/* Node label */}
                    <text
                      x={node.x + 90}
                      y={node.y + 55}
                      textAnchor="middle"
                      fontSize="10"
                      fill={status === 'pending' ? '#6b7280' : '#ffffff'}
                      fontWeight="600"
                      style={{ 
                        pointerEvents: 'none',
                        userSelect: 'none',
                        textShadow: status !== 'pending' ? '0 1px 2px rgba(0,0,0,0.3)' : 'none'
                      }}
                    >
                      {node.name.length > 15 
                        ? node.name.substring(0, 12) + '...' 
                        : node.name}
                    </text>
                    
                    {/* Status indicator dot */}
                    <circle
                      cx={node.x + 15}
                      cy={node.y + 15}
                      r={4}
                      fill={statusColor}
                      opacity={1}
                    />
                  </g>
                );
              })}
              
              {/* Viewport indicator (shows current view area) */}
              {containerRef.current && (
                <rect
                  x={(panX / zoomLevel)}
                  y={(panY / zoomLevel)}
                  width={(containerRef.current.clientWidth / zoomLevel) * 0.8}
                  height={(containerRef.current.clientHeight / zoomLevel) * 0.8}
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  strokeDasharray="4,4"
                  opacity={0.6}
                  style={{ pointerEvents: 'none' }}
                />
              )}
            </svg>
            
            {/* Legend */}
            <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between text-[10px] bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm rounded px-2 py-1 border">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                  <span>Data</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-purple-500"></div>
                  <span>Research</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-orange-500"></div>
                  <span>Analysis</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span>Execution</span>
                </div>
              </div>
              <div className="text-muted-foreground flex items-center gap-2">
                <span>Click nodes to navigate</span>
                <span className="text-[9px] opacity-70">• Ctrl/Cmd + scroll to zoom</span>
              </div>
            </div>
          </div>
        </Card>
      )}
    </Card>
  );
}
