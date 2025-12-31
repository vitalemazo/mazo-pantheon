/**
 * Multi-source API client for financial data.
 * 
 * Primary data source routing (based on PRIMARY_DATA_SOURCE env var):
 * - fmp: FMP Ultimate first (recommended), fallback to Financial Datasets/Yahoo
 * - alpaca: Alpaca Market Data first, fallback to FMP/Yahoo
 * - financial_datasets: Financial Datasets API first (legacy default)
 */

const FINANCIAL_DATASETS_BASE_URL = 'https://api.financialdatasets.ai';
const FMP_BASE_URL = 'https://financialmodelingprep.com/stable';

export interface ApiResponse {
  data: Record<string, unknown>;
  url: string;
  source?: string;
}

export interface ApiError {
  status: number;
  statusText: string;
  endpoint: string;
  ticker?: string;
}

// Track API errors for monitoring
const recentErrors: ApiError[] = [];
const MAX_ERRORS = 50;

export function getRecentApiErrors(): ApiError[] {
  return [...recentErrors];
}

function recordError(error: ApiError): void {
  recentErrors.push(error);
  if (recentErrors.length > MAX_ERRORS) {
    recentErrors.shift();
  }
}

/**
 * Get fallback settings from environment variables.
 * These are synced from the database by the backend.
 * 
 * Default primary data source is now FMP (Financial Modeling Prep).
 */
export function getFallbackSettings(): {
  useYahooFinanceFallback: boolean;
  yahooFinanceForPrices: boolean;
  yahooFinanceForMetrics: boolean;
  yahooFinanceForNews: boolean;
  primaryDataSource: string;
  isFmpPrimary: boolean;
  isAlpacaPrimary: boolean;
} {
  const envTrue = (key: string, defaultVal: boolean = true): boolean => {
    const val = process.env[key];
    if (val === undefined || val === '') return defaultVal;
    return val.toLowerCase() === 'true';
  };

  // Default to FMP as primary data source
  const primaryDataSource = process.env.PRIMARY_DATA_SOURCE || 'fmp';

  return {
    useYahooFinanceFallback: envTrue('USE_YAHOO_FINANCE_FALLBACK', true),
    yahooFinanceForPrices: envTrue('YAHOO_FINANCE_FOR_PRICES', true),
    yahooFinanceForMetrics: envTrue('YAHOO_FINANCE_FOR_METRICS', true),
    yahooFinanceForNews: envTrue('YAHOO_FINANCE_FOR_NEWS', true),
    primaryDataSource,
    isFmpPrimary: primaryDataSource === 'fmp',
    isAlpacaPrimary: primaryDataSource === 'alpaca',
  };
}

/**
 * Check if FMP is the primary data source.
 * When FMP is primary, all data types (prices, fundamentals, news) come from FMP first.
 */
export function isFmpPrimary(): boolean {
  return getFallbackSettings().isFmpPrimary;
}

/**
 * Check if Alpaca is the primary data source.
 * When Alpaca is primary, prices and news will be fetched from Alpaca first.
 * Note: Alpaca does NOT provide fundamentals, so those always fall back to other sources.
 */
export function isAlpacaPrimary(): boolean {
  return getFallbackSettings().isAlpacaPrimary;
}

/**
 * Get data source info for logging/debugging.
 */
export function getDataSourceInfo(): {
  primary: string;
  fmpEnabled: boolean;
  alpacaEnabled: boolean;
  yahooFallbackEnabled: boolean;
  fmpFallbackEnabled: boolean;
} {
  const settings = getFallbackSettings();
  return {
    primary: settings.primaryDataSource,
    fmpEnabled: settings.isFmpPrimary,
    alpacaEnabled: settings.isAlpacaPrimary,
    yahooFallbackEnabled: settings.useYahooFinanceFallback,
    fmpFallbackEnabled: shouldUseFmpFallback('all'),
  };
}

/**
 * Check if Yahoo Finance fallback should be used for a specific data type.
 */
export function shouldUseYahooFallback(dataType: 'prices' | 'metrics' | 'news' | 'all' = 'all'): boolean {
  const settings = getFallbackSettings();
  
  // Master switch must be enabled
  if (!settings.useYahooFinanceFallback) {
    return false;
  }
  
  // Check specific data type
  switch (dataType) {
    case 'prices':
      return settings.yahooFinanceForPrices;
    case 'metrics':
      return settings.yahooFinanceForMetrics;
    case 'news':
      return settings.yahooFinanceForNews;
    default:
      return true;
  }
}

