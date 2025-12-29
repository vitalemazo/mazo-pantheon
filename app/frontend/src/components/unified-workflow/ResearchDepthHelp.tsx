import React, { useState } from 'react';
import { Info, X, ChevronRight, Zap, Target, Layers, Globe, Brain } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface ResearchDepthInfo {
  depth: string;
  title: string;
  icon: React.ReactNode;
  description: string;
  useCase: string;
  executionTime: string;
  coverage: string[];
  queryExample: string;
  whenToUse: string[];
  limitations: string[];
  apiCalls: {
    llmCalls: string;
    estimatedTokens: string;
    tokenBreakdown: string;
    costEstimate: string;
  };
}

const researchDepths: ResearchDepthInfo[] = [
  {
    depth: 'quick',
    title: 'Quick Research',
    icon: <Zap className="w-5 h-5 text-yellow-500" />,
    description: 'Fast, high-level overview of recent performance and outlook. Minimal analysis for quick decisions.',
    useCase: 'Use when you need a rapid assessment or are screening multiple tickers. Best for getting a general sense of a company quickly.',
    executionTime: '~30-60 seconds',
    apiCalls: {
      llmCalls: '1-2 LLM API calls',
      estimatedTokens: '~1,000-2,000 tokens',
      tokenBreakdown: 'Input: ~300-500 tokens (query) | Output: ~700-1,500 tokens (response)',
      costEstimate: 'GPT-4: ~$0.03-0.06 | GPT-3.5: ~$0.001-0.002 | Claude 3.5: ~$0.01-0.02'
    },
    coverage: [
      'Recent financial performance snapshot',
      'Current market outlook',
      'Basic company overview',
      'Key highlights only'
    ],
    queryExample: "Give me a quick overview of TSLA's recent performance and outlook.",
    whenToUse: [
      'Screening multiple stocks quickly',
      'Getting a first impression',
      'When time is critical',
      'Initial due diligence phase',
      'Market scanning and filtering'
    ],
    limitations: [
      'Limited historical analysis',
      'No deep competitive analysis',
      'Minimal risk assessment',
      'No detailed valuation metrics',
      'Surface-level insights only'
    ]
  },
  {
    depth: 'standard',
    title: 'Standard Research',
    icon: <Target className="w-5 h-5 text-blue-500" />,
    description: 'Comprehensive analysis covering key financial metrics, competitive position, risks, and valuation. Balanced depth and speed.',
    useCase: 'Use for most investment decisions. Provides thorough analysis without excessive time. Best default choice for single-ticker analysis.',
    executionTime: '~2-5 minutes',
    apiCalls: {
      llmCalls: '2-4 LLM API calls',
      estimatedTokens: '~3,000-5,000 tokens',
      tokenBreakdown: 'Input: ~800-1,200 tokens (detailed query) | Output: ~2,200-3,800 tokens (comprehensive response)',
      costEstimate: 'GPT-4: ~$0.09-0.15 | GPT-3.5: ~$0.003-0.005 | Claude 3.5: ~$0.03-0.05'
    },
    coverage: [
      'Recent financial performance (detailed)',
      'Competitive position and market share',
      'Key risks and opportunities',
      'Valuation assessment vs peers',
      'Investment recommendation',
      'Management overview',
      'Growth drivers and headwinds'
    ],
    queryExample: `Analyze TSLA covering:
1. Recent financial performance
2. Competitive position
3. Key risks and opportunities
4. Valuation assessment
5. Investment recommendation`,
    whenToUse: [
      'Single ticker deep dive',
      'Making investment decisions',
      'Portfolio analysis',
      'Regular research updates',
      'Pre-trade analysis',
      'When you need balanced detail and speed'
    ],
    limitations: [
      'Limited to 1-2 year historical trends',
      'No exhaustive competitive landscape',
      'Moderate depth on risk factors',
      'Standard peer comparison only'
    ]
  },
  {
    depth: 'deep',
    title: 'Deep Research',
    icon: <Layers className="w-5 h-5 text-purple-500" />,
    description: 'Exhaustive, comprehensive analysis covering multi-year trends, detailed competitive landscape, extensive risk analysis, and thorough valuation. Maximum depth for critical decisions.',
    useCase: 'Use for major investment decisions, due diligence, or when you need the most comprehensive analysis possible. Best for high-conviction trades or large positions.',
    executionTime: '~5-15 minutes',
    apiCalls: {
      llmCalls: '4-8 LLM API calls',
      estimatedTokens: '~5,000-10,000 tokens',
      tokenBreakdown: 'Input: ~1,500-2,500 tokens (exhaustive query) | Output: ~3,500-7,500 tokens (detailed response)',
      costEstimate: 'GPT-4: ~$0.15-0.30 | GPT-3.5: ~$0.005-0.01 | Claude 3.5: ~$0.05-0.10'
    },
    coverage: [
      'Financial performance (3+ year trends)',
      'Detailed competitive landscape and market position',
      'Management quality and capital allocation deep dive',
      'Growth drivers and headwinds (comprehensive)',
      'Valuation analysis vs peers and historical ranges',
      'Risk factors (macro, micro, regulatory, sector-specific)',
      'Bull and bear case scenarios',
      'Key metrics to monitor',
      'Industry trends and positioning',
      'ESG considerations (if relevant)',
      'Long-term strategic outlook'
    ],
    queryExample: `Provide an exhaustive analysis of TSLA covering:
1. Financial performance (3-year trends)
2. Competitive landscape and market position
3. Management quality and capital allocation
4. Growth drivers and headwinds
5. Valuation analysis vs peers and history
6. Risk factors (macro, micro, regulatory)
7. Bull and bear case scenarios
8. Key metrics to monitor`,
    whenToUse: [
      'Major investment decisions',
      'High-conviction trades',
      'Large position sizing',
      'Due diligence for acquisitions',
      'Long-term investment thesis',
      'When maximum insight is required',
      'Regulatory or compliance reviews',
      'Board-level analysis'
    ],
    limitations: [
      'Longest execution time',
      'Higher API costs',
      'May include redundant information',
      'Overkill for quick decisions'
    ]
  }
];

