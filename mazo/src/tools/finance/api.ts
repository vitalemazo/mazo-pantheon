const BASE_URL = 'https://api.financialdatasets.ai';

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

export async function callApi(
  endpoint: string,
  params: Record<string, string | number | string[] | undefined>
): Promise<ApiResponse> {
  // Read API key lazily at call time (after dotenv has loaded)
  const FINANCIAL_DATASETS_API_KEY = process.env.FINANCIAL_DATASETS_API_KEY;
  const url = new URL(`${BASE_URL}${endpoint}`);

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
    // Record the error
    recordError({
      status: response.status,
      statusText: response.statusText,
      endpoint,
      ticker: params.ticker as string | undefined,
    });
    
    // Provide more detailed error messages
    let errorMessage = `API request failed: ${response.status} ${response.statusText}`;
    
    if (response.status === 402) {
      errorMessage = `API credits exhausted (402). The Financial Datasets API requires credits for this request. Ticker: ${params.ticker || 'unknown'}`;
    } else if (response.status === 429) {
      errorMessage = `Rate limited (429). Too many requests to Financial Datasets API.`;
    } else if (response.status === 404) {
      errorMessage = `Data not found (404) for ticker: ${params.ticker || 'unknown'}`;
    }
    
    throw new Error(errorMessage);
  }

  const data = await response.json();
  return { data, url: url.toString(), source: 'Financial Datasets API' };
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
 * Call API with Yahoo Finance and FMP fallbacks.
 * If the primary API fails, tries Yahoo Finance first, then FMP as backups.
 * Respects fallback settings from environment variables.
 */
export async function callApiWithFallback<T>(
  primaryCall: () => Promise<ApiResponse>,
  yahooFallbackCall: () => Promise<{ data: T; source: string } | null>,
  fmpFallbackCall: (() => Promise<{ data: T; source: string } | null>) | null,
  endpoint: string,
  dataType: 'prices' | 'metrics' | 'news' = 'prices'
): Promise<ApiResponse> {
  try {
    return await primaryCall();
  } catch (primaryError) {
    // Try Yahoo Finance first (free, no API key required)
    if (shouldUseYahooFallback(dataType)) {
      console.log(`Primary API failed for ${endpoint}, trying Yahoo Finance fallback...`);
      
      try {
        const yahooResult = await yahooFallbackCall();
        
        if (yahooResult) {
          console.log(`Yahoo Finance fallback succeeded for ${endpoint}`);
          return {
            data: yahooResult.data as Record<string, unknown>,
            url: `yahoo-finance://${endpoint}`,
            source: yahooResult.source,
          };
        }
      } catch (yahooError) {
        console.error(`Yahoo Finance fallback failed for ${endpoint}:`, yahooError);
      }
    }
    
    // Try FMP second (requires API key)
    if (fmpFallbackCall && shouldUseFmpFallback(dataType)) {
      console.log(`Yahoo Finance failed, trying FMP fallback for ${endpoint}...`);
      
      try {
        const fmpResult = await fmpFallbackCall();
        
        if (fmpResult) {
          console.log(`FMP fallback succeeded for ${endpoint}`);
          return {
            data: fmpResult.data as Record<string, unknown>,
            url: `fmp://${endpoint}`,
            source: fmpResult.source,
          };
        }
      } catch (fmpError) {
        console.error(`FMP fallback also failed for ${endpoint}:`, fmpError);
      }
    }
    
    // Re-throw the original error if all fallbacks failed
    throw primaryError;
  }
}
