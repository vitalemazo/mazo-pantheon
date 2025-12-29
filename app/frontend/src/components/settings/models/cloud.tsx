import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Cloud, RefreshCw, Info, FileJson, Cpu, ExternalLink, AlertCircle } from 'lucide-react';
import { useEffect, useState } from 'react';

interface CloudModelsProps {
  className?: string;
}

interface CloudModel {
  display_name: string;
  model_name: string;
  provider: string;
}

interface ModelProvider {
  name: string;
  models: Array<{
    display_name: string;
    model_name: string;
  }>;
}

// Model descriptions for tooltips/info
const MODEL_INFO: Record<string, { description: string; bestFor: string; jsonMode: boolean }> = {
  // Anthropic
  'claude-sonnet-4-5-20250929': {
    description: 'Latest Claude Sonnet - balanced speed and intelligence',
    bestFor: 'Complex analysis, detailed reasoning',
    jsonMode: true
  },
  'claude-haiku-4-5-20251001': {
    description: 'Fast, lightweight Claude model',
    bestFor: 'Quick tasks, high-volume processing',
    jsonMode: true
  },
  'claude-opus-4-1-20250805': {
    description: 'Most capable Claude model',
    bestFor: 'Complex multi-step reasoning',
    jsonMode: true
  },
  // DeepSeek
  'deepseek-reasoner': {
    description: 'DeepSeek R1 - specialized reasoning model',
    bestFor: 'Step-by-step analysis, math, logic',
    jsonMode: false
  },
  'deepseek-chat': {
    description: 'DeepSeek V3 - general conversation model',
    bestFor: 'General analysis, cost-effective',
    jsonMode: false
  },
  // Google
  'gemini-2.5-pro-preview-06-05': {
    description: 'Google Gemini Pro - multimodal capable',
    bestFor: 'Research synthesis, document analysis',
    jsonMode: false
  },
  // GigaChat
  'GigaChat-2-Max': {
    description: 'Russian language model from Sber',
    bestFor: 'Russian market analysis, multilingual',
    jsonMode: true
  },
  // xAI
  'grok-4-0709': {
    description: 'Grok 4 from xAI',
    bestFor: 'Real-time info, unconventional perspectives',
    jsonMode: true
  },
  // OpenRouter
  'z-ai/glm-4.5-air': {
    description: 'GLM-4.5 Air via OpenRouter',
    bestFor: 'Fast inference, general tasks',
    jsonMode: true
  },
  'z-ai/glm-4.5': {
    description: 'Full GLM-4.5 via OpenRouter',
    bestFor: 'Complex reasoning',
    jsonMode: true
  },
  'qwen/qwen3-235b-a22b-thinking-2507': {
    description: 'Qwen 3 235B with thinking mode',
    bestFor: 'Deep reasoning, complex problems',
    jsonMode: true
  },
  // Custom (OpenAI proxy)
  'claude-opus-4-5-20251101': {
    description: 'Claude Opus 4.5 via OpenAI-compatible proxy',
    bestFor: 'Highest capability via your proxy API',
    jsonMode: true
  },
  'claude-opus-4-5-20251101-thinking': {
    description: 'Claude Opus 4.5 with extended thinking',
    bestFor: 'Complex multi-step reasoning via proxy',
    jsonMode: true
  },
  'gpt-5.1': {
    description: 'GPT-5.1 via your configured API',
    bestFor: 'Latest OpenAI capabilities',
    jsonMode: true
  },
  'gpt-4.1': {
    description: 'GPT-4.1 via your configured API',
    bestFor: 'Reliable, well-tested model',
    jsonMode: true
  }
};

