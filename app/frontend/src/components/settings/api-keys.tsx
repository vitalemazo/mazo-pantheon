import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { apiKeysService } from '@/services/api-keys-api';
import { Eye, EyeOff, Key, Trash2, Globe, Zap, Info } from 'lucide-react';
import { useEffect, useState } from 'react';

interface ApiKey {
  key: string;
  label: string;
  description: string;
  url: string;
  placeholder: string;
}

const FINANCIAL_API_KEYS: ApiKey[] = [
  {
    key: 'FINANCIAL_DATASETS_API_KEY',
    label: 'Financial Datasets API',
    description: 'For getting financial data to power the hedge fund',
    url: 'https://financialdatasets.ai/',
    placeholder: 'your-financial-datasets-api-key'
  }
];

const API_ENDPOINTS: ApiKey[] = [
  {
    key: 'OPENAI_API_BASE',
    label: 'OpenAI API Base URL',
    description: 'Custom base URL for OpenAI-compatible APIs (leave empty for default OpenAI)',
    url: 'https://platform.openai.com/',
    placeholder: 'https://api.openai.com/v1'
  }
];

const TRADING_API_KEYS: ApiKey[] = [
  {
    key: 'ALPACA_API_KEY',
    label: 'Alpaca API Key',
    description: 'For paper or live trading via Alpaca',
    url: 'https://app.alpaca.markets/',
    placeholder: 'your-alpaca-api-key'
  },
  {
    key: 'ALPACA_SECRET_KEY',
    label: 'Alpaca Secret Key',
    description: 'Secret key for Alpaca trading API',
    url: 'https://app.alpaca.markets/',
    placeholder: 'your-alpaca-secret-key'
  },
  {
    key: 'ALPACA_BASE_URL',
    label: 'Alpaca Base URL',
    description: 'API endpoint (paper-api.alpaca.markets for testing, api.alpaca.markets for live)',
    url: 'https://alpaca.markets/docs/api-references/',
    placeholder: 'https://paper-api.alpaca.markets/v2'
  },
  {
    key: 'ALPACA_TRADING_MODE',
    label: 'Trading Mode',
    description: 'Set to "paper" for testing or "live" for real trading',
    url: 'https://alpaca.markets/docs/',
    placeholder: 'paper'
  }
];

const MAZO_CONFIG: ApiKey[] = [
  {
    key: 'MAZO_PATH',
    label: 'Mazo Path',
    description: 'Absolute path to the Mazo research agent directory',
    url: 'https://github.com/virattt/mazo',
    placeholder: '/path/to/mazo-pantheon/mazo'
  },
  {
    key: 'MAZO_TIMEOUT',
    label: 'Mazo Timeout',
    description: 'Timeout for Mazo queries in seconds',
    url: 'https://github.com/virattt/mazo',
    placeholder: '300'
  },
  {
    key: 'DEFAULT_WORKFLOW_MODE',
    label: 'Default Workflow Mode',
    description: 'Default mode: signal, research, pre-research, post-research, full',
    url: '#',
    placeholder: 'full'
  },
  {
    key: 'DEFAULT_RESEARCH_DEPTH',
    label: 'Default Research Depth',
    description: 'Default depth: quick, standard, deep',
    url: '#',
    placeholder: 'standard'
  }
];

const SEARCH_API_KEYS: ApiKey[] = [
  {
    key: 'TAVILY_API_KEY',
    label: 'Tavily API',
    description: 'For real-time web search in Mazo research',
    url: 'https://tavily.com/',
    placeholder: 'your-tavily-api-key'
  }
];

// Workflow optimization toggles
interface WorkflowToggle {
  key: string;
  label: string;
  description: string;
  detailedExplanation: string;
}

const WORKFLOW_TOGGLES: WorkflowToggle[] = [
  {
    key: 'AGGREGATE_DATA',
    label: 'Pre-fetch Financial Data',
    description: 'Aggregate all financial data before agents run',
    detailedExplanation: 'When enabled, the system will fetch ALL financial data (prices, metrics, news, insider trades) for your tickers in a single batch BEFORE the AI agents start analyzing. This reduces duplicate API calls since each agent would otherwise fetch data independently. Recommended for multi-ticker analysis. Adds a brief initial delay but significantly reduces total API calls.'
  }
];

