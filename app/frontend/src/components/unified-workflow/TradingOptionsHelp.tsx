import React, { useState } from 'react';
import { Info, X, AlertTriangle, CheckCircle2, Eye, DollarSign, ChevronRight } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface TradingOptionInfo {
  option: string;
  title: string;
  icon: React.ReactNode;
  description: string;
  whatItDoes: string[];
  whenToUse: string[];
  workflowModes: {
    bestWith: string[];
    worksWith: string[];
    notRecommended: string[];
  };
  safety: string[];
  limitations: string[];
}

const tradingOptions: TradingOptionInfo[] = [
  {
    option: 'dry-run',
    title: 'Dry Run',
    icon: <Eye className="w-5 h-5 text-blue-500" />,
    description: 'Simulates trades without actually executing them. Shows what would be traded, but no orders are placed.',
    whatItDoes: [
      'Shows the action (BUY/SELL/HOLD) and quantity that would be traded',
      'Displays the reasoning behind the trade decision',
      'No actual orders are placed with your broker',
      'No money is at risk',
      'Perfect for testing and validation'
    ],
    whenToUse: [
      'Testing the workflow for the first time',
      'Validating signals before committing capital',
      'Learning how the system makes decisions',
      'Backtesting strategies without risk',
      'Reviewing trade logic before going live',
      'When you want to see what WOULD happen without risk'
    ],
    workflowModes: {
      bestWith: [
        'Signal Only - Quick validation of agent signals',
        'Pre-Research - Test informed signals before trading',
        'Post-Research - Validate signal explanations',
        'Full Workflow - Complete testing of entire system'
      ],
      worksWith: [
        'Research Only - Not applicable (no signals to trade)'
      ],
      notRecommended: []
    },
    safety: [
      '100% safe - no real trades executed',
      'No risk to your capital',
      'No impact on your portfolio',
      'Can run unlimited times for testing'
    ],
    limitations: [
      'Does not show actual fill prices (uses estimates)',
      'Does not account for slippage or market impact',
      'Does not update your portfolio',
      'Cannot verify broker connection or account status'
    ]
  },
  {
    option: 'execute-trades',
    title: 'Execute Trades',
    icon: <DollarSign className="w-5 h-5 text-green-500" />,
    description: 'Actually places orders with your broker (Alpaca). Real trades, real money, real risk.',
    whatItDoes: [
      'Places actual BUY/SELL orders with your broker',
      'Uses real money from your trading account',
      'Updates your portfolio with new positions',
      'Executes trades based on portfolio manager decisions',
      'Connects to Alpaca (paper or live trading)'
    ],
    whenToUse: [
      'You have validated the system with Dry Run',
      'You trust the signals and want to trade them',
      'You have sufficient capital and risk tolerance',
      'You understand the risks of automated trading',
      'You want to build positions based on AI signals',
      'You are ready to commit real capital'
    ],
    workflowModes: {
      bestWith: [
        'Signal Only - Quick execution of agent signals',
        'Pre-Research - Trade informed signals',
        'Post-Research - Trade validated signals with explanations',
        'Full Workflow - Execute fully researched and validated trades'
      ],
      worksWith: [
        'Research Only - Not applicable (no signals to trade)'
      ],
      notRecommended: []
    },
    safety: [
      '⚠️ Uses real money - trades are executed',
      '⚠️ Risk of loss - markets can move against you',
      '⚠️ Paper trading available - test with virtual money first',
      '⚠️ Review signals carefully before enabling',
      '⚠️ Start with small position sizes',
      '⚠️ Monitor trades actively'
    ],
    limitations: [
      'Cannot be undone once executed (market orders)',
      'Subject to market conditions and slippage',
      'Requires valid broker connection and sufficient capital',
      'May hit rate limits or account restrictions'
    ]
  }
];

