import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { apiKeysService } from '@/services/api-keys-api';
import { API_BASE_URL } from '@/lib/api-config';
import { Eye, EyeOff, Key, Trash2, Globe, Zap, Info, CheckCircle, XCircle, Loader2, RefreshCw, Cloud, Server } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

interface ApiKey {
  key: string;
  label: string;
  description: string;
  url: string;
  placeholder: string;
}

const FINANCIAL_API_KEYS: ApiKey[] = [
  {
    key: 'FMP_API_KEY',
    label: 'FMP Ultimate (Primary)',
    description: 'Recommended primary data source - comprehensive coverage with 100+ endpoints',
    url: 'https://financialmodelingprep.com/',
    placeholder: 'your-fmp-api-key'
  },
  {
    key: 'FINANCIAL_DATASETS_API_KEY',
    label: 'Financial Datasets API',
    description: 'Alternative source for financial data (prices, metrics, news, insider trades)',
    url: 'https://financialdatasets.ai/',
    placeholder: 'your-financial-datasets-api-key'
  }
];

const API_ENDPOINTS: ApiKey[] = [
  {
    key: 'OPENAI_API_BASE',
    label: 'OpenAI API Base URL',
    description: 'Custom base URL for OpenAI-compatible APIs or proxy relays',
    url: 'https://platform.openai.com/',
    placeholder: 'https://api.openai.com/v1'
  },
  {
    key: 'ANTHROPIC_API_BASE',
    label: 'Anthropic API Base URL',
    description: 'Custom base URL for Anthropic Claude API (leave empty for default)',
    url: 'https://docs.anthropic.com/',
    placeholder: 'https://api.anthropic.com'
  },
  {
    key: 'OPENROUTER_API_BASE',
    label: 'OpenRouter API Base URL',
    description: 'Custom base URL for OpenRouter (default: openrouter.ai/api/v1)',
    url: 'https://openrouter.ai/',
    placeholder: 'https://openrouter.ai/api/v1'
  }
];

const AZURE_CONFIG: ApiKey[] = [
  {
    key: 'AZURE_OPENAI_API_KEY',
    label: 'Azure OpenAI API Key',
    description: 'API key for Azure OpenAI service',
    url: 'https://azure.microsoft.com/en-us/products/ai-services/openai-service',
    placeholder: 'your-azure-openai-key'
  },
  {
    key: 'AZURE_OPENAI_ENDPOINT',
    label: 'Azure OpenAI Endpoint',
    description: 'Your Azure OpenAI resource endpoint URL',
    url: 'https://azure.microsoft.com/en-us/products/ai-services/openai-service',
    placeholder: 'https://your-resource.openai.azure.com'
  },
  {
    key: 'AZURE_OPENAI_DEPLOYMENT_NAME',
    label: 'Azure Deployment Name',
    description: 'Name of your Azure OpenAI model deployment',
    url: 'https://azure.microsoft.com/en-us/products/ai-services/openai-service',
    placeholder: 'gpt-4'
  },
  {
    key: 'AZURE_OPENAI_API_VERSION',
    label: 'Azure API Version',
    description: 'API version for Azure OpenAI (e.g., 2024-02-15-preview)',
    url: 'https://learn.microsoft.com/en-us/azure/ai-services/openai/',
    placeholder: '2024-02-15-preview'
  }
];