export function ResearchDepthHelp() {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedDepth, setSelectedDepth] = useState<string | null>(null);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center justify-center rounded-full p-2 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        title="Learn about research depth levels"
      >
        <Info className="w-4 h-4 text-blue-500" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-2xl font-bold">Research Depth Guide</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Understand each research depth level and when to use them
            </p>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="rounded-full p-2 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-6">
            {researchDepths.map((depthInfo) => (
              <div
                key={depthInfo.depth}
                className={`border rounded-lg p-5 transition-all ${
                  selectedDepth === depthInfo.depth
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-800'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-start gap-3 flex-1">
                    <div className="flex-shrink-0 mt-1">
                      {depthInfo.icon}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-xl font-semibold">{depthInfo.title}</h3>
                        <Badge variant="outline">{depthInfo.depth}</Badge>
                        <Badge variant="secondary" className="text-xs">
                          {depthInfo.executionTime}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">
                        {depthInfo.description}
                      </p>
                      <p className="text-xs bg-yellow-50 dark:bg-yellow-900/20 p-2 rounded border-l-2 border-yellow-500">
                        <strong>Use Case:</strong> {depthInfo.useCase}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedDepth(selectedDepth === depthInfo.depth ? null : depthInfo.depth)}
                    className="ml-4 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
                  >
                    <ChevronRight
                      className={`w-5 h-5 transition-transform ${
                        selectedDepth === depthInfo.depth ? 'rotate-90' : ''
                      }`}
                    />
                  </button>
                </div>

                {selectedDepth === depthInfo.depth && (
                  <div className="mt-4 space-y-4 border-t pt-4">
                    {/* API Calls & Token Usage */}
                    <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
                      <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                        <Brain className="w-4 h-4" />
                        API Calls & Token Usage
                      </h4>
                      <div className="grid grid-cols-1 gap-2 text-xs">
                        <div>
                          <span className="font-medium">LLM API Calls:</span>
                          <div className="text-muted-foreground mt-1">
                            {depthInfo.apiCalls.llmCalls}
                          </div>
                        </div>
                        <div>
                          <span className="font-medium">Estimated Tokens:</span>
                          <div className="text-muted-foreground mt-1">
                            {depthInfo.apiCalls.estimatedTokens}
                          </div>
                        </div>
                        <div>
                          <span className="font-medium">Token Breakdown:</span>
                          <div className="text-muted-foreground mt-1 text-[10px]">
                            {depthInfo.apiCalls.tokenBreakdown}
                          </div>
                        </div>
                        <div>
                          <span className="font-medium">Cost Estimate (per ticker):</span>
                          <div className="text-muted-foreground mt-1 text-[10px]">
                            {depthInfo.apiCalls.costEstimate}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Coverage */}
                    <div>
                      <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                        <Target className="w-4 h-4" />
                        What's Covered:
                      </h4>
                      <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                        {depthInfo.coverage.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>

                    {/* Query Example */}
                    <div>
                      <h4 className="font-semibold text-sm mb-2">Example Query:</h4>
                      <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded border text-xs font-mono whitespace-pre-wrap">
                        {depthInfo.queryExample}
                      </div>
                    </div>

                    {/* When to Use */}
                    <div>
                      <h4 className="font-semibold text-sm mb-2 text-green-600 dark:text-green-400">
                        ✓ When to Use:
                      </h4>
                      <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                        {depthInfo.whenToUse.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>

                    {/* Limitations */}
                    <div>
                      <h4 className="font-semibold text-sm mb-2 text-orange-600 dark:text-orange-400">
                        ⚠ Limitations:
                      </h4>
                      <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                        {depthInfo.limitations.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Comparison Table */}
          <div className="mt-8 border-t pt-6">
            <h3 className="text-lg font-semibold mb-4">Quick Comparison</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Depth</th>
                    <th className="text-left p-2">Speed</th>
                    <th className="text-left p-2">Detail Level</th>
                    <th className="text-left p-2">Historical Data</th>
                    <th className="text-left p-2">Best For</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b">
                    <td className="p-2 font-medium">Quick</td>
                    <td className="p-2">⚡ Fastest (30-60s)</td>
                    <td className="p-2">Surface</td>
                    <td className="p-2">Recent only</td>
                    <td className="p-2">Screening, quick checks</td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-2 font-medium">Standard</td>
                    <td className="p-2">⏱️ Medium (2-5 min)</td>
                    <td className="p-2">Comprehensive</td>
                    <td className="p-2">1-2 years</td>
                    <td className="p-2">Most decisions (default)</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-medium">Deep</td>
                    <td className="p-2">🐢 Slowest (5-15 min)</td>
                    <td className="p-2">Exhaustive</td>
                    <td className="p-2">3+ years</td>
                    <td className="p-2">Major decisions, due diligence</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* API & Token Usage Guide */}
          <div className="mt-6 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 p-5 rounded-lg border border-purple-200 dark:border-purple-800">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Globe className="w-5 h-5" />
              Understanding Token Usage & Costs
            </h3>
            <div className="space-y-4 text-sm">
              <div>
                <h4 className="font-semibold mb-2">How Tokens Work</h4>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs ml-2">
                  <li><strong>Input Tokens:</strong> Your query/prompt sent to the LLM (counts every word/token)</li>
                  <li><strong>Output Tokens:</strong> The LLM's response (longer responses = more tokens)</li>
                  <li><strong>Total Tokens:</strong> Input + Output = what you're charged for</li>
                  <li><strong>Token Count:</strong> ~1 token = 0.75 words (roughly 4 characters)</li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Why Depth Affects Tokens</h4>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs ml-2">
                  <li><strong>Quick:</strong> Short query → Short response (~1-2k tokens)</li>
                  <li><strong>Standard:</strong> Detailed query → Comprehensive response (~3-5k tokens)</li>
                  <li><strong>Deep:</strong> Exhaustive query → Very detailed response (~5-10k tokens)</li>
                  <li>Deeper research = longer prompts + longer responses = more tokens</li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Cost Examples (per ticker, per research call)</h4>
                <div className="bg-white dark:bg-gray-900 p-3 rounded border text-xs">
                  <div className="grid grid-cols-3 gap-2 mb-2">
                    <div className="font-semibold">Depth</div>
                    <div className="font-semibold">GPT-4</div>
                    <div className="font-semibold">GPT-3.5</div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 border-b pb-1 mb-1">
                    <div>Quick</div>
                    <div>$0.03-0.06</div>
                    <div>$0.001-0.002</div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 border-b pb-1 mb-1">
                    <div>Standard</div>
                    <div>$0.09-0.15</div>
                    <div>$0.003-0.005</div>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div>Deep</div>
                    <div>$0.15-0.30</div>
                    <div>$0.005-0.01</div>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-2">
                    *Prices are estimates based on typical token usage. Actual costs vary by provider and model.
                  </p>
                </div>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Tips to Manage Costs</h4>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs ml-2">
                  <li>Use "Quick" for initial screening of multiple tickers</li>
                  <li>Use "Standard" for most single-ticker analysis</li>
                  <li>Reserve "Deep" for final investment decisions only</li>
                  <li>Consider cheaper models (GPT-3.5) for non-critical research</li>
                  <li>Remember: Research depth multiplies when used in "Full Workflow" (2 research calls)</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Recommendations */}
          <div className="mt-6 bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
            <h3 className="font-semibold mb-2">💡 Recommendations</h3>
            <ul className="text-sm space-y-2 text-muted-foreground">
              <li>
                <strong>Start with Standard:</strong> For most use cases, "Standard" provides the best balance of detail, speed, and cost.
              </li>
              <li>
                <strong>Use Quick for screening:</strong> When analyzing multiple tickers, start with "Quick" to filter, then use "Standard" or "Deep" for finalists.
              </li>
              <li>
                <strong>Use Deep for conviction:</strong> Reserve "Deep" for high-stakes decisions, large positions, or when maximum insight is critical.
              </li>
              <li>
                <strong>Combine with workflow modes:</strong> "Quick" works well with "Signal Only" for speed. "Deep" pairs best with "Full Workflow" for comprehensive analysis.
              </li>
              <li>
                <strong>Cost awareness:</strong> "Deep" research costs 3-5x more than "Quick". Use strategically.
              </li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
