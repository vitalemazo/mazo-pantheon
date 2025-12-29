/**
 * Yahoo Finance fallback for when Financial Datasets API fails.
 * Uses Yahoo Finance's public API endpoints.
 */

interface YahooQuote {
  symbol: string;
  regularMarketPrice: number;
  regularMarketOpen: number;
  regularMarketDayHigh: number;
  regularMarketDayLow: number;
  regularMarketVolume: number;
  regularMarketPreviousClose: number;
  regularMarketChange: number;
  regularMarketChangePercent: number;
  marketCap?: number;
  trailingPE?: number;
  forwardPE?: number;
  priceToBook?: number;
  fiftyTwoWeekHigh?: number;
  fiftyTwoWeekLow?: number;
}

interface YahooHistoricalPrice {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  adjclose: number;
}

/**
 * Fetch current price snapshot from Yahoo Finance using the chart endpoint.
 * The chart endpoint is more reliable than the quote endpoint.
 */
export async function getYahooPriceSnapshot(ticker: string): Promise<{
  snapshot: Record<string, unknown>;
  source: string;
} | null> {
  try {
    // Use the chart endpoint which is more reliable
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?interval=1d&range=1d`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`Yahoo Finance chart failed: ${response.status}`);
      return null;
    }

    const data = await response.json();
    const result = data.chart?.result?.[0];

    if (!result) {
      return null;
    }

    const meta = result.meta || {};
    const quote = result.indicators?.quote?.[0] || {};
    const lastIndex = (result.timestamp?.length || 1) - 1;

    return {
      snapshot: {
        ticker: meta.symbol,
        price: meta.regularMarketPrice,
        open: quote.open?.[lastIndex] ?? meta.chartPreviousClose,
        high: quote.high?.[lastIndex] ?? meta.regularMarketDayHigh,
        low: quote.low?.[lastIndex] ?? meta.regularMarketDayLow,
        close: quote.close?.[lastIndex] ?? meta.regularMarketPrice,
        previous_close: meta.chartPreviousClose,
        volume: quote.volume?.[lastIndex] ?? meta.regularMarketVolume,
        currency: meta.currency,
        exchange: meta.exchangeName,
        fifty_two_week_high: meta.fiftyTwoWeekHigh,
        fifty_two_week_low: meta.fiftyTwoWeekLow,
        _source: 'Yahoo Finance (fallback)',
      },
      source: 'Yahoo Finance',
    };
  } catch (error) {
    console.error('Yahoo Finance price snapshot error:', error);
    return null;
  }
}

/**
 * Fetch historical prices from Yahoo Finance.
 */
export async function getYahooHistoricalPrices(
  ticker: string,
  startDate: string,
  endDate: string
): Promise<{
  prices: Record<string, unknown>[];
  source: string;
} | null> {
  try {
    // Convert dates to Unix timestamps
    const start = Math.floor(new Date(startDate).getTime() / 1000);
    const end = Math.floor(new Date(endDate).getTime() / 1000);

    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?period1=${start}&period2=${end}&interval=1d`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      },
    });

    if (!response.ok) {
      console.error(`Yahoo Finance chart failed: ${response.status}`);
      return null;
    }

    const data = await response.json();
    const result = data.chart?.result?.[0];

    if (!result || !result.timestamp) {
      return null;
    }

    const timestamps = result.timestamp;
    const quote = result.indicators?.quote?.[0];
    const adjclose = result.indicators?.adjclose?.[0]?.adjclose;

    if (!quote) {
      return null;
    }

    const prices = timestamps.map((ts: number, i: number) => ({
      time: new Date(ts * 1000).toISOString().split('T')[0],
      open: quote.open?.[i] ?? null,
      high: quote.high?.[i] ?? null,
      low: quote.low?.[i] ?? null,
      close: quote.close?.[i] ?? null,
      volume: quote.volume?.[i] ?? null,
      adjusted_close: adjclose?.[i] ?? null,
      _source: 'Yahoo Finance (fallback)',
    })).filter((p: Record<string, unknown>) => p.close !== null);

    return {
      prices,
      source: 'Yahoo Finance',
    };
  } catch (error) {
    console.error('Yahoo Finance historical prices error:', error);
    return null;
  }
}

