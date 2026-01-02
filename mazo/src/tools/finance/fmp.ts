/**
 * FMP (Financial Modeling Prep) Data Client
 * 
 * Primary data source when PRIMARY_DATA_SOURCE=fmp.
 * Provides comprehensive financial data including:
 * - Real-time and historical prices
 * - Company profiles and key metrics
 * - News and press releases
 * - Income statements, balance sheets, cash flow
 * - Insider trading data
 * 
 * API Documentation: https://financialmodelingprep.com/developer/docs
 */

const FMP_BASE_URL = 'https://financialmodelingprep.com/stable';

/**
 * Get FMP API key from environment.
 */
function getFmpApiKey(): string | undefined {
  return process.env.FMP_API_KEY;
}

/**
 * Fetch current price snapshot from FMP.
 */
export async function getFmpPriceSnapshot(ticker: string): Promise<{
  snapshot: Record<string, unknown>;
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/quote?symbol=${ticker}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP quote failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data) || data.length === 0) {
      return null;
    }

    const quote = data[0];

    return {
      snapshot: {
        ticker: quote.symbol,
        price: quote.price,
        open: quote.open,
        high: quote.dayHigh,
        low: quote.dayLow,
        close: quote.previousClose,
        volume: quote.volume,
        change: quote.change,
        change_percent: quote.changesPercentage,
        market_cap: quote.marketCap,
        pe_ratio: quote.pe,
        eps: quote.eps,
        year_high: quote.yearHigh,
        year_low: quote.yearLow,
        avg_volume: quote.avgVolume,
        exchange: quote.exchange,
        _source: 'FMP',
      },
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP price snapshot error:', error);
    return null;
  }
}

/**
 * Fetch historical prices from FMP.
 */
export async function getFmpHistoricalPrices(
  ticker: string,
  startDate: string,
  endDate: string
): Promise<{
  prices: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/historical-price-eod/full?symbol=${ticker}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP historical prices failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    // Filter by date range and format
    const prices = data
      .filter((item: Record<string, unknown>) => {
        const date = item.date as string;
        return date >= startDate && date <= endDate;
      })
      .map((item: Record<string, unknown>) => ({
        time: item.date,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
        volume: item.volume,
        adjusted_close: item.adjClose,
        _source: 'FMP',
      }))
      .sort((a: Record<string, unknown>, b: Record<string, unknown>) => 
        (a.time as string).localeCompare(b.time as string)
      );

    return {
      prices,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP historical prices error:', error);
    return null;
  }
}

/**
 * Fetch company profile/metrics from FMP.
 */
export async function getFmpFinancialMetrics(ticker: string): Promise<{
  metrics: Record<string, unknown>;
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/profile?symbol=${ticker}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP profile failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data) || data.length === 0) {
      return null;
    }

    const profile = data[0];

    return {
      metrics: {
        ticker,
        company_name: profile.companyName,
        exchange: profile.exchangeShortName,
        industry: profile.industry,
        sector: profile.sector,
        description: profile.description,
        ceo: profile.ceo,
        website: profile.website,
        market_cap: profile.mktCap,
        price: profile.price,
        beta: profile.beta,
        vol_avg: profile.volAvg,
        last_div: profile.lastDiv,
        range: profile.range,
        currency: profile.currency,
        ipo_date: profile.ipoDate,
        full_time_employees: profile.fullTimeEmployees,
        _source: 'FMP',
        _report_period: new Date().toISOString().split('T')[0],
      },
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP profile error:', error);
    return null;
  }
}

/**
 * Fetch company news from FMP.
 */
export async function getFmpNews(ticker: string, limit: number = 10): Promise<{
  news: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/stock-news?symbol=${ticker}&limit=${limit}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP news failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    const news = data.slice(0, limit).map((item: Record<string, unknown>) => ({
      title: item.title,
      url: item.url,
      source: item.site,
      date: item.publishedDate,
      text: item.text,
      image: item.image,
      symbol: item.symbol,
      _source: 'FMP',
    }));

    return {
      news,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP news error:', error);
    return null;
  }
}

/**
 * Fetch income statements from FMP.
 */
