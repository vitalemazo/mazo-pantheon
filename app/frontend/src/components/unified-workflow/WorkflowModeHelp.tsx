import React, { useState } from 'react';
import { Info, X, ChevronRight, CheckCircle2, FileSearch, Brain, DollarSign, Database, Globe, Zap } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface WorkflowModeInfo {
  mode: string;
  title: string;
  description: string;
  useCase: string;
  apiCalls: {
    financialDatasets: number;
    llmCalls: number;
    estimatedTokens: string;
    costNote: string;
  };
  steps: Array<{
    id: string;
    name: string;
    icon: React.ReactNode;
    description: string;
    when: string;
    apiCalls?: string[];
  }>;
}

const workflowModes: WorkflowModeInfo[] = [
  {
    mode: 'signal',
    title: 'Signal Only',
    description: 'Generate trading signals using AI Hedge Fund agents without any Mazo research.',
    useCase: 'Use when you want quick trading signals based on AI agent analysis. Fastest mode with no external research.',
    apiCalls: {
      financialDatasets: 4,
      llmCalls: 18,
      estimatedTokens: '~15,000-30,000 tokens',
      costNote: 'Lower cost - no Mazo research. Only Financial Datasets API (cached) + 18 LLM agent calls.'
    },
    steps: [
      {
        id: 'data_aggregation',
        name: 'Data Aggregation',
        icon: <Database className="w-4 h-4" />,
        description: 'Fetches financial data (prices, metrics, news, insider trades) from Financial Datasets API for the ticker(s).',
        when: 'Always runs first to provide data for agents.',
        apiCalls: [
          'Financial Datasets API: get_financial_metrics (1 call per ticker)',
          'Financial Datasets API: get_prices (1 call per ticker)',
          'Financial Datasets API: get_company_news (1 call per ticker)',
          'Financial Datasets API: get_insider_trades (1 call per ticker)',
          'Note: Results are cached - repeated calls use cache, not API'
        ]
      },
      {
        id: 'ai_hedge_fund',
        name: 'AI Hedge Fund Analysis',
        icon: <Brain className="w-4 h-4" />,
        description: 'Runs 18 specialized AI agents (Buffett, Burry, Wood, Lynch, etc.) to analyze the ticker and generate signals.',
        when: 'Core step - all 18 agents analyze the data.',
        apiCalls: [
          'LLM API: 18 agent calls (1 per agent)',
          'Each agent: ~500-2,000 tokens (input + output)',
          'Total: ~9,000-36,000 tokens for all agents',
          'Agents may make additional Financial Datasets API calls (cached)'
        ]
      },
      {
        id: 'agents',
        name: '18 Agents Processing',
        icon: <Brain className="w-4 h-4" />,
        description: 'Each agent applies their unique investment philosophy to the ticker. Results are aggregated.',
        when: 'Runs in parallel with AI Hedge Fund Analysis.',
        apiCalls: [
          'Same as AI Hedge Fund Analysis - these steps run together',
          '18 LLM API calls total (one per agent)'
        ]
      },
      {
        id: 'portfolio_manager',
        name: 'Portfolio Manager Decision',
        icon: <CheckCircle2 className="w-4 h-4" />,
        description: 'Synthesizes all agent signals into a final trading decision (BULLISH/BEARISH/NEUTRAL) with confidence.',
        when: 'After all agents complete their analysis.'
      },
      {
        id: 'trade_execution',
        name: 'Trade Execution',
        icon: <DollarSign className="w-4 h-4" />,
        description: 'Executes trades based on the portfolio manager\'s decision (if enabled).',
        when: 'Only if "Execute Trades" or "Dry Run" is checked.'
      }
    ]
  },
  {
    mode: 'research',
    title: 'Research Only',
    description: 'Run Mazo financial research only, without AI Hedge Fund signal generation.',
    useCase: 'Use when you want comprehensive research reports from Mazo without trading signals. Great for due diligence.',
    apiCalls: {
      financialDatasets: 0,
      llmCalls: 1,
      estimatedTokens: 'Varies by depth: Quick ~1,000-2,000 | Standard ~3,000-5,000 | Deep ~5,000-10,000',
      costNote: 'Mazo makes LLM calls internally. Token usage depends on research depth. No Financial Datasets API calls (Mazo uses its own data sources).'
    },
    steps: [
      {
        id: 'mazo_initial',
        name: 'Mazo Research',
        icon: <FileSearch className="w-4 h-4" />,
        description: 'Mazo performs comprehensive financial research on the ticker(s) based on the selected depth (quick/standard/deep).',
        when: 'Only step - generates detailed research report.',
        apiCalls: [
          'LLM API: 1+ calls (Mazo makes internal LLM calls)',
          'Token usage varies by depth (see Research Depth help)',
          'Mazo may use Financial Datasets API internally (not counted here)',
          'No direct Financial Datasets API calls from workflow'
        ]
      }
    ]
  },
  {
    mode: 'pre-research',
    title: 'Pre-Research',
    description: 'Mazo research first, then AI Hedge Fund uses that research as context for signal generation.',
    useCase: 'Use when you want informed signals. Mazo research provides context to help agents make better decisions.',
    apiCalls: {
      financialDatasets: 4,
      llmCalls: 19,
      estimatedTokens: '~18,000-45,000 tokens (varies by research depth)',
      costNote: 'Financial Datasets API (cached) + 1 Mazo LLM call + 18 agent LLM calls. Higher token usage due to research context in agent prompts.'
    },
    steps: [
      {
        id: 'data_aggregation',
        name: 'Data Aggregation',
        icon: <Database className="w-4 h-4" />,
        description: 'Fetches financial data from APIs for the ticker(s).',
        when: 'Runs first to provide base data.'
      },
      {
        id: 'mazo_initial',
        name: 'Mazo Initial Research',
        icon: <FileSearch className="w-4 h-4" />,
        description: 'Mazo performs research on the ticker(s) BEFORE signal generation. This research is provided to AI agents as context.',
        when: 'Runs before AI Hedge Fund analysis.',
        apiCalls: [
          'LLM API: 1+ Mazo research call(s)',
          'Token usage: Quick ~1,000-2,000 | Standard ~3,000-5,000 | Deep ~5,000-10,000',
          'Research result is included in agent prompts (increases agent token usage)'
        ]
      },
      {
        id: 'ai_hedge_fund',
        name: 'AI Hedge Fund Analysis',
        icon: <Brain className="w-4 h-4" />,
        description: '18 AI agents analyze the ticker WITH the Mazo research context, leading to more informed signals.',
        when: 'After Mazo research completes.'
      },
      {
        id: 'agents',
        name: '18 Agents Processing',
        icon: <Brain className="w-4 h-4" />,
        description: 'Agents use both raw data and Mazo research insights to generate signals.',
        when: 'Runs with AI Hedge Fund Analysis.'
      },
      {
        id: 'portfolio_manager',
        name: 'Portfolio Manager Decision',
        icon: <CheckCircle2 className="w-4 h-4" />,
        description: 'Final trading decision based on agent signals that were informed by Mazo research.',
        when: 'After all agents complete.'
      },
      {
        id: 'trade_execution',
        name: 'Trade Execution',
        icon: <DollarSign className="w-4 h-4" />,
        description: 'Executes trades based on the informed decision (if enabled).',
        when: 'Only if "Execute Trades" or "Dry Run" is checked.'
      }
    ]
  },
  {
    mode: 'post-research',
    title: 'Post-Research',
    description: 'AI Hedge Fund generates signals first, then Mazo explains and expands on those signals.',
    useCase: 'Use when you want signals quickly, then get Mazo to explain WHY the signal makes sense with deeper analysis.',
    apiCalls: {
      financialDatasets: 4,
      llmCalls: 19,
      estimatedTokens: '~18,000-45,000 tokens (varies by research depth)',
      costNote: 'Financial Datasets API (cached) + 18 agent LLM calls + 1 Mazo LLM call. Mazo receives signal context, so research is more focused.'
    },
    steps: [
      {
        id: 'data_aggregation',
        name: 'Data Aggregation',
        icon: <Database className="w-4 h-4" />,
        description: 'Fetches financial data from APIs.',
        when: 'Runs first.'
      },
      {
        id: 'ai_hedge_fund',
        name: 'AI Hedge Fund Analysis',
        icon: <Brain className="w-4 h-4" />,
        description: '18 AI agents generate trading signals based on raw data analysis.',
        when: 'Runs BEFORE Mazo research.'
      },
      {
        id: 'agents',
        name: '18 Agents Processing',
        icon: <Brain className="w-4 h-4" />,
        description: 'Agents analyze and generate signals without Mazo context.',
        when: 'Runs with AI Hedge Fund Analysis.'
      },
      {
        id: 'portfolio_manager',
        name: 'Portfolio Manager Decision',
        icon: <CheckCircle2 className="w-4 h-4" />,
        description: 'Generates initial trading decision and reasoning.',
        when: 'After agents complete.'
      },
      {
        id: 'mazo_deep_dive',
        name: 'Mazo Deep Dive',
        icon: <FileSearch className="w-4 h-4" />,
        description: 'Mazo takes the signal and reasoning, then performs deep research to explain, validate, or challenge the signal.',
        when: 'Runs AFTER signal generation to explain it.',
        apiCalls: [
          'LLM API: 1+ Mazo research call(s) with signal context',
          'Token usage: Quick ~1,000-2,000 | Standard ~3,000-5,000 | Deep ~5,000-10,000',
          'Mazo receives agent reasoning as input (adds to prompt tokens)'
        ]
      },
      {
        id: 'trade_execution',
        name: 'Trade Execution',
        icon: <DollarSign className="w-4 h-4" />,
        description: 'Executes trades (if enabled).',
        when: 'Only if "Execute Trades" or "Dry Run" is checked.'
      }
    ]
  },
  {
    mode: 'full',
    title: 'Full Workflow',
    description: 'Complete workflow: Mazo pre-research → AI Hedge Fund signals → Mazo post-research explanation.',
    useCase: 'Use for maximum insight. Get research context, informed signals, and deep explanations. Most comprehensive but slowest.',
    apiCalls: {
      financialDatasets: 4,
      llmCalls: 20,
      estimatedTokens: '~25,000-60,000 tokens (varies by research depth)',
      costNote: 'Financial Datasets API (cached) + 2 Mazo LLM calls + 18 agent LLM calls. Highest token usage due to research context in both directions.'
    },
    steps: [
      {
        id: 'data_aggregation',
        name: 'Data Aggregation',
        icon: <Database className="w-4 h-4" />,
        description: 'Fetches comprehensive financial data.',
        when: 'Always runs first.'
      },
      {
        id: 'mazo_initial',
        name: 'Mazo Initial Research',
        icon: <FileSearch className="w-4 h-4" />,
        description: 'Mazo performs initial research to provide context for signal generation.',
        when: 'Step 1 of 3 - provides research context.'
      },
      {
        id: 'ai_hedge_fund',
        name: 'AI Hedge Fund Analysis',
        icon: <Brain className="w-4 h-4" />,
        description: '18 agents generate signals using both data and Mazo research context.',
        when: 'Step 2 of 3 - informed signal generation.'
      },
      {
        id: 'agents',
        name: '18 Agents Processing',
        icon: <Brain className="w-4 h-4" />,
        description: 'Agents analyze with research context.',
        when: 'Runs with AI Hedge Fund Analysis.'
      },
      {
        id: 'portfolio_manager',
        name: 'Portfolio Manager Decision',
        icon: <CheckCircle2 className="w-4 h-4" />,
        description: 'Synthesizes informed signals into final decision.',
        when: 'After agents complete.'
      },
      {
        id: 'mazo_deep_dive',
        name: 'Mazo Deep Dive',
        icon: <FileSearch className="w-4 h-4" />,
        description: 'Mazo performs deep research to explain, validate, and expand on the generated signal.',
        when: 'Step 3 of 3 - explains the signal.'
      },
      {
        id: 'trade_execution',
        name: 'Trade Execution',
        icon: <DollarSign className="w-4 h-4" />,
        description: 'Executes trades based on fully researched and explained signals (if enabled).',
        when: 'Only if "Execute Trades" or "Dry Run" is checked.'
      }
    ]
  }
];