/**
 * Make API call to Financial Datasets API (legacy/fallback).
 */
async function callFinancialDatasetsApi(
  endpoint: string,
  params: Record<string, string | number | string[] | undefined>
): Promise<ApiResponse> {
  const FINANCIAL_DATASETS_API_KEY = process.env.FINANCIAL_DATASETS_API_KEY;
  const url = new URL(`${FINANCIAL_DATASETS_BASE_URL}${endpoint}`);

  // Add params to URL, handling arrays
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      if (Array.isArray(value)) {
        value.forEach((v) => url.searchParams.append(key, v));
      } else {
        url.searchParams.append(key, String(value));
      }
    }
  }

  const response = await fetch(url.toString(), {
    headers: {
      'x-api-key': FINANCIAL_DATASETS_API_KEY || '',
    },
  });

  if (!response.ok) {
    recordError({
      status: response.status,
      statusText: response.statusText,
      endpoint,
      ticker: params.ticker as string | undefined,
    });
    
    let errorMessage = `API request failed: ${response.status} ${response.statusText}`;
    
    if (response.status === 402) {
      errorMessage = `API credits exhausted (402). Financial Datasets API. Ticker: ${params.ticker || 'unknown'}`;
    } else if (response.status === 429) {
      errorMessage = `Rate limited (429). Financial Datasets API.`;
    } else if (response.status === 404) {
      errorMessage = `Data not found (404) for ticker: ${params.ticker || 'unknown'}`;
    }
    
    throw new Error(errorMessage);
  }

  const data = await response.json();
  return { data, url: url.toString(), source: 'Financial Datasets API' };
}

/**
 * Make API call to FMP (Financial Modeling Prep) API.
 */
