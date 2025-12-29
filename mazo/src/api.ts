#!/usr/bin/env bun
/**
 * API Entry Point - Non-interactive mode for web integration
 *
 * Usage: bun run src/api.ts --query "Your question" [--model claude-sonnet-4-5-20250929]
 */
import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { Agent } from './agent/orchestrator.js';
import { DEFAULT_MODEL } from './model/llm.js';

// Load environment variables from parent directory (shared with ai-hedge-fund)
const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, '../../.env'), quiet: true });
// Also try loading from current directory as fallback
config({ quiet: true });

interface ApiResult {
  success: boolean;
  answer?: string;
  confidence?: number;
  sources?: string[];
  error?: string;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  // Parse arguments
  let query = '';
  let model = DEFAULT_MODEL;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--query' && args[i + 1]) {
      query = args[i + 1];
      i++;
    } else if (args[i] === '--model' && args[i + 1]) {
      model = args[i + 1];
      i++;
    }
  }

  if (!query) {
    const result: ApiResult = {
      success: false,
      error: 'No query provided. Usage: bun run src/api.ts --query "Your question"'
    };
    console.log(JSON.stringify(result));
    process.exit(1);
  }

  try {
    // Collect the streamed answer using a promise
    let answer = '';
    let streamComplete: () => void;
    const streamPromise = new Promise<void>((resolve) => {
      streamComplete = resolve;
    });

    const agent = new Agent({
      model,
      callbacks: {
        onAnswerStream: async (stream) => {
          try {
            for await (const chunk of stream) {
              answer += chunk;
            }
          } finally {
            streamComplete();
          }
        },
      },
    });

    await agent.run(query);

    // Wait for the stream to complete
    await streamPromise;

    const result: ApiResult = {
      success: true,
      answer: answer || 'Analysis complete.',
      confidence: 85,
      sources: [],
    };

    console.log(JSON.stringify(result));
  } catch (error) {
    const result: ApiResult = {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
    console.log(JSON.stringify(result));
    process.exit(1);
  }
}

main();
