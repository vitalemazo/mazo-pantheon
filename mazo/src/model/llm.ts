import { ChatOpenAI } from '@langchain/openai';
import { ChatAnthropic } from '@langchain/anthropic';
import { ChatGoogleGenerativeAI } from '@langchain/google-genai';
import { ChatPromptTemplate } from '@langchain/core/prompts';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { StructuredToolInterface } from '@langchain/core/tools';
import { Runnable } from '@langchain/core/runnables';
import { z } from 'zod';
import { zodToJsonSchema } from 'zod-to-json-schema';
import { DEFAULT_SYSTEM_PROMPT } from '../agent/prompts.js';

// Check if we're using a proxy that doesn't support structured output
function isUsingProxy(): boolean {
  return !!process.env.OPENAI_API_BASE;
}

// Use Claude via OpenAI-compatible proxy
export const DEFAULT_MODEL = 'claude-sonnet-4-5-20250929';

// Generic retry helper with exponential backoff
async function withRetry<T>(fn: () => Promise<T>, maxAttempts = 3): Promise<T> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (attempt === maxAttempts - 1) throw e;
      await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
    }
  }
  throw new Error('Unreachable');
}

// Model provider configuration
interface ModelOpts {
  streaming: boolean;
}

type ModelFactory = (name: string, opts: ModelOpts) => BaseChatModel;

function getApiKey(envVar: string, providerName: string): string {
  const apiKey = process.env[envVar];
  if (!apiKey) {
    throw new Error(`${envVar} not found in environment variables`);
  }
  return apiKey;
}

const MODEL_PROVIDERS: Record<string, ModelFactory> = {
  'claude-': (name, opts) =>
    new ChatAnthropic({
      model: name,
      ...opts,
      apiKey: getApiKey('ANTHROPIC_API_KEY', 'Anthropic'),
    }),
  'gemini-': (name, opts) =>
    new ChatGoogleGenerativeAI({
      model: name,
      ...opts,
      apiKey: getApiKey('GOOGLE_API_KEY', 'Google'),
    }),
};

const DEFAULT_PROVIDER: ModelFactory = (name, opts) => {
  const config: any = {
    model: name,
    ...opts,
    apiKey: process.env.OPENAI_API_KEY,
  };

  // Support custom base URL for OpenAI-compatible APIs
  if (process.env.OPENAI_API_BASE) {
    config.configuration = {
      baseURL: process.env.OPENAI_API_BASE,
    };
  }

  return new ChatOpenAI(config);
};

export function getChatModel(
  modelName: string = DEFAULT_MODEL,
  streaming: boolean = false
): BaseChatModel {
  const opts: ModelOpts = { streaming };

  // If OPENAI_API_BASE is set, use the OpenAI-compatible proxy for ALL models
  // This allows using Claude models through proxies like xcmfai.com
  if (process.env.OPENAI_API_BASE) {
    return DEFAULT_PROVIDER(modelName, opts);
  }

  // Otherwise, use the appropriate provider based on model name
  const prefix = Object.keys(MODEL_PROVIDERS).find((p) => modelName.startsWith(p));
  const factory = prefix ? MODEL_PROVIDERS[prefix] : DEFAULT_PROVIDER;
  return factory(modelName, opts);
}

interface CallLlmOptions {
  model?: string;
  systemPrompt?: string;
  outputSchema?: z.ZodType<unknown>;
  tools?: StructuredToolInterface[];
}