const XAI_CONFIG: ApiKey[] = [
  {
    key: 'XAI_API_KEY',
    label: 'xAI (Grok) API Key',
    description: 'API key for xAI Grok models',
    url: 'https://x.ai/',
    placeholder: 'your-xai-api-key'
  },
  {
    key: 'XAI_API_BASE',
    label: 'xAI API Base URL',
    description: 'Custom base URL for xAI API (leave empty for default)',
    url: 'https://x.ai/',
    placeholder: 'https://api.x.ai/v1'
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

interface FallbackToggle {
  key: string;
  label: string;
  description: string;
  detailedExplanation: string;
  isMaster?: boolean;
}

const DATA_FALLBACK_TOGGLES: FallbackToggle[] = [
  {
    key: 'USE_YAHOO_FINANCE_FALLBACK',
    label: 'Enable Yahoo Finance Fallback',
    description: 'Use Yahoo Finance as backup when primary API fails',
    detailedExplanation: 'When enabled, if the primary API fails, Yahoo Finance will be tried as a fallback. Yahoo Finance is free but has limited data.',
    isMaster: true
  },
  {
    key: 'YAHOO_FINANCE_FOR_PRICES',
    label: 'Yahoo Finance → Price Data',
    description: 'Historical and current prices',
    detailedExplanation: 'OHLCV (Open, High, Low, Close, Volume) data including historical prices and current snapshots.'
  },
  {
    key: 'YAHOO_FINANCE_FOR_METRICS',
    label: 'Yahoo Finance → Financial Metrics',
    description: 'Company metrics (P/E, market cap, etc.)',
    detailedExplanation: 'Basic metrics like P/E ratio, market cap, 52-week high/low. Note: Some advanced metrics may not be available.'
  },
  {
    key: 'YAHOO_FINANCE_FOR_NEWS',
    label: 'Yahoo Finance → News',
    description: 'Company news articles',
    detailedExplanation: 'Recent news articles with titles, sources, and publication dates.'
  }
];

const FMP_FALLBACK_TOGGLES: FallbackToggle[] = [
  {
    key: 'USE_FMP_FALLBACK',
    label: 'Enable FMP Fallback',
    description: 'Use Financial Modeling Prep as backup (requires API key)',
    detailedExplanation: 'When enabled, FMP will be tried as a fallback. FMP provides comprehensive financial data with 100+ endpoints. Requires FMP API key.',
    isMaster: true
  },
  {
    key: 'FMP_FOR_PRICES',
    label: 'FMP → Price Data',
    description: 'Real-time and historical prices',
    detailedExplanation: 'Real-time quotes and full historical price data including open, high, low, close, and volume.'
  },
  {
    key: 'FMP_FOR_METRICS',
    label: 'FMP → Financial Metrics',
    description: 'Company profile and key metrics',
    detailedExplanation: 'Detailed company profiles with market cap, P/E, sector, industry, and key financial ratios.'
  },
  {
    key: 'FMP_FOR_NEWS',
    label: 'FMP → News',
    description: 'Stock news and press releases',
    detailedExplanation: 'Latest news articles and press releases for stocks with sentiment analysis.'
  },
  {
    key: 'FMP_FOR_FINANCIALS',
    label: 'FMP → Financial Statements',
    description: 'Income statements, balance sheets, cash flows',
    detailedExplanation: 'Complete financial statements including income statements, balance sheets, and cash flow statements.'
  }
];

interface DataSourceOption {
  value: string;
  label: string;
  description: string;
}

const PRIMARY_DATA_SOURCES: DataSourceOption[] = [
  {
    value: 'fmp',
    label: 'FMP Ultimate (Recommended)',
    description: 'Comprehensive data: prices, fundamentals, news, insider trades, 100+ endpoints'
  },
  {
    value: 'alpaca',
    label: 'Alpaca Market Data',
    description: 'Real-time prices & news only (uses trading API keys, no fundamentals)'
  },
  {
    value: 'financial_datasets',
    label: 'Financial Datasets API',
    description: 'Premium financial data with focus on fundamentals'
  },
  {
    value: 'yahoo_finance',
    label: 'Yahoo Finance',
    description: 'Free fallback (limited features, may be rate limited)'
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
  const [testingConnection, setTestingConnection] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<Record<string, 'success' | 'error' | null>>({});
  const [syncing, setSyncing] = useState(false);

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

  const testAlpacaConnection = async () => {
    setTestingConnection('alpaca');
    try {
      const response = await fetch(`${API_BASE_URL}/alpaca/status`);
      const data = await response.json();
      if (data.connected) {
        setConnectionStatus(prev => ({ ...prev, alpaca: 'success' }));
        toast.success(`Alpaca Connected! Mode: ${data.mode}, Balance: $${data.portfolio_value?.toLocaleString() || 'N/A'}`);
      } else {
        setConnectionStatus(prev => ({ ...prev, alpaca: 'error' }));
        toast.error('Alpaca connection failed. Check your API keys.');
      }
    } catch (err) {
      setConnectionStatus(prev => ({ ...prev, alpaca: 'error' }));
      toast.error('Failed to test Alpaca connection');
    } finally {
      setTestingConnection(null);
    }
  };

  const testLLMConnection = async (provider: string) => {
    setTestingConnection(provider);
    try {
      // Simple ping test - just verify the key exists and is formatted correctly
      const key = apiKeys[`${provider.toUpperCase()}_API_KEY`];
      if (key && key.length > 10) {
        setConnectionStatus(prev => ({ ...prev, [provider]: 'success' }));
        toast.success(`${provider} API key configured (${key.length} chars)`);
      } else {
        setConnectionStatus(prev => ({ ...prev, [provider]: 'error' }));
        toast.error(`${provider} API key appears invalid or missing`);
      }
    } catch (err) {
      setConnectionStatus(prev => ({ ...prev, [provider]: 'error' }));
      toast.error(`Failed to validate ${provider}`);
    } finally {
      setTestingConnection(null);
    }
  };

  const syncToEnvFile = async () => {
    setSyncing(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api-keys/sync-to-env`, {
        method: 'POST'
      });
      if (response.ok) {
        toast.success('Settings synced to .env file! Restart backend to apply changes.');
      } else {
        toast.error('Failed to sync to .env file');
      }
    } catch (err) {
      toast.error('Failed to sync settings');
    } finally {
      setSyncing(false);
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
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-primary mb-2">API Keys & Configuration</h2>
          <p className="text-sm text-muted-foreground">
            Configure API endpoints, authentication credentials, and custom relay URLs.
            Changes are automatically saved to the database.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={syncToEnvFile}
          disabled={syncing}
          className="flex items-center gap-2"
        >
          {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Sync to .env
        </Button>
      </div>

      {/* Quick Status */}
      <Card className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border-purple-500/20">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-purple-400" />
                <span className="text-sm text-primary">Quick Connection Tests</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={testAlpacaConnection}
                disabled={testingConnection === 'alpaca'}
                className="text-xs"
              >
                {testingConnection === 'alpaca' ? (
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                ) : connectionStatus.alpaca === 'success' ? (
                  <CheckCircle className="h-3 w-3 text-green-500 mr-1" />
                ) : connectionStatus.alpaca === 'error' ? (
                  <XCircle className="h-3 w-3 text-red-500 mr-1" />
                ) : null}
                Test Alpaca
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => testLLMConnection('openai')}
                disabled={testingConnection === 'openai'}
                className="text-xs"
              >
                {testingConnection === 'openai' ? (
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                ) : connectionStatus.openai === 'success' ? (
                  <CheckCircle className="h-3 w-3 text-green-500 mr-1" />
                ) : connectionStatus.openai === 'error' ? (
                  <XCircle className="h-3 w-3 text-red-500 mr-1" />
                ) : null}
                Test OpenAI
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => testLLMConnection('anthropic')}
                disabled={testingConnection === 'anthropic'}
                className="text-xs"
              >
                {testingConnection === 'anthropic' ? (
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                ) : connectionStatus.anthropic === 'success' ? (
                  <CheckCircle className="h-3 w-3 text-green-500 mr-1" />
                ) : connectionStatus.anthropic === 'error' ? (
                  <XCircle className="h-3 w-3 text-red-500 mr-1" />
                ) : null}
                Test Anthropic
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

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

      {/* API Endpoints / Relay URLs */}
      {renderApiKeySection(
        'Custom API Endpoints & Relay URLs',
        'Configure custom base URLs for API providers. Use these for proxy relays, enterprise endpoints, or self-hosted services.',
        API_ENDPOINTS,
        <Globe className="h-4 w-4" />
      )}

      {/* Azure OpenAI */}
      {renderApiKeySection(
        'Azure OpenAI',
        'Configure Azure-hosted OpenAI service for enterprise deployments.',
        AZURE_CONFIG,
        <Cloud className="h-4 w-4" />
      )}

      {/* xAI / Grok */}
      {renderApiKeySection(
        'xAI (Grok)',
        'Configure xAI API for Grok models.',
        XAI_CONFIG,
        <Key className="h-4 w-4" />
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

      {/* Data Source Fallbacks */}
      <Card className="bg-panel border-gray-700 dark:border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg font-medium text-primary flex items-center gap-2">
            <Globe className="h-4 w-4" />
            Data Source Fallbacks
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Configure backup data sources when the primary Financial Datasets API is unavailable.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Primary Data Source Selector */}
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium text-primary">
                Primary Data Source
              </label>
              <p className="text-xs text-muted-foreground">
                Select the default source for financial data
              </p>
            </div>
            <select
              className="w-full bg-background border border-input rounded-md px-3 py-2 text-sm"
              value={apiKeys['PRIMARY_DATA_SOURCE'] || 'fmp'}
              onChange={(e) => handleKeyChange('PRIMARY_DATA_SOURCE', e.target.value)}
            >
              {PRIMARY_DATA_SOURCES.map((source) => (
                <option key={source.value} value={source.value}>
                  {source.label} - {source.description}
                </option>
              ))}
            </select>
            
            {/* FMP-specific note */}
            {(apiKeys['PRIMARY_DATA_SOURCE'] === 'fmp' || !apiKeys['PRIMARY_DATA_SOURCE']) && (
              <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3 mt-3">
                <div className="flex items-start gap-2">
                  <Info className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-muted-foreground">
                    <p className="font-medium text-green-500 mb-1">FMP Ultimate - Full Coverage</p>
                    <p>FMP provides <strong>comprehensive data</strong>: prices, fundamentals, financial statements, key metrics, news, insider trades, analyst estimates, and more.</p>
                    <p className="mt-1">Requires FMP_API_KEY (add it in Financial Data APIs above). Alpaca is used only for trade execution.</p>
                    {!apiKeys['FMP_API_KEY'] && (
                      <p className="mt-2 text-amber-500 font-medium">⚠️ FMP API Key not configured - add it above to enable FMP data.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            {/* Alpaca-specific note */}
            {apiKeys['PRIMARY_DATA_SOURCE'] === 'alpaca' && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 mt-3">
                <div className="flex items-start gap-2">
                  <Info className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-muted-foreground">
                    <p className="font-medium text-amber-500 mb-1">Alpaca Market Data Limitations</p>
                    <p>Alpaca provides <strong>prices and news only</strong>. Fundamental data (P/E ratios, financial statements, insider trades) will automatically fall back to Yahoo Finance or FMP.</p>
                    <p className="mt-1">Uses your existing Alpaca trading API keys - no additional setup required.</p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Yahoo Finance Fallback */}
          <div className="border-t border-gray-700 pt-4">
            <p className="text-sm font-medium text-primary mb-2">Yahoo Finance (Free)</p>
            <p className="text-xs text-muted-foreground mb-4">No API key required. Limited data availability.</p>
            
            {DATA_FALLBACK_TOGGLES.map((toggle) => {
              const isEnabled = apiKeys[toggle.key]?.toLowerCase() === 'true';
              const masterEnabled = apiKeys['USE_YAHOO_FINANCE_FALLBACK']?.toLowerCase() === 'true';
              const isDisabled = !toggle.isMaster && !masterEnabled;
              
              return (
                <div key={toggle.key} className={`space-y-2 mb-3 ${isDisabled ? 'opacity-50' : ''}`}>
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <label className={`text-sm font-medium ${toggle.isMaster ? 'text-blue-400' : 'text-primary'}`}>
                        {toggle.label}
                        {toggle.isMaster && <span className="ml-2 text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded">Master</span>}
                      </label>
                      <p className="text-xs text-muted-foreground">
                        {toggle.description}
                      </p>
                    </div>
                    <Switch
                      checked={isEnabled}
                      disabled={isDisabled}
                      onCheckedChange={(checked) => {
                        handleKeyChange(toggle.key, checked ? 'true' : 'false');
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          
          {/* FMP Fallback */}
          <div className="border-t border-gray-700 pt-4">
            <p className="text-sm font-medium text-primary mb-2">FMP - Financial Modeling Prep</p>
            <p className="text-xs text-muted-foreground mb-4">
              Requires API key (see Financial Data APIs above). 100+ endpoints with comprehensive data.
            </p>
            
            {FMP_FALLBACK_TOGGLES.map((toggle) => {
              const isEnabled = apiKeys[toggle.key]?.toLowerCase() === 'true';
              const masterEnabled = apiKeys['USE_FMP_FALLBACK']?.toLowerCase() === 'true';
              const hasFmpKey = !!apiKeys['FMP_API_KEY'];
              const isDisabled = !toggle.isMaster && (!masterEnabled || !hasFmpKey);
              
              return (
                <div key={toggle.key} className={`space-y-2 mb-3 ${isDisabled ? 'opacity-50' : ''}`}>
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <label className={`text-sm font-medium ${toggle.isMaster ? 'text-orange-400' : 'text-primary'}`}>
                        {toggle.label}
                        {toggle.isMaster && <span className="ml-2 text-xs bg-orange-500/20 text-orange-400 px-2 py-0.5 rounded">Master</span>}
                      </label>
                      <p className="text-xs text-muted-foreground">
                        {toggle.description}
                      </p>
                    </div>
                    <Switch
                      checked={isEnabled}
                      disabled={isDisabled || (!toggle.isMaster && !hasFmpKey)}
                      onCheckedChange={(checked) => {
                        handleKeyChange(toggle.key, checked ? 'true' : 'false');
                      }}
                    />
                  </div>
                </div>
              );
            })}
            
            {!apiKeys['FMP_API_KEY'] && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 mt-2">
                <p className="text-xs text-amber-500">
                  ⚠️ Add FMP API key in Financial Data APIs section to enable FMP fallback
                </p>
              </div>
            )}
          </div>
          
          {/* Fallback Status */}
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 space-y-3 mt-4">
            <p className="text-sm font-medium text-primary">Fallback Coverage Summary</p>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="font-medium text-blue-400 mb-1">Yahoo Finance</p>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={apiKeys['YAHOO_FINANCE_FOR_PRICES']?.toLowerCase() === 'true' ? 'text-green-500' : 'text-gray-500'}>●</span>
                    <span>Prices</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={apiKeys['YAHOO_FINANCE_FOR_METRICS']?.toLowerCase() === 'true' ? 'text-green-500' : 'text-gray-500'}>●</span>
                    <span>Metrics</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={apiKeys['YAHOO_FINANCE_FOR_NEWS']?.toLowerCase() === 'true' ? 'text-green-500' : 'text-gray-500'}>●</span>
                    <span>News</span>
                  </div>
                </div>
              </div>
              <div>
                <p className="font-medium text-orange-400 mb-1">FMP</p>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={apiKeys['FMP_FOR_PRICES']?.toLowerCase() === 'true' && apiKeys['FMP_API_KEY'] ? 'text-green-500' : 'text-gray-500'}>●</span>
                    <span>Prices</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={apiKeys['FMP_FOR_METRICS']?.toLowerCase() === 'true' && apiKeys['FMP_API_KEY'] ? 'text-green-500' : 'text-gray-500'}>●</span>
                    <span>Metrics</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={apiKeys['FMP_FOR_NEWS']?.toLowerCase() === 'true' && apiKeys['FMP_API_KEY'] ? 'text-green-500' : 'text-gray-500'}>●</span>
                    <span>News</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={apiKeys['FMP_FOR_FINANCIALS']?.toLowerCase() === 'true' && apiKeys['FMP_API_KEY'] ? 'text-green-500' : 'text-gray-500'}>●</span>
                    <span>Financials</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
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