const LLM_API_KEYS: ApiKey[] = [
  {
    key: 'ANTHROPIC_API_KEY',
    label: 'Anthropic API',
    description: 'For Claude models (claude-4-sonnet, claude-4.1-opus, etc.)',
    url: 'https://anthropic.com/',
    placeholder: 'your-anthropic-api-key'
  },
  {
    key: 'DEEPSEEK_API_KEY',
    label: 'DeepSeek API',
    description: 'For DeepSeek models (deepseek-chat, deepseek-reasoner, etc.)',
    url: 'https://deepseek.com/',
    placeholder: 'your-deepseek-api-key'
  },
  {
    key: 'GROQ_API_KEY',
    label: 'Groq API',
    description: 'For Groq-hosted models (deepseek, llama3, etc.)',
    url: 'https://groq.com/',
    placeholder: 'your-groq-api-key'
  },
  {
    key: 'GOOGLE_API_KEY',
    label: 'Google API',
    description: 'For Gemini models (gemini-2.5-flash, gemini-2.5-pro)',
    url: 'https://ai.dev/',
    placeholder: 'your-google-api-key'
  },
  {
    key: 'OPENAI_API_KEY',
    label: 'OpenAI API',
    description: 'For OpenAI models (gpt-4o, gpt-4o-mini, etc.)',
    url: 'https://platform.openai.com/',
    placeholder: 'your-openai-api-key'
  },
  {
    key: 'OPENROUTER_API_KEY',
    label: 'OpenRouter API',
    description: 'For OpenRouter models (gpt-4o, gpt-4o-mini, etc.)',
    url: 'https://openrouter.ai/',
    placeholder: 'your-openrouter-api-key'
  },
  {
    key: 'GIGACHAT_API_KEY',
    label: 'GigaChat API',
    description: 'For GigaChat models (GigaChat-2-Max, etc.)',
    url: 'https://github.com/ai-forever/gigachat',
    placeholder: 'your-gigachat-api-key'
  }
];