export function WorkflowModeHelp() {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedMode, setSelectedMode] = useState<string | null>(null);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center justify-center rounded-full p-2 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        title="Learn about workflow modes"
      >
        <Info className="w-5 h-5 text-blue-500" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-2xl font-bold">Workflow Modes Guide</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Understand each workflow mode and when to use them
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
            {workflowModes.map((modeInfo) => (
              <div
                key={modeInfo.mode}
                className={`border rounded-lg p-5 transition-all ${
                  selectedMode === modeInfo.mode
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-800'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-xl font-semibold">{modeInfo.title}</h3>
                      <Badge variant="outline">{modeInfo.mode}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">
                      {modeInfo.description}
                    </p>
                    <p className="text-xs bg-yellow-50 dark:bg-yellow-900/20 p-2 rounded border-l-2 border-yellow-500">
                      <strong>Use Case:</strong> {modeInfo.useCase}
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedMode(selectedMode === modeInfo.mode ? null : modeInfo.mode)}
                    className="ml-4 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
                  >
                    <ChevronRight
                      className={`w-5 h-5 transition-transform ${
                        selectedMode === modeInfo.mode ? 'rotate-90' : ''
                      }`}
                    />
                  </button>
                </div>

                {selectedMode === modeInfo.mode && (
                  <div className="mt-4 space-y-3 border-t pt-4">
                    {/* API Calls Summary */}
                    <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800 mb-4">
                      <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                        <Globe className="w-4 h-4" />
                        API Calls & Token Usage
                      </h4>
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div>
                          <span className="font-medium">Financial Datasets API:</span>
                          <div className="text-muted-foreground mt-1">
                            {modeInfo.apiCalls.financialDatasets} calls per ticker
                            <br />
                            <span className="text-[10px]">(Results are cached)</span>
                          </div>
                        </div>
                        <div>
                          <span className="font-medium">LLM API Calls:</span>
                          <div className="text-muted-foreground mt-1">
                            {modeInfo.apiCalls.llmCalls} call(s)
                          </div>
                        </div>
                        <div className="col-span-2">
                          <span className="font-medium">Estimated Tokens:</span>
                          <div className="text-muted-foreground mt-1">
                            {modeInfo.apiCalls.estimatedTokens}
                          </div>
                        </div>
                        <div className="col-span-2">
                          <span className="font-medium">Cost Note:</span>
                          <div className="text-muted-foreground mt-1 text-[10px]">
                            {modeInfo.apiCalls.costNote}
                          </div>
                        </div>
                      </div>
                    </div>

                    <h4 className="font-semibold text-sm mb-3">Workflow Steps:</h4>
                    {modeInfo.steps.map((step, idx) => (
                      <div
                        key={step.id}
                        className="bg-white dark:bg-gray-900 p-4 rounded border"
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 mt-1">
                            <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400">
                              {idx + 1}
                            </div>
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              {step.icon}
                              <span className="font-semibold text-sm">{step.name}</span>
                            </div>
                            <p className="text-xs text-muted-foreground mb-2">
                              {step.description}
                            </p>
                            <p className="text-xs bg-gray-50 dark:bg-gray-800 p-2 rounded mb-2">
                              <strong>When:</strong> {step.when}
                            </p>
                            {step.apiCalls && step.apiCalls.length > 0 && (
                              <div className="text-xs bg-purple-50 dark:bg-purple-900/20 p-2 rounded border-l-2 border-purple-500 mt-2">
                                <strong className="flex items-center gap-1 mb-1">
                                  <Zap className="w-3 h-3" />
                                  API Calls:
                                </strong>
                                <ul className="list-disc list-inside space-y-1 text-[10px] text-muted-foreground">
                                  {step.apiCalls.map((call, i) => (
                                    <li key={i}>{call}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
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
                    <th className="text-left p-2">Mode</th>
                    <th className="text-left p-2">Mazo Pre-Research</th>
                    <th className="text-left p-2">AI Signals</th>
                    <th className="text-left p-2">Mazo Post-Research</th>
                    <th className="text-left p-2">LLM Calls</th>
                    <th className="text-left p-2">Est. Tokens</th>
                    <th className="text-left p-2">Speed</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b">
                    <td className="p-2 font-medium">Signal Only</td>
                    <td className="p-2">❌</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">❌</td>
                    <td className="p-2">18</td>
                    <td className="p-2">~15-30k</td>
                    <td className="p-2">⚡ Fastest</td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-2 font-medium">Research Only</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">❌</td>
                    <td className="p-2">❌</td>
                    <td className="p-2">1</td>
                    <td className="p-2">~1-10k*</td>
                    <td className="p-2">🐢 Slow</td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-2 font-medium">Pre-Research</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">❌</td>
                    <td className="p-2">19</td>
                    <td className="p-2">~18-45k</td>
                    <td className="p-2">⏱️ Medium</td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-2 font-medium">Post-Research</td>
                    <td className="p-2">❌</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">19</td>
                    <td className="p-2">~18-45k</td>
                    <td className="p-2">⏱️ Medium</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-medium">Full Workflow</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">✅</td>
                    <td className="p-2">20</td>
                    <td className="p-2">~25-60k</td>
                    <td className="p-2">🐢 Slowest</td>
                  </tr>
                </tbody>
              </table>
              <p className="text-xs text-muted-foreground mt-2">
                *Token usage for Research Only varies by depth: Quick ~1-2k | Standard ~3-5k | Deep ~5-10k
              </p>
            </div>
          </div>

          {/* API & Token Usage Guide */}
          <div className="mt-6 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 p-5 rounded-lg border border-blue-200 dark:border-blue-800">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Globe className="w-5 h-5" />
              Understanding API Calls & Token Usage
            </h3>
            <div className="space-y-4 text-sm">
              <div>
                <h4 className="font-semibold mb-2">1. Financial Datasets API</h4>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs ml-2">
                  <li><strong>What:</strong> External API for financial data (prices, metrics, news, insider trades)</li>
                  <li><strong>Calls per ticker:</strong> 4 calls (financial_metrics, prices, news, insider_trades)</li>
                  <li><strong>Caching:</strong> Results are cached - repeated requests use cache, not API</li>
                  <li><strong>Cost:</strong> Depends on your Financial Datasets API plan</li>
                  <li><strong>When:</strong> Only called if data aggregation is enabled (most modes)</li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold mb-2">2. LLM API (OpenAI, Anthropic, etc.)</h4>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs ml-2">
                  <li><strong>What:</strong> Your LLM provider API (OpenAI, Anthropic, via broker, etc.)</li>
                  <li><strong>Agent Calls:</strong> Each of 18 agents makes 1 LLM call (~500-2,000 tokens each)</li>
                  <li><strong>Mazo Calls:</strong> 1+ LLM calls for research (varies by depth: 1,000-10,000 tokens)</li>
                  <li><strong>Token Usage:</strong> Input tokens (prompts) + Output tokens (responses)</li>
                  <li><strong>Cost:</strong> Depends on your LLM provider pricing (e.g., GPT-4: ~$0.03/1k input, $0.06/1k output)</li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold mb-2">3. Cost Estimation Examples</h4>
                <div className="bg-white dark:bg-gray-900 p-3 rounded border text-xs">
                  <p className="mb-2"><strong>Signal Only (18 LLM calls, ~20k tokens):</strong></p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground ml-2">
                    <li>GPT-4: ~$0.60-1.20 per ticker</li>
                    <li>GPT-3.5: ~$0.02-0.04 per ticker</li>
                    <li>Claude 3.5 Sonnet: ~$0.15-0.30 per ticker</li>
                  </ul>
                  <p className="mb-2 mt-3"><strong>Full Workflow + Deep Research (~50k tokens):</strong></p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground ml-2">
                    <li>GPT-4: ~$1.50-3.00 per ticker</li>
                    <li>GPT-3.5: ~$0.05-0.10 per ticker</li>
                    <li>Claude 3.5 Sonnet: ~$0.40-0.80 per ticker</li>
                  </ul>
                  <p className="text-[10px] text-muted-foreground mt-2">
                    *Prices are estimates. Actual costs depend on model, prompt length, and provider pricing.
                  </p>
                </div>
              </div>
              <div>
                <h4 className="font-semibold mb-2">4. Tips to Reduce Costs</h4>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs ml-2">
                  <li>Use "Signal Only" mode for quick analysis (lowest token usage)</li>
                  <li>Use "Quick" research depth when speed matters more than detail</li>
                  <li>Financial Datasets API calls are cached - repeated analysis of same ticker uses cache</li>
                  <li>Consider using GPT-3.5 or cheaper models for non-critical analysis</li>
                  <li>Use "Research Only" mode if you only need Mazo research (no agent calls)</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