export async function getFmpIncomeStatements(
  ticker: string,
  period: 'annual' | 'quarter' = 'annual',
  limit: number = 5
): Promise<{
  statements: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/income-statement?symbol=${ticker}&period=${period}&limit=${limit}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP income statement failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    const statements = data.map((item: Record<string, unknown>) => ({
      ...item,
      _source: 'FMP',
    }));

    return {
      statements,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP income statement error:', error);
    return null;
  }
}

/**
 * Fetch balance sheet statements from FMP.
 */
export async function getFmpBalanceSheets(
  ticker: string,
  period: 'annual' | 'quarter' = 'annual',
  limit: number = 5
): Promise<{
  statements: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/balance-sheet-statement?symbol=${ticker}&period=${period}&limit=${limit}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MazoAgent/1.0)',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP balance sheet failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    const statements = data.map((item: Record<string, unknown>) => ({
      ...item,
      _source: 'FMP',
    }));

    return {
      statements,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP balance sheet error:', error);
    return null;
  }
}

/**
 * Fetch cash flow statements from FMP.
 */
export async function getFmpCashFlowStatements(
  ticker: string,
  period: 'annual' | 'quarter' = 'annual',
  limit: number = 5
): Promise<{
  statements: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/cash-flow-statement?symbol=${ticker}&period=${period}&limit=${limit}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MazoAgent/1.0)',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP cash flow failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    const statements = data.map((item: Record<string, unknown>) => ({
      ...item,
      _source: 'FMP',
    }));

    return {
      statements,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP cash flow error:', error);
    return null;
  }
}

/**
 * Fetch SEC filings from FMP.
 */
export async function getFmpSecFilings(
  ticker: string,
  type?: string,
  limit: number = 20
): Promise<{
  filings: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    let url = `${FMP_BASE_URL}/sec_filings?symbol=${ticker}&limit=${limit}&apikey=${apiKey}`;
    if (type) {
      url += `&type=${type}`;
    }
    
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MazoAgent/1.0)',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP SEC filings failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    const filings = data.map((item: Record<string, unknown>) => ({
      type: item.type,
      filing_date: item.fillingDate,
      accepted_date: item.acceptedDate,
      cik: item.cik,
      link: item.link,
      final_link: item.finalLink,
      _source: 'FMP',
    }));

    return {
      filings,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP SEC filings error:', error);
    return null;
  }
}

/**
 * Fetch analyst estimates from FMP.
 */
export async function getFmpAnalystEstimates(
  ticker: string,
  period: 'annual' | 'quarter' = 'annual',
  limit: number = 10
): Promise<{
  estimates: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/analyst-estimates?symbol=${ticker}&period=${period}&limit=${limit}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MazoAgent/1.0)',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP analyst estimates failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    const estimates = data.map((item: Record<string, unknown>) => ({
      symbol: item.symbol,
      date: item.date,
      estimated_revenue_low: item.estimatedRevenueLow,
      estimated_revenue_high: item.estimatedRevenueHigh,
      estimated_revenue_avg: item.estimatedRevenueAvg,
      estimated_ebitda_low: item.estimatedEbitdaLow,
      estimated_ebitda_high: item.estimatedEbitdaHigh,
      estimated_ebitda_avg: item.estimatedEbitdaAvg,
      estimated_ebit_low: item.estimatedEbitLow,
      estimated_ebit_high: item.estimatedEbitHigh,
      estimated_ebit_avg: item.estimatedEbitAvg,
      estimated_net_income_low: item.estimatedNetIncomeLow,
      estimated_net_income_high: item.estimatedNetIncomeHigh,
      estimated_net_income_avg: item.estimatedNetIncomeAvg,
      estimated_eps_low: item.estimatedEpsLow,
      estimated_eps_high: item.estimatedEpsHigh,
      estimated_eps_avg: item.estimatedEpsAvg,
      number_analyst_estimated_revenue: item.numberAnalystEstimatedRevenue,
      number_analysts_estimated_eps: item.numberAnalystsEstimatedEps,
      _source: 'FMP',
    }));

    return {
      estimates,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP analyst estimates error:', error);
    return null;
  }
}

/**
 * Fetch revenue by product/segment from FMP.
 */
