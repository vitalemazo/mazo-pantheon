import { DynamicStructuredTool } from '@langchain/core/tools';
import { z } from 'zod';
import { formatToolResult } from '../types.js';

// Lazy initialization to avoid errors when TAVILY_API_KEY is not set
let tavilyClient: any = null;

function getTavilyClient() {
  if (!tavilyClient) {
    const { TavilySearch } = require('@langchain/tavily');
    tavilyClient = new TavilySearch({ maxResults: 5 });
  }
  return tavilyClient;
}

export const tavilySearch = new DynamicStructuredTool({
  name: 'search_web',
  description: 'Search the web for current information on any topic. Returns relevant search results with URLs and content snippets.',
  schema: z.object({
    query: z.string().describe('The search query to look up on the web'),
  }),
  func: async (input) => {
    const client = getTavilyClient();
    const result = await client.invoke({ query: input.query });
    const parsed = typeof result === 'string' ? JSON.parse(result) : result;
    const urls = parsed.results
      ?.map((r: { url?: string }) => r.url)
      .filter((url: string | undefined): url is string => Boolean(url)) ?? [];
    return formatToolResult(parsed, urls);
  },
});
