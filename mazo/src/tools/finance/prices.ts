import { DynamicStructuredTool } from '@langchain/core/tools';
import { z } from 'zod';
import { callApi, callApiWithFallback } from './api.js';
import { formatToolResult } from '../types.js';
import { getYahooPriceSnapshot, getYahooHistoricalPrices } from './yahoo.js';
import { getFmpPriceSnapshot, getFmpHistoricalPrices } from './fmp.js';

const PriceSnapshotInputSchema = z.object({
  ticker: z
    .string()
    .describe(
      "The stock ticker symbol to fetch the price snapshot for. For example, 'AAPL' for Apple."
    ),
});

export const getPriceSnapshot = new DynamicStructuredTool({
  name: 'get_price_snapshot',
  description: `Fetches the most recent price snapshot for a specific stock ticker, including the latest price, trading volume, and other open, high, low, and close price data.`,
  schema: PriceSnapshotInputSchema,
  func: async (input) => {
    const params = { ticker: input.ticker };
    
    try {
      // Try primary API with Yahoo Finance and FMP fallbacks
      const result = await callApiWithFallback(
        async () => {
          const { data, url } = await callApi('/prices/snapshot/', params);
          return { data: { snapshot: data.snapshot || {} }, url };
        },
        // Yahoo Finance fallback
        async () => {
          const yahooResult = await getYahooPriceSnapshot(input.ticker);
          if (yahooResult) {
            return { data: { snapshot: yahooResult.snapshot }, source: yahooResult.source };
          }
          return null;
        },
        // FMP fallback
        async () => {
          const fmpResult = await getFmpPriceSnapshot(input.ticker);
          if (fmpResult) {
            return { data: { snapshot: fmpResult.snapshot }, source: fmpResult.source };
          }
          return null;
        },
        `/prices/snapshot/${input.ticker}`,
        'prices'
      );
      
      const snapshot = (result.data as Record<string, unknown>).snapshot || {};
      const sources = [result.url];
      if (result.source) {
        (snapshot as Record<string, unknown>)._data_source = result.source;
      }
      
      return formatToolResult(snapshot, sources);
    } catch (error) {
      // If all fallbacks fail, return error message
      return formatToolResult(
        { error: `Failed to fetch price snapshot for ${input.ticker}: ${error}` },
        []
      );
    }
  },
});

const PricesInputSchema = z.object({
  ticker: z
    .string()
    .describe(
      "The stock ticker symbol to fetch aggregated prices for. For example, 'AAPL' for Apple."
    ),
  interval: z
    .enum(['minute', 'day', 'week', 'month', 'year'])
    .default('day')
    .describe("The time interval for price data. Defaults to 'day'."),
  interval_multiplier: z
    .number()
    .default(1)
    .describe('Multiplier for the interval. Defaults to 1.'),
  start_date: z.string().describe('Start date in YYYY-MM-DD format. Must be in past. Required.'),
  end_date: z.string().describe('End date in YYYY-MM-DD format. Must be today or in the past. Required.'),
});

export const getPrices = new DynamicStructuredTool({
  name: 'get_prices',
  description: `Retrieves historical price data for a stock over a specified date range, including open, high, low, close prices, and volume.`,
  schema: PricesInputSchema,
  func: async (input) => {
    const params = {
      ticker: input.ticker,
      interval: input.interval,
      interval_multiplier: input.interval_multiplier,
      start_date: input.start_date,
      end_date: input.end_date,
    };
    
    try {
      // Try primary API with Yahoo Finance and FMP fallbacks
      const result = await callApiWithFallback(
        async () => {
          const { data, url } = await callApi('/prices/', params);
          return { data: { prices: data.prices || [] }, url };
        },
        // Yahoo Finance fallback
        async () => {
          const yahooResult = await getYahooHistoricalPrices(
            input.ticker,
            input.start_date,
            input.end_date
          );
          if (yahooResult) {
            return { data: { prices: yahooResult.prices }, source: yahooResult.source };
          }
          return null;
        },
        // FMP fallback
        async () => {
          const fmpResult = await getFmpHistoricalPrices(
            input.ticker,
            input.start_date,
            input.end_date
          );
          if (fmpResult) {
            return { data: { prices: fmpResult.prices }, source: fmpResult.source };
          }
          return null;
        },
        `/prices/${input.ticker}`,
        'prices'
      );
      
      const prices = (result.data as Record<string, unknown>).prices || [];
      
      // Add data source indicator to response
      let finalPrices = prices;
      if (result.source && Array.isArray(prices)) {
        finalPrices = prices.map((p: Record<string, unknown>) => ({
          ...p,
          _data_source: result.source,
        }));
      }
      
      return formatToolResult(finalPrices, [result.url]);
    } catch (error) {
      // If all fallbacks fail, return error message
      return formatToolResult(
        { error: `Failed to fetch prices for ${input.ticker}: ${error}` },
        []
      );
    }
  },
});