export async function getFmpRevenueSegmentation(
  ticker: string,
  period: 'annual' | 'quarter' = 'annual'
): Promise<{
  segments: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/revenue-product-segmentation?symbol=${ticker}&period=${period}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MazoAgent/1.0)',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP revenue segmentation failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    const segments = data.map((item: Record<string, unknown>) => ({
      ...item,
      _source: 'FMP',
    }));

    return {
      segments,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP revenue segmentation error:', error);
    return null;
  }
}

/**
 * Fetch insider trading data from FMP.
 */
export async function getFmpInsiderTrading(
  ticker: string,
  limit: number = 20
): Promise<{
  trades: Record<string, unknown>[];
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/insider-trading?symbol=${ticker}&limit=${limit}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MazoAgent/1.0)',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP insider trading failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data)) {
      return null;
    }

    const trades = data.map((item: Record<string, unknown>) => ({
      symbol: item.symbol,
      filing_date: item.filingDate,
      transaction_date: item.transactionDate,
      reporting_name: item.reportingName,
      transaction_type: item.transactionType,
      securities_owned: item.securitiesOwned,
      securities_transacted: item.securitiesTransacted,
      security_name: item.securityName,
      price: item.price,
      form_type: item.formType,
      link: item.link,
      _source: 'FMP',
    }));

    return {
      trades,
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP insider trading error:', error);
    return null;
  }
}

/**
 * Fetch key metrics (TTM) from FMP.
 */
