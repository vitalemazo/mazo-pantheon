# AI Models Configuration Guide

This document explains the model system in Mazo Pantheon, including cloud API models, local Ollama models, and custom model configurations.

---

## Table of Contents

1. [Overview](#overview)
2. [Cloud Models](#cloud-models)
   - [Supported Providers](#supported-providers)
   - [Custom Models (OpenAI-Compatible)](#custom-models-openai-compatible)
   - [Model Configuration Files](#model-configuration-files)
3. [Local Models (Ollama)](#local-models-ollama)
4. [How Models Are Used](#how-models-are-used)
5. [Adding New Models](#adding-new-models)
6. [Troubleshooting](#troubleshooting)

---

## Overview

Mazo Pantheon supports **13 model providers** across two categories:

| Category | Providers | Description |
|----------|-----------|-------------|
| **Cloud API** | OpenAI, Anthropic, Google, DeepSeek, Groq, xAI, GigaChat, OpenRouter, Azure OpenAI | API-based models accessed via internet |
| **Local** | Ollama | Self-hosted models running on your machine |

The model system is configured in:
- `src/llm/models.py` - Python backend model management
- `src/llm/api_models.json` - Cloud model definitions
- `src/llm/ollama_models.json` - Local Ollama model definitions
- Settings UI → Models tab - Visual model management

---

## Cloud Models

### Supported Providers

#### 1. **OpenAI** (`OPENAI_API_KEY`)
- **Purpose**: Industry-standard LLMs with excellent instruction following
- **Models**: GPT-4.1, GPT-5.1, GPT-4o, GPT-4o-mini
- **Best for**: General analysis, structured output, reliable JSON mode
- **API Docs**: https://platform.openai.com/

#### 2. **Anthropic** (`ANTHROPIC_API_KEY`)
- **Purpose**: Claude models known for nuanced reasoning and safety
- **Models**: Claude Sonnet 4.5, Claude Haiku 4.5, Claude Opus 4.1
- **Best for**: Complex financial analysis, detailed reasoning, long context
- **API Docs**: https://anthropic.com/

#### 3. **Google** (`GOOGLE_API_KEY`)
- **Purpose**: Gemini models with multimodal capabilities
- **Models**: Gemini 2.5 Pro
- **Best for**: Research synthesis, document analysis
- **Note**: Does NOT support JSON mode - uses text parsing instead
- **API Docs**: https://ai.google.dev/

#### 4. **DeepSeek** (`DEEPSEEK_API_KEY`)
- **Purpose**: Cost-effective reasoning models from China
- **Models**: DeepSeek R1 (reasoner), DeepSeek V3 (chat)
- **Best for**: Budget-conscious deployments, reasoning tasks
- **Note**: Does NOT support JSON mode - uses text parsing instead
- **API Docs**: https://deepseek.com/

#### 5. **Groq** (`GROQ_API_KEY`)
- **Purpose**: Ultra-fast inference using custom LPU hardware
- **Models**: Various open-source models at high speed
- **Best for**: Low-latency requirements, batch processing
- **API Docs**: https://groq.com/

#### 6. **xAI** (`XAI_API_KEY`)
- **Purpose**: Grok models from Elon Musk's AI company
- **Models**: Grok 4
- **Best for**: Real-time information, unconventional perspectives
- **API Docs**: https://x.ai/

#### 7. **GigaChat** (`GIGACHAT_API_KEY`)
- **Purpose**: Russian language model from Sber
- **Models**: GigaChat-2-Max
- **Best for**: Russian market analysis, multilingual content
- **API Docs**: https://github.com/ai-forever/gigachat

#### 8. **OpenRouter** (`OPENROUTER_API_KEY`)
- **Purpose**: Meta-API that routes to 100+ models from various providers
- **Models**: GLM-4.5, GLM-4.5-Air, Qwen 3 (235B) Thinking
- **Best for**: Access to models not directly available, fallback routing
- **How it works**: Uses OpenAI-compatible API with model routing
- **API Docs**: https://openrouter.ai/

#### 9. **Azure OpenAI** (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`)
- **Purpose**: Enterprise-grade OpenAI models with Azure compliance
- **Models**: Configurable via deployment
- **Best for**: Enterprise deployments, data residency requirements
- **API Docs**: https://azure.microsoft.com/en-us/products/ai-services/openai-service

---

### Custom Models (OpenAI-Compatible)

Several models in `api_models.json` are marked as **"Custom"** and use the **OpenAI provider**. This is a powerful pattern:

```json
{
  "display_name": "Claude Opus 4.5 (Custom)",
  "model_name": "claude-opus-4-5-20251101",
  "provider": "OpenAI"
}
```

**Why does a Claude model use "OpenAI" as provider?**

These models are accessed through an **OpenAI-compatible proxy API** configured via:
- `OPENAI_API_KEY` - Your proxy API key
- `OPENAI_API_BASE` - The proxy URL (e.g., `https://www.api.xcmfai.com/v1`)

**How Custom Models Work:**

1. You set `OPENAI_API_BASE` to a proxy service URL
2. The proxy translates requests to the actual provider (Anthropic, xAI, etc.)
3. The system uses OpenAI's SDK but gets responses from other models

**Current Custom Models (Proxy-Specific):**

> ⚠️ **Important:** These model names are specific to the proxy service configured in this installation. 
> If you use a different proxy, you must update the model names in `api_models.json` to match what your proxy supports.

| Display Name | Model ID | Actual Provider |
|--------------|----------|-----------------|
| Claude Opus 4.5 (Custom) | claude-opus-4-5-20251101 | Anthropic via proxy |
| Claude Opus 4.5 Thinking (Custom) | claude-opus-4-5-20251101-thinking | Anthropic via proxy |
| Claude Sonnet 4.5 (Custom) | claude-sonnet-4-5-20250929 | Anthropic via proxy |
| Claude Sonnet 4.5 Thinking (Custom) | claude-sonnet-4-5-20250929-thinking | Anthropic via proxy |
| GPT-5.1 | gpt-5.1 | OpenAI via proxy |
| GPT-4.1 | gpt-4.1 | OpenAI via proxy |
| gpt-oss (20B/120B) | gpt-oss:20b/120b | Open-source via Ollama |

**Setting Up Custom Models:**

1. Configure your proxy credentials:
```bash
# In .env
OPENAI_API_KEY=your-proxy-api-key
OPENAI_API_BASE=https://your-proxy-service.com/v1
```

2. Check your proxy's documentation for available model names

3. Edit `src/llm/api_models.json` to add models your proxy supports:
```json
{
  "display_name": "Your Model Name (Custom)",
  "model_name": "exact-model-id-from-proxy",
  "provider": "OpenAI"
}
```

4. Restart the backend to load the new models

---

### Model Configuration Files

#### `src/llm/api_models.json`
Defines all cloud API models:

```json
[
  {
    "display_name": "Human-readable name",
    "model_name": "api-model-identifier",
    "provider": "Provider name (must match ModelProvider enum)"
  }
]
```

#### `src/llm/ollama_models.json`
Defines recommended Ollama models:

```json
[
  {
    "display_name": "Llama 3.3 (70B)",
    "model_name": "llama3.3:70b-instruct-q4_0",
    "provider": "Meta"
  }
]
```

---

## Local Models (Ollama)

### What is Ollama?

Ollama is a tool for running large language models locally on your machine. Benefits:
- **Privacy**: Data never leaves your machine
- **Cost**: No API fees after initial download
- **Latency**: No network roundtrip
- **Offline**: Works without internet

### Setup

1. Install Ollama from https://ollama.com
2. The system auto-detects Ollama installation
3. Use Settings → Models → Ollama to:
   - Start/stop the Ollama server
   - Download recommended models
   - Delete unused models

### Recommended Ollama Models

| Model | Size | Provider | Best For |
|-------|------|----------|----------|
| Gemma 3 (4B) | ~2.5GB | Google | Light tasks, fast responses |
| Qwen 3 (4B) | ~2.5GB | Alibaba | Balanced performance |
| Qwen 3 (8B) | ~5GB | Alibaba | Better reasoning |
| Llama 3.1 (8B) | ~5GB | Meta | General purpose |
| Gemma 3 (12B) | ~7GB | Google | Higher quality |
| Mistral Small 3.1 (24B) | ~14GB | Mistral | Complex tasks |
| Gemma 3 (27B) | ~16GB | Google | High quality |
| Qwen 3 (30B-a3B) | ~18GB | Alibaba | MoE efficiency |
| Llama 3.3 (70B) | ~40GB | Meta | Best quality |

### JSON Mode Support

Not all Ollama models support structured JSON output:
- ✅ **Supports JSON mode**: llama3.x, neural-chat
- ❌ **No JSON mode**: Other models use text parsing

---

## How Models Are Used

### Model Selection Flow

```
User selects model in UI
         ↓
Backend receives (model_name, model_provider)
         ↓
get_model() in src/llm/models.py
         ↓
Returns appropriate LangChain chat model
         ↓
Agents use model for analysis
```

### The `get_model()` Function

Located in `src/llm/models.py`, this function:

1. Takes `model_name`, `model_provider`, and optional `api_keys`
2. Validates the API key exists
3. Returns the correct LangChain chat model instance

```python
def get_model(model_name: str, model_provider: ModelProvider, api_keys: dict = None):
    if model_provider == ModelProvider.OPENAI:
        api_key = api_keys.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = api_keys.get("OPENAI_API_BASE") or os.getenv("OPENAI_API_BASE")
        return ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url)
    elif model_provider == ModelProvider.ANTHROPIC:
        # ... similar pattern
```

---

## Adding New Models

### Adding a Cloud Model

1. **Edit `src/llm/api_models.json`**:
```json
{
  "display_name": "New Model Name",
  "model_name": "model-api-identifier",
  "provider": "ProviderName"
}
```

2. **If new provider**, add to `ModelProvider` enum in `models.py`:
```python
class ModelProvider(str, Enum):
    NEW_PROVIDER = "NewProvider"
```

3. **Add handler in `get_model()`**:
```python
elif model_provider == ModelProvider.NEW_PROVIDER:
    api_key = api_keys.get("NEW_PROVIDER_API_KEY") or os.getenv("NEW_PROVIDER_API_KEY")
    return ChatNewProvider(model=model_name, api_key=api_key)
```

4. **Add API key to `.env`**:
```bash
NEW_PROVIDER_API_KEY=your-api-key
```

5. **Add to env sync service** (`app/backend/services/env_sync_service.py`):
```python
{
    "env_key": "NEW_PROVIDER_API_KEY",
    "provider": "NEW_PROVIDER_API_KEY",
    "description": "For NewProvider models"
},
```

### Adding an Ollama Model

1. **Edit `src/llm/ollama_models.json`**:
```json
{
  "display_name": "New Local Model",
  "model_name": "model-tag:version",
  "provider": "OriginalProvider"
}
```

2. Model will appear in Settings → Models → Ollama for download

---

## Troubleshooting

### "API Key not found" Error

**Problem**: Model fails with API key error

**Solution**:
1. Check `.env` file has the correct key
2. Verify key is synced to database (Settings → API Keys)
3. Restart backend after `.env` changes

### "Model not found" in Ollama

**Problem**: Ollama model not listed

**Solution**:
1. Ensure Ollama server is running (green status in Settings)
2. Download the model from Settings → Models → Ollama
3. Check Ollama has enough disk space

### Custom Models Not Working

**Problem**: Custom (proxy) models fail

**Solution**:
1. Verify `OPENAI_API_BASE` is set correctly
2. Check proxy service is accessible
3. Confirm API key is valid for the proxy
4. Test with: `curl -H "Authorization: Bearer $OPENAI_API_KEY" $OPENAI_API_BASE/models`

### JSON Mode Errors

**Problem**: "Model does not support JSON mode"

**Solution**:
- DeepSeek and Gemini models don't support JSON mode
- The system falls back to text parsing automatically
- Consider using OpenAI/Anthropic for tasks requiring structured output

### Rate Limiting

**Problem**: 429 errors or rate limit messages

**Solution**:
- System has built-in rate limiting (configurable via `LLM_MAX_CONCURRENT`, `LLM_REQUESTS_PER_MINUTE`)
- Reduce concurrent requests
- Consider using multiple providers to distribute load
- Enable data aggregation to reduce per-agent API calls

---

## Environment Variables Reference

| Variable | Provider | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | OpenAI | OpenAI API key |
| `OPENAI_API_BASE` | OpenAI | Custom base URL for proxies |
| `ANTHROPIC_API_KEY` | Anthropic | Claude API key |
| `GOOGLE_API_KEY` | Google | Gemini API key |
| `DEEPSEEK_API_KEY` | DeepSeek | DeepSeek API key |
| `GROQ_API_KEY` | Groq | Groq API key |
| `XAI_API_KEY` | xAI | Grok API key |
| `GIGACHAT_API_KEY` | GigaChat | GigaChat API key |
| `OPENROUTER_API_KEY` | OpenRouter | OpenRouter API key |
| `AZURE_OPENAI_API_KEY` | Azure | Azure OpenAI key |
| `AZURE_OPENAI_ENDPOINT` | Azure | Azure endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Azure | Deployment name |
| `OLLAMA_HOST` | Ollama | Ollama host (default: localhost) |
| `OLLAMA_BASE_URL` | Ollama | Ollama URL (default: http://localhost:11434) |
| `LLM_MAX_CONCURRENT` | All | Max concurrent LLM calls (default: 3) |
| `LLM_REQUESTS_PER_MINUTE` | All | Rate limit (default: 60) |