export function TradingOptionsHelp() {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center justify-center rounded-full p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        title="Learn about Dry Run vs Execute Trades"
      >
        <Info className="w-4 h-4 text-blue-500" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <Card className="w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-2xl font-bold">Trading Options Guide</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Understand when and why to use Dry Run vs Execute Trades
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
            {tradingOptions.map((optionInfo) => (
              <div
                key={optionInfo.option}
                className={`border rounded-lg p-5 transition-all ${
                  selectedOption === optionInfo.option
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-800'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-start gap-3 flex-1">
                    <div className="flex-shrink-0 mt-1">
                      {optionInfo.icon}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-xl font-semibold">{optionInfo.title}</h3>
                        <Badge variant={optionInfo.option === 'dry-run' ? 'secondary' : 'default'}>
                          {optionInfo.option === 'dry-run' ? 'Safe' : 'Live Trading'}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">
                        {optionInfo.description}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedOption(selectedOption === optionInfo.option ? null : optionInfo.option)}
                    className="ml-4 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
                  >
                    <ChevronRight
                      className={`w-5 h-5 transition-transform ${
                        selectedOption === optionInfo.option ? 'rotate-90' : ''
                      }`}
                    />
                  </button>
                </div>

                {selectedOption === optionInfo.option && (
                  <div className="mt-4 space-y-4 border-t pt-4">
                    {/* What It Does */}
                    <div>
                      <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4" />
                        What It Does:
                      </h4>
                      <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                        {optionInfo.whatItDoes.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>

                    {/* When to Use */}
                    <div>
                      <h4 className="font-semibold text-sm mb-2 text-green-600 dark:text-green-400">
                        ✓ When to Use:
                      </h4>
                      <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                        {optionInfo.whenToUse.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>

                    {/* Workflow Modes */}
                    <div>
                      <h4 className="font-semibold text-sm mb-2">Workflow Mode Compatibility:</h4>
                      <div className="space-y-2 text-sm">
                        {optionInfo.workflowModes.bestWith.length > 0 && (
                          <div>
                            <span className="font-medium text-green-600 dark:text-green-400">✓ Best With:</span>
                            <ul className="list-disc list-inside space-y-1 text-muted-foreground ml-2 mt-1">
                              {optionInfo.workflowModes.bestWith.map((mode, idx) => (
                                <li key={idx}>{mode}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {optionInfo.workflowModes.worksWith.length > 0 && (
                          <div>
                            <span className="font-medium text-blue-600 dark:text-blue-400">→ Works With:</span>
                            <ul className="list-disc list-inside space-y-1 text-muted-foreground ml-2 mt-1">
                              {optionInfo.workflowModes.worksWith.map((mode, idx) => (
                                <li key={idx}>{mode}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Safety */}
                    <div>
                      <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                        {optionInfo.option === 'dry-run' ? (
                          <CheckCircle2 className="w-4 h-4 text-green-500" />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-orange-500" />
                        )}
                        Safety & Risk:
                      </h4>
                      <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                        {optionInfo.safety.map((item, idx) => (
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
                        {optionInfo.limitations.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Comparison & Recommendations */}
          <div className="mt-8 border-t pt-6 space-y-6">
            {/* Side-by-Side Comparison */}
            <div>
              <h3 className="text-lg font-semibold mb-4">Quick Comparison</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="border rounded-lg p-4 bg-blue-50 dark:bg-blue-900/20">
                  <h4 className="font-semibold mb-2 flex items-center gap-2">
                    <Eye className="w-4 h-4" />
                    Dry Run
                  </h4>
                  <ul className="text-xs space-y-1 text-muted-foreground">
                    <li>✓ No real trades</li>
                    <li>✓ No risk</li>
                    <li>✓ Unlimited testing</li>
                    <li>✓ Shows what would trade</li>
                    <li>✗ No actual execution</li>
                  </ul>
                </div>
                <div className="border rounded-lg p-4 bg-green-50 dark:bg-green-900/20">
                  <h4 className="font-semibold mb-2 flex items-center gap-2">
                    <DollarSign className="w-4 h-4" />
                    Execute Trades
                  </h4>
                  <ul className="text-xs space-y-1 text-muted-foreground">
                    <li>✓ Real trades</li>
                    <li>✓ Updates portfolio</li>
                    <li>✓ Actual execution</li>
                    <li>⚠ Real money at risk</li>
                    <li>⚠ Cannot undo easily</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Recommended Workflow */}
            <div className="bg-gradient-to-r from-yellow-50 to-orange-50 dark:from-yellow-900/20 dark:to-orange-900/20 p-5 rounded-lg border border-yellow-200 dark:border-yellow-800">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-orange-500" />
                Recommended Workflow
              </h3>
              <div className="space-y-3 text-sm">
                <div className="bg-white dark:bg-gray-900 p-3 rounded border">
                  <h4 className="font-semibold mb-2">Step 1: Start with Dry Run</h4>
                  <p className="text-xs text-muted-foreground mb-2">
                    Always test first! Run multiple workflows with Dry Run enabled to:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground ml-2">
                    <li>Understand how the system makes decisions</li>
                    <li>Validate signal quality and reasoning</li>
                    <li>See what trades would be executed</li>
                    <li>Test different workflow modes and research depths</li>
                    <li>Build confidence in the system</li>
                  </ul>
                </div>
                <div className="bg-white dark:bg-gray-900 p-3 rounded border">
                  <h4 className="font-semibold mb-2">Step 2: Review & Validate</h4>
                  <p className="text-xs text-muted-foreground mb-2">
                    Before enabling Execute Trades, ensure:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground ml-2">
                    <li>Signals make sense and align with your strategy</li>
                    <li>You understand the reasoning behind each trade</li>
                    <li>You have sufficient capital and risk tolerance</li>
                    <li>You've tested with multiple tickers and scenarios</li>
                    <li>You're comfortable with automated trading</li>
                  </ul>
                </div>
                <div className="bg-white dark:bg-gray-900 p-3 rounded border">
                  <h4 className="font-semibold mb-2">Step 3: Start Small (if executing)</h4>
                  <p className="text-xs text-muted-foreground mb-2">
                    When ready to execute:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground ml-2">
                    <li>Start with paper trading if available</li>
                    <li>Use small position sizes initially</li>
                    <li>Monitor trades actively</li>
                    <li>Review results and adjust as needed</li>
                    <li>Consider using "Signal Only" or "Post-Research" for faster validation</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Workflow Mode Recommendations */}
            <div className="bg-blue-50 dark:bg-blue-900/20 p-5 rounded-lg border border-blue-200 dark:border-blue-800">
              <h3 className="font-semibold mb-3">💡 Workflow Mode Recommendations</h3>
              <div className="space-y-3 text-sm">
                <div>
                  <h4 className="font-semibold mb-1">For Dry Run Testing:</h4>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground ml-2">
                    <li><strong>Signal Only:</strong> Quick validation of agent signals</li>
                    <li><strong>Full Workflow:</strong> Complete end-to-end testing</li>
                    <li><strong>Post-Research:</strong> See how Mazo explains signals</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-semibold mb-1">For Live Trading:</h4>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground ml-2">
                    <li><strong>Pre-Research:</strong> Trade informed signals (research → signal → trade)</li>
                    <li><strong>Post-Research:</strong> Quick signals, then validate with research</li>
                    <li><strong>Full Workflow:</strong> Maximum confidence trades (research → signal → validation → trade)</li>
                    <li><strong>Signal Only:</strong> Fast execution, but less context</li>
                  </ul>
                </div>
                <div className="bg-white dark:bg-gray-900 p-3 rounded border mt-3">
                  <h4 className="font-semibold mb-1 text-red-600 dark:text-red-400">⚠️ Never Execute Without Testing First!</h4>
                  <p className="text-xs text-muted-foreground">
                    Always run Dry Run multiple times with different scenarios before enabling Execute Trades. 
                    Understand the system's behavior, validate signal quality, and ensure you're comfortable with the decisions it makes.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
