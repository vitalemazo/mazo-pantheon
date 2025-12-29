import { DynamicStructuredTool } from '@langchain/core/tools';
import { z } from 'zod';
import { callApi, callApiWithFallback } from './api.js';
import { formatToolResult } from '../types.js';
import { getYahooNews } from './yahoo.js';
import { getFmpNews } from './fmp.js';

const NewsInputSchema = z.object({
  ticker: z
    .string()
    .describe("The stock ticker symbol to fetch news for. For example, 'AAPL' for Apple."),
  start_date: z
    .string()
    .optional()
    .describe('The start date to fetch news from (YYYY-MM-DD).'),
  end_date: z.string().optional().describe('The end date to fetch news to (YYYY-MM-DD).'),
  limit: z
    .number()
    .default(10)
    .describe('The number of news articles to retrieve. Max is 100.'),
});

export const getNews = new DynamicStructuredTool({
  name: 'get_news',
  description: `Retrieves recent news articles for a given company ticker, covering financial announcements, market trends, and other significant events. Useful for staying up-to-date with market-moving information and investor sentiment.`,
  schema: NewsInputSchema,
  func: async (input) => {
    const params: Record<string, string | number | undefined> = {
      ticker: input.ticker,
      limit: input.limit,
      start_date: input.start_date,
      end_date: input.end_date,
    };
    
    try {
      // Try primary API with Yahoo Finance and FMP fallbacks
      const result = await callApiWithFallback(
        async () => {
          const { data, url } = await callApi('/news/', params);
          return { data: { news: data.news || [] }, url };
        },
        // Yahoo Finance fallback
        async () => {
          const yahooResult = await getYahooNews(input.ticker, input.limit);
          if (yahooResult) {
            return { data: { news: yahooResult.news }, source: yahooResult.source };
          }
          return null;
        },
        // FMP fallback
        async () => {
          const fmpResult = await getFmpNews(input.ticker, input.limit);
          if (fmpResult) {
            return { data: { news: fmpResult.news }, source: fmpResult.source };
          }
          return null;
        },
        `/news/${input.ticker}`,
        'news'
      );
      
      let news = (result.data as Record<string, unknown>).news || [];
      
      // Add data source indicator
      if (result.source && Array.isArray(news)) {
        news = news.map((n: Record<string, unknown>) => ({
          ...n,
          _data_source: result.source,
        }));
      }
      
      return formatToolResult(news, [result.url]);
    } catch (error) {
      return formatToolResult(
        { error: `Failed to fetch news for ${input.ticker}: ${error}` },
        []
      );
    }
  },
});
