import { StructuredToolInterface } from '@langchain/core/tools';
import { AIMessage } from '@langchain/core/messages';
import { z } from 'zod';
import { callLlm, DEFAULT_MODEL } from '../model/llm.js';
import { ToolContextManager } from '../utils/context.js';
import { getToolSelectionSystemPrompt, buildToolSelectionPrompt } from './prompts.js';
import type { Task, ToolCallStatus, Understanding } from './state.js';

// ============================================================================
// Constants
// ============================================================================

// Use a small/fast model for tool selection when available
// Falls back to DEFAULT_MODEL when using proxies that don't support gpt-5-mini
const SMALL_MODEL = process.env.OPENAI_API_BASE ? DEFAULT_MODEL : 'gpt-5-mini';

// Schema for tool selection response (for proxies that don't support tool binding)
// Note: We accept flexible field names since LLMs may use name/tool and args/arguments
const ToolCallSchema = z.object({
  name: z.string().optional().describe('Tool name'),
  tool: z.string().optional().describe('Tool name (alternative)'),
  args: z.record(z.string(), z.any()).optional().describe('Tool arguments'),
  arguments: z.record(z.string(), z.any()).optional().describe('Tool arguments (alternative)'),
});

const ToolSelectionSchema = z.object({
  tool_calls: z.array(ToolCallSchema).describe('List of tool calls to make'),
});

// Transform tool call to normalize field names
function normalizeToolCall(tc: z.infer<typeof ToolCallSchema>): { name: string; args: Record<string, unknown> } {
  return {
    name: tc.name || tc.tool || '',
    args: tc.args || tc.arguments || {},
  };
}

// ============================================================================
// Tool Executor Options
// ============================================================================

export interface ToolExecutorOptions {
  tools: StructuredToolInterface[];
  contextManager: ToolContextManager;
}

// ============================================================================
// Tool Executor Callbacks
// ============================================================================

export interface ToolExecutorCallbacks {
  onToolCallUpdate?: (taskId: string, toolIndex: number, status: ToolCallStatus['status']) => void;
  onToolCallError?: (taskId: string, toolIndex: number, toolName: string, args: Record<string, unknown>, error: Error) => void;
}

// ============================================================================
// Tool Executor Implementation
// ============================================================================

/**
 * Handles tool selection and execution for tasks.
 * Uses a small, fast model (gpt-5-mini) for tool selection.
 */
export class ToolExecutor {
  private readonly tools: StructuredToolInterface[];
  private readonly toolMap: Map<string, StructuredToolInterface>;
  private readonly contextManager: ToolContextManager;

  constructor(options: ToolExecutorOptions) {
    this.tools = options.tools;
    this.toolMap = new Map(options.tools.map(t => [t.name, t]));
    this.contextManager = options.contextManager;
  }

  /**
   * Selects tools for a task.
   * Uses JSON schema output when using a proxy (since tool binding isn't supported).
   */
  async selectTools(
    task: Task,
    understanding: Understanding
  ): Promise<ToolCallStatus[]> {
    const tickers = understanding.entities
      .filter(e => e.type === 'ticker')
      .map(e => e.value);

    const periods = understanding.entities
      .filter(e => e.type === 'period')
      .map(e => e.value);

    const prompt = buildToolSelectionPrompt(task.description, tickers, periods);
    const systemPrompt = getToolSelectionSystemPrompt(this.formatToolDescriptions());

    // When using a proxy, use JSON schema output instead of tool binding
    // because most proxies don't support OpenAI's function calling format
    if (process.env.OPENAI_API_BASE) {
      const response = await callLlm(prompt, {
        model: SMALL_MODEL,
        systemPrompt,
        outputSchema: ToolSelectionSchema,
      });

      const result = response as { tool_calls: z.infer<typeof ToolCallSchema>[] };
      return (result.tool_calls || []).map(tc => {
        const normalized = normalizeToolCall(tc);
        return {
          tool: normalized.name,
          args: normalized.args,
          status: 'pending' as const,
        };
      });
    }

    // Use native tool binding when not using a proxy
    const response = await callLlm(prompt, {
      model: SMALL_MODEL,
      systemPrompt,
      tools: this.tools,
    });

    const toolCalls = this.extractToolCalls(response);
    return toolCalls.map(tc => ({ ...tc, status: 'pending' as const }));
  }

  /**
   * Executes tool calls for a task and saves results to context.
   * Returns true if all tool calls succeeded, false if any failed.
   */
  async executeTools(
    task: Task,
    queryId: string,
    callbacks?: ToolExecutorCallbacks
  ): Promise<boolean> {
    if (!task.toolCalls) return true;

    let allSucceeded = true;

    await Promise.all(
      task.toolCalls.map(async (toolCall, index) => {
        callbacks?.onToolCallUpdate?.(task.id, index, 'running');
        
        try {
          const tool = this.toolMap.get(toolCall.tool);
          if (!tool) {
            throw new Error(`Tool not found: ${toolCall.tool}`);
          }

          const result = await tool.invoke(toolCall.args);

          this.contextManager.saveContext(
            toolCall.tool,
            toolCall.args,
            result,
            undefined,
            queryId
          );

          toolCall.status = 'completed';
          callbacks?.onToolCallUpdate?.(task.id, index, 'completed');
        } catch (error) {
          allSucceeded = false;
          toolCall.status = 'failed';
          callbacks?.onToolCallUpdate?.(task.id, index, 'failed');
          callbacks?.onToolCallError?.(
            task.id, 
            index, 
            toolCall.tool,
            toolCall.args,
            error instanceof Error ? error : new Error(String(error))
          );
        }
      })
    );

    return allSucceeded;
  }

  /**
   * Formats tool descriptions for the prompt.
   */
  private formatToolDescriptions(): string {
    return this.tools.map(tool => {
      const schema = tool.schema;
      let argsDescription = '';
      
      if (schema && typeof schema === 'object' && 'shape' in schema) {
        const shape = schema.shape as Record<string, { description?: string }>;
        const args = Object.entries(shape)
          .map(([key, value]) => `  - ${key}: ${value.description || 'No description'}`)
          .join('\n');
        argsDescription = args ? `\n  Arguments:\n${args}` : '';
      }
      
      return `- ${tool.name}: ${tool.description}${argsDescription}`;
    }).join('\n\n');
  }

  /**
   * Extracts tool calls from an LLM response.
   */
  private extractToolCalls(response: unknown): Array<{ tool: string; args: Record<string, unknown> }> {
    if (!response || typeof response !== 'object') return [];
    
    const message = response as AIMessage;
    if (!message.tool_calls || !Array.isArray(message.tool_calls)) return [];

    return message.tool_calls.map(tc => ({
      tool: tc.name,
      args: tc.args as Record<string, unknown>,
    }));
  }
}