/**
 * Fetch basic financial metrics from Yahoo Finance.
 * Uses the chart endpoint's meta data for basic metrics.
 */
export async function getYahooFinancialMetrics(ticker: string): Promise<{
  metrics: Record<string, unknown>;
  source: string;
} | null> {
  try {
    // Use the chart endpoint which includes some key metrics in meta
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?interval=1d&range=1mo`;
    
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      console.error(`Yahoo Finance metrics (chart) failed: ${response.status}`);
      return null;
    }

    const data = await response.json();
    const result = data.chart?.result?.[0];

    if (!result) {
      return null;
    }

    const meta = result.meta || {};
    
    // Calculate some basic metrics from price data
    const closes = result.indicators?.quote?.[0]?.close || [];
    const validCloses = closes.filter((c: number | null) => c !== null);
    const avgPrice = validCloses.length > 0 
      ? validCloses.reduce((a: number, b: number) => a + b, 0) / validCloses.length 
      : null;
    
    // Calculate price change over period
    const firstClose = validCloses[0];
    const lastClose = validCloses[validCloses.length - 1];
    const priceChange = firstClose && lastClose ? ((lastClose - firstClose) / firstClose) * 100 : null;

    return {
      metrics: {
        ticker,
        current_price: meta.regularMarketPrice,
        previous_close: meta.chartPreviousClose,
        currency: meta.currency,
        exchange: meta.exchangeName,
        fifty_two_week_high: meta.fiftyTwoWeekHigh,
        fifty_two_week_low: meta.fiftyTwoWeekLow,
        fifty_day_average: meta.fiftyDayAverage,
        two_hundred_day_average: meta.twoHundredDayAverage,
        average_price_1mo: avgPrice,
        price_change_1mo_pct: priceChange,
        regular_market_volume: meta.regularMarketVolume,
        _source: 'Yahoo Finance (fallback)',
        _report_period: new Date().toISOString().split('T')[0],
        _note: 'Limited metrics available from Yahoo Finance fallback. For complete financial metrics, ensure Financial Datasets API is working.',
      },
      source: 'Yahoo Finance',
    };
  } catch (error) {
    console.error('Yahoo Finance metrics error:', error);
    return null;
  }
}

/**
 * Fetch news from Yahoo Finance.
 */
export async function getYahooNews(ticker: string, limit: number = 10): Promise<{
  news: Record<string, unknown>[];
  source: string;
} | null> {
  try {
    const url = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${ticker}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      },
    });

    // Yahoo's quote endpoint doesn't include news directly
    // We need to use a different approach - the search endpoint
    const searchUrl = `https://query1.finance.yahoo.com/v1/finance/search?q=${ticker}&newsCount=${limit}`;
    const searchResponse = await fetch(searchUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      },
    });

    if (!searchResponse.ok) {
      console.error(`Yahoo Finance news failed: ${searchResponse.status}`);
      return null;
    }

    const data = await searchResponse.json();
    const newsItems = data.news || [];

    const news = newsItems.slice(0, limit).map((item: Record<string, unknown>) => ({
      title: item.title,
      url: item.link,
      source: item.publisher,
      date: item.providerPublishTime 
        ? new Date((item.providerPublishTime as number) * 1000).toISOString()
        : null,
      thumbnail: (item.thumbnail as Record<string, unknown>)?.resolutions?.[0]?.url,
      _source: 'Yahoo Finance (fallback)',
    }));

    return {
      news,
      source: 'Yahoo Finance',
    };
  } catch (error) {
    console.error('Yahoo Finance news error:', error);
    return null;
  }
}
