import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, TrendingUp, Loader2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { API_BASE_URL } from '@/lib/api-config';

interface Asset {
  symbol: string;
  name: string;
  exchange?: string;
  asset_class?: string;
  fractionable?: boolean;
  shortable?: boolean;
}

interface TickerSearchProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

export function TickerSearch({
  value,
  onChange,
  placeholder = "Search tickers (e.g., AAPL, MSFT)",
  className,
  disabled = false,
}: TickerSearchProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [popularTickers, setPopularTickers] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alpacaConnected, setAlpacaConnected] = useState<boolean | null>(null);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Parse current tickers from value
  const currentTickers = value.split(',').map(t => t.trim()).filter(Boolean);

  // Check Alpaca connection status
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/alpaca/status`);
        if (response.ok) {
          const data = await response.json();
          setAlpacaConnected(data.connected);
        }
      } catch {
        setAlpacaConnected(false);
      }
    };
    checkStatus();
  }, []);

  // Load popular tickers on mount
  useEffect(() => {
    const loadPopular = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/alpaca/popular`);
        if (response.ok) {
          const data = await response.json();
          setPopularTickers(data.tickers);
        }
      } catch (e) {
        console.error('Failed to load popular tickers:', e);
      }
    };
    loadPopular();
  }, []);

  // Search assets with debounce
  const searchAssets = useCallback(async (query: string) => {
    if (!query || query.length < 1) {
      setAssets([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/alpaca/assets?search=${encodeURIComponent(query)}&limit=20`
      );
      
      if (response.ok) {
        const data = await response.json();
        setAssets(data.assets);
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Search failed' }));
        setError(errorData.detail);
        setAssets([]);
      }
    } catch (e) {
      setError('Failed to connect to backend');
      setAssets([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (search.length >= 1) {
      debounceRef.current = setTimeout(() => {
        searchAssets(search);
      }, 300);
    } else {
      setAssets([]);
    }

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [search, searchAssets]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const addTicker = (symbol: string) => {
    const upperSymbol = symbol.toUpperCase();
    if (!currentTickers.includes(upperSymbol)) {
      const newTickers = [...currentTickers, upperSymbol];
      onChange(newTickers.join(', '));
    }
    setSearch('');
    setAssets([]);
    inputRef.current?.focus();
  };

  const removeTicker = (symbol: string) => {
    const newTickers = currentTickers.filter(t => t !== symbol);
    onChange(newTickers.join(', '));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && search.trim()) {
      e.preventDefault();
      // Add the search term as a ticker directly
      addTicker(search.trim());
    } else if (e.key === 'Backspace' && !search && currentTickers.length > 0) {
      // Remove last ticker on backspace if search is empty
      removeTicker(currentTickers[currentTickers.length - 1]);
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  const displayResults = search.length >= 1 ? assets : popularTickers;
  const showResults = isOpen && (displayResults.length > 0 || loading || error);

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Input area with tags */}
      <div
        className={cn(
          "flex flex-wrap items-center gap-1.5 p-2 rounded-md border border-border bg-background",
          "focus-within:ring-2 focus-within:ring-primary/50 focus-within:border-primary",
          disabled && "opacity-50 cursor-not-allowed"
        )}
        onClick={() => !disabled && inputRef.current?.focus()}
      >
        <Search className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        
        {/* Selected ticker tags */}
        {currentTickers.map((ticker) => (
          <span
            key={ticker}
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/10 text-primary text-xs font-medium rounded"
          >
            {ticker}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                removeTicker(ticker);
              }}
              className="hover:bg-primary/20 rounded p-0.5"
              disabled={disabled}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        
        {/* Search input */}
        <input
          ref={inputRef}
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={currentTickers.length === 0 ? placeholder : "Add more..."}
          className="flex-1 min-w-[120px] bg-transparent border-none outline-none text-sm text-primary placeholder:text-muted-foreground"
          disabled={disabled}
        />
        
        {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      {/* Alpaca connection status */}
      {alpacaConnected === false && (
        <div className="mt-1 flex items-center gap-1 text-xs text-amber-500">
          <AlertCircle className="h-3 w-3" />
          <span>Alpaca not connected - using manual entry only</span>
        </div>
      )}

      {/* Dropdown results */}
      {showResults && (
        <div className="absolute z-50 w-full mt-1 bg-panel border border-border rounded-md shadow-lg max-h-72 overflow-auto">
          {/* Section header */}
          <div className="sticky top-0 bg-panel border-b border-border px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-2">
            {search.length >= 1 ? (
              <>
                <Search className="h-3 w-3" />
                Search Results
              </>
            ) : (
              <>
                <TrendingUp className="h-3 w-3" />
                Popular Tickers
              </>
            )}
          </div>

          {error && (
            <div className="px-3 py-2 text-sm text-red-500 flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}

          {loading && !error && (
            <div className="px-3 py-4 text-center text-sm text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin mx-auto mb-1" />
              Searching...
            </div>
          )}

          {!loading && !error && displayResults.length === 0 && search.length >= 1 && (
            <div className="px-3 py-4 text-center text-sm text-muted-foreground">
              No assets found for "{search}"
              <div className="mt-1 text-xs">
                Press Enter to add "{search.toUpperCase()}" anyway
              </div>
            </div>
          )}

          {!loading && !error && displayResults.map((asset) => {
            const isSelected = currentTickers.includes(asset.symbol);
            return (
              <button
                key={asset.symbol}
                type="button"
                onClick={() => addTicker(asset.symbol)}
                disabled={isSelected}
                className={cn(
                  "w-full px-3 py-2 text-left hover:bg-muted/50 transition-colors flex items-center justify-between",
                  isSelected && "opacity-50 cursor-not-allowed bg-muted/30"
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-primary">{asset.symbol}</span>
                    {asset.exchange && (
                      <span className="text-[10px] text-muted-foreground bg-muted px-1 py-0.5 rounded">
                        {asset.exchange}
                      </span>
                    )}
                    {isSelected && (
                      <span className="text-[10px] text-green-500 bg-green-500/10 px-1 py-0.5 rounded">
                        Added
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {asset.name}
                  </div>
                </div>
                {asset.fractionable && (
                  <span className="text-[10px] text-muted-foreground ml-2">Fractional</span>
                )}
              </button>
            );
          })}

          {/* Help text */}
          <div className="sticky bottom-0 bg-panel border-t border-border px-3 py-1.5 text-[10px] text-muted-foreground">
            Type to search • Enter to add • Click to select • Backspace to remove
          </div>
        </div>
      )}
    </div>
  );
}