export async function callLlm(prompt: string, options: CallLlmOptions = {}): Promise<unknown> {
  const { model = DEFAULT_MODEL, systemPrompt, outputSchema, tools } = options;
  const finalSystemPrompt = systemPrompt || DEFAULT_SYSTEM_PROMPT;

  const llm = getChatModel(model, false);

  // When using a proxy, use JSON prompting instead of structured output
  // because most proxies don't support OpenAI's function calling format
  if (outputSchema && isUsingProxy()) {
    return callLlmWithJsonPrompt(prompt, {
      model,
      systemPrompt: finalSystemPrompt,
      outputSchema,
    });
  }

  const promptTemplate = ChatPromptTemplate.fromMessages([
    ['system', finalSystemPrompt],
    ['user', '{prompt}'],
  ]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let runnable: Runnable<any, any> = llm;

  if (outputSchema) {
    runnable = llm.withStructuredOutput(outputSchema);
  } else if (tools && tools.length > 0 && llm.bindTools) {
    runnable = llm.bindTools(tools);
  }

  const chain = promptTemplate.pipe(runnable);

  const result = await withRetry(() => chain.invoke({ prompt }));

  // If no outputSchema and no tools, extract content from AIMessage
  // When tools are provided, return the full AIMessage to preserve tool_calls
  if (!outputSchema && !tools && result && typeof result === 'object' && 'content' in result) {
    return (result as { content: string }).content;
  }
  return result;
}

/**
 * Call LLM with JSON prompting (for proxies that don't support structured output)
 */
async function callLlmWithJsonPrompt(
  prompt: string,
  options: { model: string; systemPrompt: string; outputSchema: z.ZodType<unknown> }
): Promise<unknown> {
  const { model, systemPrompt, outputSchema } = options;

  // Convert Zod schema to JSON Schema for the prompt
  const jsonSchema = zodToJsonSchema(outputSchema, 'output');
  const schemaStr = JSON.stringify(jsonSchema.definitions?.output || jsonSchema, null, 2);

  // Build enhanced system prompt that includes JSON schema
  // Escape curly braces to prevent LangChain from treating them as template variables
  const escapedSchema = schemaStr.replace(/\{/g, '{{').replace(/\}/g, '}}');
  const escapedSystemPrompt = systemPrompt.replace(/\{/g, '{{').replace(/\}/g, '}}');

  const enhancedSystemPrompt = `${escapedSystemPrompt}

IMPORTANT: You must respond with ONLY valid JSON that matches this schema:
${escapedSchema}

Do not include any text before or after the JSON. Do not use markdown code blocks.`;

  const promptTemplate = ChatPromptTemplate.fromMessages([
    ['system', enhancedSystemPrompt],
    ['user', '{prompt}'],
  ]);

  const llm = getChatModel(model, false);
  const chain = promptTemplate.pipe(llm);

  const result = await withRetry(() => chain.invoke({ prompt }));

  // Extract content from AIMessage
  let content = '';
  if (result && typeof result === 'object' && 'content' in result) {
    content = (result as { content: string }).content;
  } else if (typeof result === 'string') {
    content = result;
  }

  // Clean up the response - remove markdown code blocks if present
  content = content.trim();
  if (content.startsWith('```json')) {
    content = content.slice(7);
  } else if (content.startsWith('```')) {
    content = content.slice(3);
  }
  if (content.endsWith('```')) {
    content = content.slice(0, -3);
  }
  content = content.trim();

  // Parse JSON response
  try {
    const parsed = JSON.parse(content);
    // Validate against schema - use safeParse for better error messages
    const result = outputSchema.safeParse(parsed);
    if (result.success) {
      return result.data;
    }
    // If validation failed, try to coerce the response to match the schema
    // This handles cases where the LLM adds extra fields or uses different enum values
    console.error('Schema validation warning:', result.error.message);
    // Return the parsed JSON anyway - let the caller handle any type mismatches
    return parsed;
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : String(e);
    throw new Error(`Failed to parse LLM response as JSON: ${errorMsg}\nResponse: ${content.substring(0, 500)}`);
  }
}

export async function* callLlmStream(
  prompt: string,
  options: { model?: string; systemPrompt?: string } = {}
): AsyncGenerator<string> {
  const { model = DEFAULT_MODEL, systemPrompt } = options;
  const finalSystemPrompt = systemPrompt || DEFAULT_SYSTEM_PROMPT;

  const promptTemplate = ChatPromptTemplate.fromMessages([
    ['system', finalSystemPrompt],
    ['user', '{prompt}'],
  ]);

  const llm = getChatModel(model, true);
  const chain = promptTemplate.pipe(llm);

  // For streaming, we handle retry at the connection level
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const stream = await chain.stream({ prompt });

      for await (const chunk of stream) {
        if (chunk && typeof chunk === 'object' && 'content' in chunk) {
          const content = chunk.content;
          if (content && typeof content === 'string') {
            yield content;
          }
        }
      }
      return;
    } catch (e) {
      if (attempt === 2) throw e;
      await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
    }
  }
}