async function callFmpApi(
  endpoint: string,
  params: Record<string, string | number | string[] | undefined>
): Promise<ApiResponse> {
  const FMP_API_KEY = process.env.FMP_API_KEY;
  if (!FMP_API_KEY) {
    throw new Error('FMP_API_KEY not configured');
  }

  const url = new URL(`${FMP_BASE_URL}${endpoint}`);
  
  // Add params to URL
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      if (Array.isArray(value)) {
        value.forEach((v) => url.searchParams.append(key, v));
      } else {
        url.searchParams.append(key, String(value));
      }
    }
  }
  
  // Add API key
  url.searchParams.append('apikey', FMP_API_KEY);

  const response = await fetch(url.toString(), {
    headers: {
      'User-Agent': 'Mozilla/5.0 (compatible; MazoAgent/1.0)',
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    recordError({
      status: response.status,
      statusText: response.statusText,
      endpoint,
      ticker: params.ticker as string | undefined || params.symbol as string | undefined,
    });
    
    let errorMessage = `FMP API request failed: ${response.status} ${response.statusText}`;
    
    if (response.status === 401) {
      errorMessage = `FMP API key invalid or expired (401)`;
    } else if (response.status === 429) {
      errorMessage = `Rate limited (429). FMP API.`;
    } else if (response.status === 403) {
      errorMessage = `FMP API access denied - check subscription (403)`;
    }
    
    throw new Error(errorMessage);
  }

  const data = await response.json();
  return { data, url: url.toString(), source: 'FMP' };
}

/**
 * Main API call function - routes to the appropriate data source.
 * 
 * When PRIMARY_DATA_SOURCE=fmp, calls FMP first.
 * When PRIMARY_DATA_SOURCE=financial_datasets (or unset), calls Financial Datasets first.
 * 
 * Note: This function handles generic endpoints. For specific data types
 * (prices, news, metrics), use the specialized functions in their modules
 * which handle the full fallback chain.
 */
export async function callApi(
  endpoint: string,
  params: Record<string, string | number | string[] | undefined>
): Promise<ApiResponse> {
  const settings = getFallbackSettings();
  
  // Route based on primary data source
  if (settings.isFmpPrimary) {
    // FMP is primary - try FMP first, fallback to Financial Datasets
    try {
      // Map Financial Datasets endpoints to FMP equivalents
      const fmpEndpoint = mapEndpointToFmp(endpoint);
      if (fmpEndpoint) {
        console.log(`[Mazo] Using FMP as primary for ${endpoint}`);
        return await callFmpApi(fmpEndpoint, params);
      }
    } catch (fmpError) {
      console.log(`[Mazo] FMP failed for ${endpoint}, falling back to Financial Datasets:`, fmpError);
    }
    
    // Fallback to Financial Datasets
    if (process.env.FINANCIAL_DATASETS_API_KEY) {
      return await callFinancialDatasetsApi(endpoint, params);
    }
    
    throw new Error(`No data source available for ${endpoint}`);
  }
  
  // Financial Datasets is primary (legacy behavior)
  return await callFinancialDatasetsApi(endpoint, params);
}

/**
 * Map Financial Datasets API endpoints to FMP equivalents.
 * Returns null if no mapping exists (will fall back to Financial Datasets).
 * 
 * FMP API Docs: https://financialmodelingprep.com/developer/docs
 */
function mapEndpointToFmp(endpoint: string): string | null {
  // ==========================================================================
  // Price endpoints
  // ==========================================================================
  if (endpoint.startsWith('/prices/snapshot/')) {
    return '/quote';
  }
  if (endpoint.startsWith('/prices/')) {
    return '/historical-price-eod/full';
  }
  
  // ==========================================================================
  // Financial metrics & ratios
  // ==========================================================================
  if (endpoint.startsWith('/financial-metrics/snapshot/')) {
    return '/key-metrics-ttm';
  }
  if (endpoint.startsWith('/financial-metrics/')) {
    return '/key-metrics';
  }
  
  // ==========================================================================
  // Company profile
  // ==========================================================================
  if (endpoint.startsWith('/company/')) {
    return '/profile';
  }
  
  // ==========================================================================
  // News
  // ==========================================================================
  if (endpoint.startsWith('/news/')) {
    return '/stock-news';
  }
  
  // ==========================================================================
  // Insider trades
  // ==========================================================================
  if (endpoint.startsWith('/insider-trades/')) {
    return '/insider-trading';
  }
  
  // ==========================================================================
  // Financial statements (multiple path formats)
  // ==========================================================================
  if (endpoint.includes('/income-statements/') || endpoint.includes('/income-statement')) {
    return '/income-statement';
  }
  if (endpoint.includes('/balance-sheets/') || endpoint.includes('/balance-sheet')) {
    return '/balance-sheet-statement';
  }
  if (endpoint.includes('/cash-flow-statements/') || endpoint.includes('/cash-flow')) {
    return '/cash-flow-statement';
  }
  // General financials endpoint
  if (endpoint === '/financials/' || endpoint.startsWith('/financials/?')) {
    return '/financial-statement-full-as-reported';
  }
  
  // ==========================================================================
  // SEC Filings
  // ==========================================================================
  if (endpoint.startsWith('/filings/items/')) {
    // Line items map to financial statements - caller should use specific statement endpoints
    return '/income-statement';  // Default to income statement for line items
  }
  if (endpoint.startsWith('/filings/')) {
    return '/sec_filings';
  }
  
  // ==========================================================================
  // Analyst estimates & earnings
  // ==========================================================================
  if (endpoint.startsWith('/analyst-estimates/')) {
    return '/analyst-estimates';
  }
  
  // ==========================================================================
  // Segment revenues
  // ==========================================================================
  if (endpoint.startsWith('/financials/segmented-revenues/')) {
    return '/revenue-product-segmentation';
  }
  
  // ==========================================================================
  // Crypto prices
  // ==========================================================================
  if (endpoint.startsWith('/crypto/prices/snapshot/')) {
    return '/quote';  // FMP uses same quote endpoint for crypto with symbol like BTCUSD
  }
  if (endpoint.startsWith('/crypto/prices/tickers/')) {
    return '/symbol/available-cryptocurrencies';
  }
  if (endpoint.startsWith('/crypto/prices/')) {
    return '/historical-price-eod/full';  // Same endpoint, different symbol format
  }
  
  // ==========================================================================
  // No direct mapping - return null to fall back
  // ==========================================================================
  return null;
}

/**
 * Check if FMP fallback should be used for a specific data type.
 */
export function shouldUseFmpFallback(dataType: 'prices' | 'metrics' | 'news' | 'financials' | 'all' = 'all'): boolean {
  // Check if FMP API key is available
  if (!process.env.FMP_API_KEY) {
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

/**
 * Call API with intelligent source selection and fallbacks.
 * 
 * Source priority based on PRIMARY_DATA_SOURCE:
 * - fmp: FMP → Yahoo → Financial Datasets
 * - alpaca: Alpaca → FMP → Yahoo (for prices/news only)
 * - financial_datasets: Financial Datasets → Yahoo → FMP
 * 
 * @param financialDatasetsCall - Call to Financial Datasets API
 * @param yahooFallbackCall - Call to Yahoo Finance
 * @param fmpCall - Call to FMP API
 * @param endpoint - Endpoint name for logging
 * @param dataType - Type of data being fetched
 */
export async function callApiWithFallback<T>(
  financialDatasetsCall: () => Promise<ApiResponse>,
  yahooFallbackCall: () => Promise<{ data: T; source: string } | null>,
  fmpCall: (() => Promise<{ data: T; source: string } | null>) | null,
  endpoint: string,
  dataType: 'prices' | 'metrics' | 'news' = 'prices'
): Promise<ApiResponse> {
  const settings = getFallbackSettings();
  
  // When FMP is primary, try FMP first
  if (settings.isFmpPrimary && fmpCall) {
    console.log(`[Mazo] FMP is primary, trying FMP first for ${endpoint}`);
    
    try {
      const fmpResult = await fmpCall();
      if (fmpResult) {
        console.log(`[Mazo] FMP succeeded for ${endpoint}`);
        return {
          data: fmpResult.data as Record<string, unknown>,
          url: `fmp://${endpoint}`,
          source: fmpResult.source,
        };
      }
    } catch (fmpError) {
      console.log(`[Mazo] FMP failed for ${endpoint}, trying fallbacks:`, fmpError);
    }
    
    // FMP failed - try Yahoo as first fallback
    if (shouldUseYahooFallback(dataType)) {
      try {
        const yahooResult = await yahooFallbackCall();
        if (yahooResult) {
          console.log(`[Mazo] Yahoo Finance fallback succeeded for ${endpoint}`);
          return {
            data: yahooResult.data as Record<string, unknown>,
            url: `yahoo-finance://${endpoint}`,
            source: yahooResult.source,
          };
        }
      } catch (yahooError) {
        console.log(`[Mazo] Yahoo Finance fallback failed for ${endpoint}:`, yahooError);
      }
    }
    
    // Try Financial Datasets as last resort
    if (process.env.FINANCIAL_DATASETS_API_KEY) {
      try {
        return await financialDatasetsCall();
      } catch (fdError) {
        console.log(`[Mazo] Financial Datasets also failed for ${endpoint}:`, fdError);
      }
    }
    
    throw new Error(`All data sources failed for ${endpoint}`);
  }
  
  // Financial Datasets is primary (legacy behavior)
  try {
    return await financialDatasetsCall();
  } catch (primaryError) {
    // Try Yahoo Finance first (free, no API key required)
    if (shouldUseYahooFallback(dataType)) {
      console.log(`[Mazo] Primary API failed for ${endpoint}, trying Yahoo Finance...`);
      
      try {
        const yahooResult = await yahooFallbackCall();
        
        if (yahooResult) {
          console.log(`[Mazo] Yahoo Finance fallback succeeded for ${endpoint}`);
          return {
            data: yahooResult.data as Record<string, unknown>,
            url: `yahoo-finance://${endpoint}`,
            source: yahooResult.source,
          };
        }
      } catch (yahooError) {
        console.error(`[Mazo] Yahoo Finance fallback failed for ${endpoint}:`, yahooError);
      }
    }
    
    // Try FMP second (requires API key)
    if (fmpCall && shouldUseFmpFallback(dataType)) {
      console.log(`[Mazo] Trying FMP fallback for ${endpoint}...`);
      
      try {
        const fmpResult = await fmpCall();
        
        if (fmpResult) {
          console.log(`[Mazo] FMP fallback succeeded for ${endpoint}`);
          return {
            data: fmpResult.data as Record<string, unknown>,
            url: `fmp://${endpoint}`,
            source: fmpResult.source,
          };
        }
      } catch (fmpError) {
        console.error(`[Mazo] FMP fallback also failed for ${endpoint}:`, fmpError);
      }
    }
    
    // Re-throw the original error if all fallbacks failed
    throw primaryError;
  }
}