export function ApiKeysSettings() {
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load API keys from backend on component mount
  useEffect(() => {
    loadApiKeys();
  }, []);

  const loadApiKeys = async () => {
    try {
      setLoading(true);
      setError(null);
      const apiKeysSummary = await apiKeysService.getAllApiKeys();
      
      // Load actual key values for existing keys
      const keysData: Record<string, string> = {};
      for (const summary of apiKeysSummary) {
        try {
          const fullKey = await apiKeysService.getApiKey(summary.provider);
          keysData[summary.provider] = fullKey.key_value;
        } catch (err) {
          console.warn(`Failed to load key for ${summary.provider}:`, err);
        }
      }
      
      setApiKeys(keysData);
    } catch (err) {
      console.error('Failed to load API keys:', err);
      setError('Failed to load API keys. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyChange = async (key: string, value: string) => {
    // Update local state immediately for responsive UI
    setApiKeys(prev => ({
      ...prev,
      [key]: value
    }));

    // Auto-save with debouncing
    try {
      if (value.trim()) {
        await apiKeysService.createOrUpdateApiKey({
          provider: key,
          key_value: value.trim(),
          is_active: true
        });
      } else {
        // If value is empty, delete the key
        try {
          await apiKeysService.deleteApiKey(key);
        } catch (err) {
          // Key might not exist, which is fine
          console.log(`Key ${key} not found for deletion, which is expected`);
        }
      }
    } catch (err) {
      console.error(`Failed to save API key ${key}:`, err);
      setError(`Failed to save ${key}. Please try again.`);
    }
  };

  const toggleKeyVisibility = (key: string) => {
    setVisibleKeys(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const clearKey = async (key: string) => {
    try {
      await apiKeysService.deleteApiKey(key);
      setApiKeys(prev => {
        const newKeys = { ...prev };
        delete newKeys[key];
        return newKeys;
      });
    } catch (err) {
      console.error(`Failed to delete API key ${key}:`, err);
      setError(`Failed to delete ${key}. Please try again.`);
    }
  };

  const renderApiKeySection = (title: string, description: string, keys: ApiKey[], icon: React.ReactNode) => (
    <Card className="bg-panel border-gray-700 dark:border-gray-700">
      <CardHeader>
        <CardTitle className="text-lg font-medium text-primary flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {keys.map((apiKey) => (
          <div key={apiKey.key} className="space-y-2">
                         <button
               className="text-sm font-medium text-primary hover:text-blue-500 cursor-pointer transition-colors text-left"
               onClick={() => window.open(apiKey.url, '_blank')}
             >
               {apiKey.label}
             </button>
            <div className="relative">
              <Input
                type={visibleKeys[apiKey.key] ? 'text' : 'password'}
                placeholder={apiKey.placeholder}
                value={apiKeys[apiKey.key] || ''}
                onChange={(e) => handleKeyChange(apiKey.key, e.target.value)}
                className="pr-20"
              />
              <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-1">
                {apiKeys[apiKey.key] && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 hover:bg-red-500/10 hover:text-red-500"
                    onClick={() => clearKey(apiKey.key)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => toggleKeyVisibility(apiKey.key)}
                >
                  {visibleKeys[apiKey.key] ? (
                    <EyeOff className="h-3 w-3" />
                  ) : (
                    <Eye className="h-3 w-3" />
                  )}
                </Button>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-primary mb-2">API Keys</h2>
          <p className="text-sm text-muted-foreground">
            Loading API keys...
          </p>
        </div>
        <Card className="bg-panel border-gray-700 dark:border-gray-700">
          <CardContent className="p-6">
            <div className="text-sm text-muted-foreground">
              Please wait while we load your API keys...
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-primary mb-2">API Keys</h2>
        <p className="text-sm text-muted-foreground">
          Configure API endpoints and authentication credentials for financial data and language models.
          Changes are automatically saved.
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <Card className="bg-red-500/5 border-red-500/20">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Key className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
              <div className="space-y-1">
                <h4 className="text-sm font-medium text-red-500">Error</h4>
                <p className="text-xs text-muted-foreground">{error}</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setError(null);
                    loadApiKeys();
                  }}
                  className="text-xs mt-2 p-0 h-auto text-red-500 hover:text-red-400"
                >
                  Try again
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Financial Data API Keys */}
      {renderApiKeySection(
        'Financial Data',
        'API keys for accessing financial market data and datasets.',
        FINANCIAL_API_KEYS,
        <Key className="h-4 w-4" />
      )}

      {/* LLM API Keys */}
      {renderApiKeySection(
        'Language Models',
        'API keys for accessing various large language model providers.',
        LLM_API_KEYS,
        <Key className="h-4 w-4" />
      )}

      {/* API Endpoints */}
      {renderApiKeySection(
        'Custom API Endpoints',
        'Configure custom API endpoints for OpenAI-compatible providers.',
        API_ENDPOINTS,
        <Globe className="h-4 w-4" />
      )}

      {/* Search API Keys */}
      {renderApiKeySection(
        'Web Search',
        'API keys for real-time web search capabilities.',
        SEARCH_API_KEYS,
        <Globe className="h-4 w-4" />
      )}

      {/* Trading API Keys */}
      {renderApiKeySection(
        'Trading Integration',
        'Configure Alpaca for paper or live trading.',
        TRADING_API_KEYS,
        <Key className="h-4 w-4" />
      )}

      {/* Mazo Configuration */}
      {renderApiKeySection(
        'Mazo Research Agent',
        'Configuration for the Mazo research agent integration.',
        MAZO_CONFIG,
        <Key className="h-4 w-4" />
      )}

      {/* Workflow Optimization */}
      <Card className="bg-panel border-gray-700 dark:border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg font-medium text-primary flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Workflow Optimization
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Performance settings that affect how the trading workflow executes.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {WORKFLOW_TOGGLES.map((toggle) => {
            const isEnabled = apiKeys[toggle.key]?.toLowerCase() === 'true';
            return (
              <div key={toggle.key} className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <label className="text-sm font-medium text-primary">
                      {toggle.label}
                    </label>
                    <p className="text-xs text-muted-foreground">
                      {toggle.description}
                    </p>
                  </div>
                  <Switch
                    checked={isEnabled}
                    onCheckedChange={(checked) => {
                      handleKeyChange(toggle.key, checked ? 'true' : 'false');
                    }}
                  />
                </div>
                {/* Detailed explanation */}
                <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                    <p className="text-xs text-muted-foreground">
                      {toggle.detailedExplanation}
                    </p>
                  </div>
                </div>
                {isEnabled && (
                  <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-2">
                    <p className="text-xs text-green-500 font-medium">
                      ✓ Data Aggregation is enabled - you'll see the "Data Aggregation" step in your workflow
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Security Note */}
      <Card className="bg-amber-500/5 border-amber-500/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Key className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <h4 className="text-sm font-medium text-amber-500">Security Note</h4>
              <p className="text-xs text-muted-foreground">
                API keys are stored securely on your local system and changes are automatically saved. 
                Keep your API keys secure and don't share them with others.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 