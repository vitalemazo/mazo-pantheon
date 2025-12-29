import { DynamicStructuredTool } from '@langchain/core/tools';
import { z } from 'zod';
import { callApi, callApiWithFallback } from './api.js';
import { formatToolResult } from '../types.js';
import { getYahooFinancialMetrics } from './yahoo.js';
import { getFmpFinancialMetrics } from './fmp.js';

const FinancialMetricsSnapshotInputSchema = z.object({
  ticker: z
    .string()
    .describe(
      "The stock ticker symbol to fetch financial metrics snapshot for. For example, 'AAPL' for Apple."
    ),
});

export const getFinancialMetricsSnapshot = new DynamicStructuredTool({
  name: 'get_financial_metrics_snapshot',
  description: `Fetches a snapshot of the most current financial metrics for a company, including key indicators like market capitalization, P/E ratio, and dividend yield. Useful for a quick overview of a company's financial health.`,
  schema: FinancialMetricsSnapshotInputSchema,
  func: async (input) => {
    const params = { ticker: input.ticker };
    
    try {
      // Try primary API with Yahoo Finance and FMP fallbacks
      const result = await callApiWithFallback(
        async () => {
          const { data, url } = await callApi('/financial-metrics/snapshot/', params);
          return { data: { snapshot: data.snapshot || {} }, url };
        },
        // Yahoo Finance fallback
        async () => {
          const yahooResult = await getYahooFinancialMetrics(input.ticker);
          if (yahooResult) {
            return { data: { snapshot: yahooResult.metrics }, source: yahooResult.source };
          }
          return null;
        },
        // FMP fallback
        async () => {
          const fmpResult = await getFmpFinancialMetrics(input.ticker);
          if (fmpResult) {
            return { data: { snapshot: fmpResult.metrics }, source: fmpResult.source };
          }
          return null;
        },
        `/financial-metrics/snapshot/${input.ticker}`,
        'metrics'
      );
      
      const snapshot = (result.data as Record<string, unknown>).snapshot || {};
      if (result.source) {
        (snapshot as Record<string, unknown>)._data_source = result.source;
      }
      
      return formatToolResult(snapshot, [result.url]);
    } catch (error) {
      return formatToolResult(
        { error: `Failed to fetch financial metrics snapshot for ${input.ticker}: ${error}` },
        []
      );
    }
  },
});

const FinancialMetricsInputSchema = z.object({
  ticker: z
    .string()
    .describe(
      "The stock ticker symbol to fetch financial metrics for. For example, 'AAPL' for Apple."
    ),
  period: z
    .enum(['annual', 'quarterly', 'ttm'])
    .default('ttm')
    .describe(
      "The reporting period. 'annual' for yearly, 'quarterly' for quarterly, and 'ttm' for trailing twelve months."
    ),
  limit: z
    .number()
    .default(4)
    .describe('The number of past financial statements to retrieve.'),
  report_period: z
    .string()
    .optional()
    .describe('Filter for financial metrics with an exact report period date (YYYY-MM-DD).'),
  report_period_gt: z
    .string()
    .optional()
    .describe('Filter for financial metrics with report periods after this date (YYYY-MM-DD).'),
  report_period_gte: z
    .string()
    .optional()
    .describe(
      'Filter for financial metrics with report periods on or after this date (YYYY-MM-DD).'
    ),
  report_period_lt: z
    .string()
    .optional()
    .describe('Filter for financial metrics with report periods before this date (YYYY-MM-DD).'),
  report_period_lte: z
    .string()
    .optional()
    .describe(
      'Filter for financial metrics with report periods on or before this date (YYYY-MM-DD).'
    ),
});

export const getFinancialMetrics = new DynamicStructuredTool({
  name: 'get_financial_metrics',
  description: `Retrieves historical financial metrics for a company, such as P/E ratio, revenue per share, and enterprise value, over a specified period. Useful for trend analysis and historical performance evaluation.`,
  schema: FinancialMetricsInputSchema,
  func: async (input) => {
    const params: Record<string, string | number | undefined> = {
      ticker: input.ticker,
      period: input.period,
      limit: input.limit,
      report_period: input.report_period,
      report_period_gt: input.report_period_gt,
      report_period_gte: input.report_period_gte,
      report_period_lt: input.report_period_lt,
      report_period_lte: input.report_period_lte,
    };
    
    try {
      // Try primary API with Yahoo Finance and FMP fallbacks
      const result = await callApiWithFallback(
        async () => {
          const { data, url } = await callApi('/financial-metrics/', params);
          return { data: { financial_metrics: data.financial_metrics || [] }, url };
        },
        // Yahoo Finance fallback (provides current metrics only)
        async () => {
          const yahooResult = await getYahooFinancialMetrics(input.ticker);
          if (yahooResult) {
            return { 
              data: { financial_metrics: [yahooResult.metrics] }, 
              source: yahooResult.source 
            };
          }
          return null;
        },
        // FMP fallback
        async () => {
          const fmpResult = await getFmpFinancialMetrics(input.ticker);
          if (fmpResult) {
            return { 
              data: { financial_metrics: [fmpResult.metrics] }, 
              source: fmpResult.source 
            };
          }
          return null;
        },
        `/financial-metrics/${input.ticker}`,
        'metrics'
      );
      
      let metrics = (result.data as Record<string, unknown>).financial_metrics || [];
      
      // Add data source indicator
      if (result.source && Array.isArray(metrics)) {
        metrics = metrics.map((m: Record<string, unknown>) => ({
          ...m,
          _data_source: result.source,
        }));
      }
      
      return formatToolResult(metrics, [result.url]);
    } catch (error) {
      return formatToolResult(
        { error: `Failed to fetch financial metrics for ${input.ticker}: ${error}` },
        []
      );
    }
  },
});