export function CloudModels({ className }: CloudModelsProps) {
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedModel, setExpandedModel] = useState<string | null>(null);

  const fetchProviders = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/language-models/providers');
      if (response.ok) {
        const data = await response.json();
        setProviders(data.providers);
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`Failed to fetch providers: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Failed to fetch cloud model providers:', error);
      setError('Failed to connect to backend service');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  // Flatten all models from all providers into a single array
  const allModels: CloudModel[] = providers.flatMap(provider =>
    provider.models.map(model => ({
      ...model,
      provider: provider.name
    }))
  ).sort((a, b) => a.provider.localeCompare(b.provider));

  const isCustomModel = (model: CloudModel) => {
    return model.display_name.includes('(Custom)') || 
           (model.provider === 'OpenAI' && model.model_name.startsWith('claude'));
  };

  const getModelInfo = (modelName: string) => {
    return MODEL_INFO[modelName] || {
      description: 'Cloud-based AI model',
      bestFor: 'General analysis tasks',
      jsonMode: true
    };
  };

  return (
    <div className={cn("space-y-6", className)}>
      
      {/* Purpose & Overview Section */}
      <Card className="bg-blue-500/5 border-blue-500/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-blue-400">About Cloud Models</h4>
              <p className="text-xs text-muted-foreground">
                This section displays all cloud-based AI models available for analysis. These models are accessed 
                via API and require the corresponding API keys configured in the <strong>API Keys</strong> tab.
              </p>
              <p className="text-xs text-muted-foreground">
                <strong>How they're used:</strong> When you run a workflow, the system uses your selected model 
                to power all 18 AI agents for stock analysis, research, and decision-making.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Source Information */}
      <Card className="bg-muted border-border">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <FileJson className="h-5 w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-primary">Where Models Come From</h4>
              <div className="text-xs text-muted-foreground space-y-1">
                <p>
                  <code className="bg-background px-1 py-0.5 rounded text-primary">src/llm/api_models.json</code>
                  <span className="ml-2">— Defines available cloud models</span>
                </p>
                <p>
                  <code className="bg-background px-1 py-0.5 rounded text-primary">src/llm/models.py</code>
                  <span className="ml-2">— Handles model initialization and API routing</span>
                </p>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                <strong>To add new models:</strong> Edit the JSON file and restart the backend. 
                See <code className="bg-background px-1 py-0.5 rounded">docs/MODELS.md</code> for details.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Custom Models Explanation */}
      <Card className="bg-amber-500/5 border-amber-500/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-amber-400">About "(Custom)" Models</h4>
              <p className="text-xs text-muted-foreground">
                Models marked <strong>(Custom)</strong> with "OpenAI" provider are accessed through your 
                <code className="bg-background px-1 py-0.5 rounded mx-1">OPENAI_API_BASE</code> 
                proxy URL. The proxy translates OpenAI-compatible API calls to other providers (Anthropic, xAI, etc.).
              </p>
              <div className="bg-amber-500/10 border border-amber-500/20 rounded p-2 text-xs">
                <p className="text-amber-400 font-medium mb-1">⚠️ These model names are proxy-specific</p>
                <p className="text-muted-foreground">
                  The custom models listed here (e.g., <code>claude-opus-4-5-20251101</code>) were added based on 
                  the current proxy's available models. If you use a different proxy, you'll need to:
                </p>
                <ol className="list-decimal list-inside mt-1 text-muted-foreground space-y-0.5">
                  <li>Check your proxy's documentation for supported model names</li>
                  <li>Edit <code className="bg-background px-1 py-0.5 rounded">src/llm/api_models.json</code> to match</li>
                  <li>Restart the backend</li>
                </ol>
              </div>
              <p className="text-xs text-muted-foreground">
                <strong>Your proxy URL:</strong> Set in API Keys → Custom API Endpoints → OpenAI API Base URL
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Read-Only Notice */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/50 px-3 py-2 rounded-md">
        <Cpu className="h-4 w-4" />
        <span>
          <strong>View Only:</strong> This list is read-only. To add or modify models, edit 
          <code className="bg-background px-1 py-0.5 rounded mx-1">src/llm/api_models.json</code> 
          and restart the backend.
        </span>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-600/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Cloud className="h-5 w-5 text-red-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-red-300">Error</h4>
              <p className="text-sm text-red-500 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-primary">Available Models</h3>
          <span className="text-xs text-muted-foreground">
            {allModels.length} models from {providers.length} providers
          </span>
        </div>

        {loading ? (
          <div className="text-center py-8">
            <RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Loading cloud models...</p>
          </div>
        ) : allModels.length > 0 ? (
          <div className="space-y-1">
            {allModels.map((model) => {
              const info = getModelInfo(model.model_name);
              const isExpanded = expandedModel === model.model_name;
              const isCustom = isCustomModel(model);
              
              return (
                <div key={`${model.provider}-${model.model_name}`}>
                  <div 
                    className={cn(
                      "group flex items-center justify-between bg-muted hover-bg rounded-md px-3 py-2.5 transition-colors cursor-pointer",
                      isExpanded && "bg-primary/5 border border-primary/20"
                    )}
                    onClick={() => setExpandedModel(isExpanded ? null : model.model_name)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm truncate text-primary">
                          {model.display_name}
                        </span>
                        {model.model_name !== model.display_name && (
                          <span className="font-mono text-xs text-muted-foreground hidden sm:inline">
                            {model.model_name}
                          </span>
                        )}
                        {isCustom && (
                          <span className="text-[10px] text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded">
                            PROXY
                          </span>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {!info.jsonMode && (
                        <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded hidden sm:inline">
                          No JSON
                        </span>
                      )}
                      <Badge className={cn(
                        "text-xs border",
                        isCustom 
                          ? "text-amber-500 bg-amber-500/10 border-amber-500/30" 
                          : "text-primary bg-primary/10 border-primary/30"
                      )}>
                        {model.provider}
                      </Badge>
                      <Info className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </div>
                  
                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="bg-background border border-border rounded-md mt-1 p-3 text-xs space-y-2">
                      <div>
                        <span className="text-muted-foreground">Description: </span>
                        <span className="text-primary">{info.description}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Best for: </span>
                        <span className="text-primary">{info.bestFor}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">JSON Mode: </span>
                        <span className={info.jsonMode ? "text-green-500" : "text-amber-500"}>
                          {info.jsonMode ? "✓ Supported" : "✗ Not supported (uses text parsing)"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Model ID: </span>
                        <code className="bg-muted px-1 py-0.5 rounded text-primary">{model.model_name}</code>
                      </div>
                      {isCustom && (
                        <div className="bg-amber-500/10 border border-amber-500/20 rounded p-2 mt-2">
                          <span className="text-amber-500">
                            ⚡ This model uses your OPENAI_API_BASE proxy. Ensure your proxy supports this model.
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          !loading && (
            <div className="text-center py-8 text-muted-foreground">
              <Cloud className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No models available</p>
              <p className="text-xs mt-1">Check your backend connection</p>
            </div>
          )
        )}
      </div>

      {/* Provider API Key Reference */}
      <Card className="bg-muted border-border">
        <CardContent className="p-4">
          <h4 className="text-sm font-medium text-primary mb-3 flex items-center gap-2">
            <ExternalLink className="h-4 w-4" />
            Required API Keys by Provider
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
            {[
              { provider: 'OpenAI', key: 'OPENAI_API_KEY' },
              { provider: 'Anthropic', key: 'ANTHROPIC_API_KEY' },
              { provider: 'Google', key: 'GOOGLE_API_KEY' },
              { provider: 'DeepSeek', key: 'DEEPSEEK_API_KEY' },
              { provider: 'Groq', key: 'GROQ_API_KEY' },
              { provider: 'xAI', key: 'XAI_API_KEY' },
              { provider: 'GigaChat', key: 'GIGACHAT_API_KEY' },
              { provider: 'OpenRouter', key: 'OPENROUTER_API_KEY' },
              { provider: 'Azure OpenAI', key: 'AZURE_OPENAI_*' },
            ].map(({ provider, key }) => (
              <div key={provider} className="flex items-center gap-2 bg-background px-2 py-1.5 rounded">
                <span className="text-muted-foreground">{provider}:</span>
                <code className="text-primary text-[10px]">{key}</code>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            Configure these in <strong>API Keys</strong> tab or in your <code>.env</code> file.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