export async function getFmpKeyMetricsTTM(ticker: string): Promise<{
  metrics: Record<string, unknown>;
  source: string;
} | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const url = `${FMP_BASE_URL}/key-metrics-ttm?symbol=${ticker}&apikey=${apiKey}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MazoAgent/1.0)',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP key metrics TTM failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    if (!data || !Array.isArray(data) || data.length === 0) {
      return null;
    }

    return {
      metrics: {
        ...data[0],
        _source: 'FMP',
      },
      source: 'FMP',
    };
  } catch (error) {
    console.error('FMP key metrics TTM error:', error);
    return null;
  }
}

/**
 * Check if FMP fallback should be used.
 */
export function shouldUseFmpFallback(dataType: 'prices' | 'metrics' | 'news' | 'financials' | 'all' = 'all'): boolean {
  // Check if FMP API key is available
  if (!getFmpApiKey()) {
    return false;
  }
  
  const envTrue = (key: string, defaultVal: boolean = true): boolean => {
    const val = process.env[key];
    if (val === undefined || val === '') return defaultVal;
    return val.toLowerCase() === 'true';
  };

  // Check master switch
  if (!envTrue('USE_FMP_FALLBACK', true)) {
    return false;
  }
  
  // Check specific data type
  switch (dataType) {
    case 'prices':
      return envTrue('FMP_FOR_PRICES', true);
    case 'metrics':
      return envTrue('FMP_FOR_METRICS', true);
    case 'news':
      return envTrue('FMP_FOR_NEWS', true);
    case 'financials':
      return envTrue('FMP_FOR_FINANCIALS', true);
    default:
      return true;
  }
}


// =============================================================================
// FMP Ultimate Data Functions
// =============================================================================
// These functions provide access to the full FMP Ultimate data catalog.
// Each module can be toggled via environment variables (FMP_MODULE_*).

/**
 * Check if an FMP module is enabled.
 */
function isModuleEnabled(module: string): boolean {
  const envVar = `FMP_MODULE_${module.toUpperCase()}`;
  const val = process.env[envVar];
  return val === undefined || val === '' || val.toLowerCase() === 'true';
}

/**
 * Generic FMP API call helper.
 */
async function fmpRequest<T>(endpoint: string, params: Record<string, string> = {}): Promise<T | null> {
  const apiKey = getFmpApiKey();
  if (!apiKey) {
    console.log('FMP API key not configured');
    return null;
  }

  try {
    const queryParams = new URLSearchParams({ ...params, apikey: apiKey });
    const url = `${FMP_BASE_URL}/${endpoint}?${queryParams}`;
    
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`FMP ${endpoint} failed: ${response.status}`);
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error(`FMP ${endpoint} error:`, error);
    return null;
  }
}

// ---- Company Data ----

export interface CompanyProfile {
  symbol: string;
  companyName: string;
  sector: string;
  industry: string;
  description: string;
  ceo?: string;
  website?: string;
  country?: string;
  mktCap?: number;
  fullTimeEmployees?: number;
  ipoDate?: string;
}

/**
 * Get full company profile.
 */
export async function getFmpCompanyProfile(ticker: string): Promise<CompanyProfile | null> {
  if (!isModuleEnabled('FUNDAMENTALS')) return null;
  
  const data = await fmpRequest<CompanyProfile[]>('profile', { symbol: ticker });
  return data && data.length > 0 ? data[0] : null;
}

/**
 * Get company peer list.
 */
export async function getFmpCompanyPeers(ticker: string): Promise<string[]> {
  if (!isModuleEnabled('FUNDAMENTALS')) return [];
  
  const data = await fmpRequest<Array<{ peersList: string[] }>>('stock_peers', { symbol: ticker });
  return data && data.length > 0 ? data[0].peersList || [] : [];
}

// ---- Analyst Data ----

export interface AnalystEstimate {
  symbol: string;
  date: string;
  estimatedEpsAvg?: number;
  estimatedRevenueAvg?: number;
  numberAnalystsEstimatedEps?: number;
  numberAnalystsEstimatedRevenue?: number;
}

/**
 * Get analyst estimates.
 */
export async function getFmpAnalystEstimates(ticker: string, period: string = 'annual', limit: number = 4): Promise<AnalystEstimate[]> {
  if (!isModuleEnabled('ANALYSTS')) return [];
  
  const data = await fmpRequest<AnalystEstimate[]>('analyst-estimates', { 
    symbol: ticker, 
    period, 
    limit: String(limit) 
  });
  return data || [];
}

export interface PriceTarget {
  symbol: string;
  publishedDate: string;
  analystName?: string;
  analystCompany?: string;
  priceTarget?: number;
  priceWhenPosted?: number;
}

/**
 * Get analyst price targets.
 */
export async function getFmpPriceTargets(ticker: string, limit: number = 10): Promise<PriceTarget[]> {
  if (!isModuleEnabled('ANALYSTS')) return [];
  
  const data = await fmpRequest<PriceTarget[]>('price-target', { symbol: ticker });
  return (data || []).slice(0, limit);
}

/**
 * Get consensus price target.
 */
export async function getFmpPriceTargetConsensus(ticker: string): Promise<Record<string, unknown> | null> {
  if (!isModuleEnabled('ANALYSTS')) return null;
  
  const data = await fmpRequest<Record<string, unknown>[]>('price-target-consensus', { symbol: ticker });
  return data && data.length > 0 ? data[0] : null;
}

export interface StockGrade {
  symbol: string;
  date: string;
  gradingCompany: string;
  previousGrade?: string;
  newGrade?: string;
  action?: string;
}

/**
 * Get stock upgrade/downgrade history.
 */
export async function getFmpStockGrades(ticker: string, limit: number = 10): Promise<StockGrade[]> {
  if (!isModuleEnabled('ANALYSTS')) return [];
  
  const data = await fmpRequest<StockGrade[]>('grade', { symbol: ticker, limit: String(limit) });
  return data || [];
}

// ---- Insider & Institutional Data ----

export interface InsiderTrade {
  symbol: string;
  filingDate: string;
  transactionDate?: string;
  reportingName: string;
  transactionType: string;
  securitiesTransacted?: number;
  price?: number;
}

/**
 * Get insider trading activity.
 */
export async function getFmpInsiderTrades(ticker: string, limit: number = 50): Promise<InsiderTrade[]> {
  if (!isModuleEnabled('INSIDER')) return [];
  
  const data = await fmpRequest<InsiderTrade[]>('insider-trading', { symbol: ticker, limit: String(limit) });
  return data || [];
}

/**
 * Get institutional holders.
 */
export async function getFmpInstitutionalHolders(ticker: string): Promise<Record<string, unknown>[]> {
  if (!isModuleEnabled('FILINGS')) return [];
  
  const data = await fmpRequest<Record<string, unknown>[]>('institutional-holder', { symbol: ticker });
  return data || [];
}

// ---- Calendar Data ----

export interface EarningsEvent {
  symbol: string;
  date: string;
  epsEstimated?: number;
  eps?: number;
  revenueEstimated?: number;
  revenue?: number;
  time?: string;
}

/**
 * Get earnings calendar.
 */
export async function getFmpEarningsCalendar(fromDate?: string, toDate?: string): Promise<EarningsEvent[]> {
  if (!isModuleEnabled('CALENDAR')) return [];
  
  const params: Record<string, string> = {};
  if (fromDate) params.from = fromDate;
  if (toDate) params.to = toDate;
  
  const data = await fmpRequest<EarningsEvent[]>('earning_calendar', params);
  return data || [];
}

/**
 * Get economic calendar.
 */
export async function getFmpEconomicCalendar(fromDate?: string, toDate?: string): Promise<Record<string, unknown>[]> {
  if (!isModuleEnabled('CALENDAR')) return [];
  
  const params: Record<string, string> = {};
  if (fromDate) params.from = fromDate;
  if (toDate) params.to = toDate;
  
  const data = await fmpRequest<Record<string, unknown>[]>('economic_calendar', params);
  return data || [];
}

// ---- Market Data ----

export interface SectorPerformance {
  sector: string;
  changesPercentage: number;
}

/**
 * Get sector performance.
 */
export async function getFmpSectorPerformance(): Promise<SectorPerformance[]> {
  if (!isModuleEnabled('MARKET')) return [];
  
  const data = await fmpRequest<SectorPerformance[]>('sector-performance', {});
  return data || [];
}

export interface MarketMover {
  symbol: string;
  name: string;
  change: number;
  changesPercentage: number;
  price: number;
}

/**
 * Get market movers (gainers, losers, actives).
 */
export async function getFmpMarketMovers(type: 'gainers' | 'losers' | 'actives' = 'gainers', limit: number = 10): Promise<MarketMover[]> {
  if (!isModuleEnabled('MARKET')) return [];
  
  const data = await fmpRequest<MarketMover[]>(`stock_market/${type}`, {});
  return (data || []).slice(0, limit);
}

// ---- Non-Equity Markets ----

export interface CommodityQuote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changesPercentage: number;
}

/**
 * Get commodity quotes.
 */
export async function getFmpCommodityQuotes(): Promise<CommodityQuote[]> {
  if (!isModuleEnabled('COMMODITIES')) return [];
  
  const data = await fmpRequest<CommodityQuote[]>('quote/commodity', {});
  return data || [];
}

export interface CryptoQuote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changesPercentage: number;
  marketCap?: number;
}

/**
 * Get cryptocurrency quotes.
 */
export async function getFmpCryptoQuotes(limit: number = 20): Promise<CryptoQuote[]> {
  if (!isModuleEnabled('CRYPTO')) return [];
  
  const data = await fmpRequest<CryptoQuote[]>('quote/crypto', {});
  return (data || []).slice(0, limit);
}

// ---- ESG Data ----

export interface ESGScore {
  symbol: string;
  date: string;
  environmentScore?: number;
  socialScore?: number;
  governanceScore?: number;
  ESGScore?: number;
  ESGRating?: string;
}

/**
 * Get ESG score.
 */
export async function getFmpEsgScore(ticker: string): Promise<ESGScore | null> {
  if (!isModuleEnabled('ESG')) return null;
  
  const data = await fmpRequest<ESGScore[]>('esg-environmental-social-governance-data', { symbol: ticker });
  return data && data.length > 0 ? data[0] : null;
}

// ---- Module Status ----

/**
 * Get status of all FMP modules.
 */
export function getFmpModuleStatus(): Record<string, boolean> {
  const modules = [
    'FUNDAMENTALS', 'ANALYSTS', 'FILINGS', 'INSIDER', 
    'CALENDAR', 'MACRO', 'MARKET', 'ETF', 
    'COMMODITIES', 'FOREX', 'CRYPTO', 'ESG'
  ];
  
  const status: Record<string, boolean> = {};
  for (const mod of modules) {
    status[mod.toLowerCase()] = isModuleEnabled(mod);
  }
  return status;
}
