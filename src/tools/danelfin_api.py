"""
Danelfin API Client for AI Stock Scoring.

Danelfin provides AI-powered stock analysis with 5 key metrics:
- AI Score (1-10): Overall AI-powered stock ranking
- Technical Score (1-10): Technical analysis rating
- Fundamental Score (1-10): Fundamental analysis rating
- Sentiment Score (1-10): Market sentiment analysis
- Low Risk Score (1-10): Risk assessment rating

API Documentation: https://danelfin.com/docs/api
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)

# Danelfin API configuration
DANELFIN_API_BASE = "https://apirest.danelfin.com"

# Cache for scores (ticker -> (timestamp, data))
_score_cache: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes


@dataclass
class DanelfinScore:
    """Danelfin AI score data for a ticker."""
    ticker: str
    date: str
    ai_score: int
    technical: int
    fundamental: int
    sentiment: int
    low_risk: int
    buy_track_record: Optional[bool] = None
    sell_track_record: Optional[bool] = None
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "date": self.date,
            "ai_score": self.ai_score,
            "technical": self.technical,
            "fundamental": self.fundamental,
            "sentiment": self.sentiment,
            "low_risk": self.low_risk,
            "buy_track_record": self.buy_track_record,
            "sell_track_record": self.sell_track_record,
            "success": self.success,
            "error": self.error,
        }

    @property
    def highest_score(self) -> tuple:
        """Return the highest score category and value."""
        scores = {
            "ai_score": self.ai_score,
            "technical": self.technical,
            "fundamental": self.fundamental,
            "sentiment": self.sentiment,
            "low_risk": self.low_risk,
        }
        max_category = max(scores, key=scores.get)
        return max_category, scores[max_category]

    @property
    def signal(self) -> str:
        """Derive a signal from the AI score."""
        if self.ai_score >= 8:
            return "strong_buy"
        elif self.ai_score >= 6:
            return "buy"
        elif self.ai_score >= 4:
            return "hold"
        elif self.ai_score >= 2:
            return "sell"
        else:
            return "strong_sell"


def get_danelfin_api_key() -> Optional[str]:
    """Get Danelfin API key from database or environment."""
    # Try database first (Settings UI)
    try:
        from sqlalchemy import create_engine, text
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://mazo:mazo@mazo-postgres:5432/mazo_pantheon"
        )
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT key_value FROM api_keys WHERE provider = 'DANELFIN_API_KEY' AND is_active = true")
            )
            row = result.fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        logger.debug(f"Could not fetch Danelfin key from DB: {e}")
    
    # Fall back to environment variable
    return os.environ.get("DANELFIN_API_KEY")


def _is_cache_valid(ticker: str) -> bool:
    """Check if cached data for ticker is still valid."""
    if ticker not in _score_cache:
        return False
    timestamp, _ = _score_cache[ticker]
    return (time.time() - timestamp) < CACHE_TTL_SECONDS


def _get_cached_score(ticker: str) -> Optional[DanelfinScore]:
    """Get cached score if valid."""
    if _is_cache_valid(ticker):
        _, data = _score_cache[ticker]
        return data
    return None


def _cache_score(ticker: str, score: DanelfinScore) -> None:
    """Cache a score result."""
    _score_cache[ticker] = (time.time(), score)


def test_connection() -> Dict[str, Any]:
    """
    Test Danelfin API connection.
    
    Returns:
        Dict with success status and connection info
    """
    api_key = get_danelfin_api_key()
    
    if not api_key:
        return {
            "success": False,
            "error": "Danelfin API key not configured. Add DANELFIN_API_KEY in Settings.",
            "configured": False,
        }
    
    try:
        headers = {"x-api-key": api_key}
        
        # Test with a simple request for AAPL (always available)
        response = requests.get(
            f"{DANELFIN_API_BASE}/ranking",
            params={"ticker": "AAPL"},
            headers=headers,
            timeout=15,
        )
        
        if response.status_code == 200:
            data = response.json()
            # Check if we got valid data
            if data and isinstance(data, dict):
                return {
                    "success": True,
                    "configured": True,
                    "message": "Danelfin API connected successfully",
                    "test_ticker": "AAPL",
                    "data_available": bool(data),
                }
            else:
                return {
                    "success": True,
                    "configured": True,
                    "message": "API connected but no data returned",
                }
        elif response.status_code == 403:
            return {
                "success": False,
                "error": "Invalid API key or insufficient permissions",
                "configured": True,
            }
        elif response.status_code == 429:
            return {
                "success": True,
                "configured": True,
                "message": "API key valid but rate limited. Wait and try again.",
            }
        else:
            return {
                "success": False,
                "error": f"API error: {response.status_code} - {response.text[:200]}",
                "configured": True,
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Connection timeout. Danelfin API may be slow.",
            "configured": True,
        }
    except Exception as e:
        logger.error(f"Danelfin test error: {e}")
        return {
            "success": False,
            "error": str(e),
            "configured": True,
        }


def get_score(ticker: str, use_cache: bool = True) -> DanelfinScore:
    """
    Get Danelfin AI scores for a ticker.
    
    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        use_cache: Whether to use cached results (default True)
    
    Returns:
        DanelfinScore with all 5 metrics
    """
    ticker = ticker.upper().strip()
    
    # Check cache first
    if use_cache:
        cached = _get_cached_score(ticker)
        if cached:
            logger.debug(f"[Danelfin] Cache hit for {ticker}")
            return cached
    
    api_key = get_danelfin_api_key()
    
    if not api_key:
        return DanelfinScore(
            ticker=ticker,
            date="",
            ai_score=0,
            technical=0,
            fundamental=0,
            sentiment=0,
            low_risk=0,
            success=False,
            error="Danelfin API key not configured",
        )
    
    try:
        headers = {"x-api-key": api_key}
        
        # Get latest scores for ticker
        response = requests.get(
            f"{DANELFIN_API_BASE}/ranking",
            params={"ticker": ticker},
            headers=headers,
            timeout=15,
        )
        
        if response.status_code != 200:
            error_msg = f"API error: {response.status_code}"
            logger.warning(f"[Danelfin] {error_msg} for {ticker}")
            return DanelfinScore(
                ticker=ticker,
                date="",
                ai_score=0,
                technical=0,
                fundamental=0,
                sentiment=0,
                low_risk=0,
                success=False,
                error=error_msg,
            )
        
        data = response.json()
        
        # Parse response - format is {"date": {"aiscore": X, ...}}
        if not data or not isinstance(data, dict):
            return DanelfinScore(
                ticker=ticker,
                date="",
                ai_score=0,
                technical=0,
                fundamental=0,
                sentiment=0,
                low_risk=0,
                success=False,
                error="No data available for ticker",
            )
        
        # Get the most recent date's data
        latest_date = max(data.keys())
        scores = data[latest_date]
        
        result = DanelfinScore(
            ticker=ticker,
            date=latest_date,
            ai_score=int(scores.get("aiscore", 0)),
            technical=int(scores.get("technical", 0)),
            fundamental=int(scores.get("fundamental", 0)),
            sentiment=int(scores.get("sentiment", 0)),
            low_risk=int(scores.get("low_risk", 0)),
            buy_track_record=scores.get("buy_track_record") == "yes" if "buy_track_record" in scores else None,
            sell_track_record=scores.get("sell_track_record") == "yes" if "sell_track_record" in scores else None,
            success=True,
        )
        
        # Cache the result
        _cache_score(ticker, result)
        
        logger.info(f"[Danelfin] Got scores for {ticker}: AI={result.ai_score}, Tech={result.technical}, Fund={result.fundamental}")
        
        return result
        
    except requests.exceptions.Timeout:
        logger.warning(f"[Danelfin] Timeout getting scores for {ticker}")
        return DanelfinScore(
            ticker=ticker,
            date="",
            ai_score=0,
            technical=0,
            fundamental=0,
            sentiment=0,
            low_risk=0,
            success=False,
            error="Request timeout",
        )
    except Exception as e:
        logger.error(f"[Danelfin] Error getting scores for {ticker}: {e}")
        return DanelfinScore(
            ticker=ticker,
            date="",
            ai_score=0,
            technical=0,
            fundamental=0,
            sentiment=0,
            low_risk=0,
            success=False,
            error=str(e),
        )


def get_top_stocks(
    date: Optional[str] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    min_ai_score: int = 8,
    asset_type: str = "stock",
    limit: int = 10,
) -> Dict[str, DanelfinScore]:
    """
    Get top-ranked stocks from Danelfin.
    
    Args:
        date: Date in YYYY-MM-DD format (defaults to today)
        sector: Filter by sector slug
        industry: Filter by industry slug
        min_ai_score: Minimum AI score threshold
        asset_type: "stock" or "etf"
        limit: Maximum number of results
    
    Returns:
        Dict mapping ticker to DanelfinScore
    """
    api_key = get_danelfin_api_key()
    
    if not api_key:
        logger.warning("[Danelfin] API key not configured")
        return {}
    
    try:
        headers = {"x-api-key": api_key}
        params = {
            "aiscore_min": min_ai_score,
            "asset": asset_type,
        }
        
        if date:
            params["date"] = date
        else:
            params["date"] = datetime.now().strftime("%Y-%m-%d")
        
        if sector:
            params["sector"] = sector
        if industry:
            params["industry"] = industry
        
        response = requests.get(
            f"{DANELFIN_API_BASE}/ranking",
            params=params,
            headers=headers,
            timeout=30,
        )
        
        if response.status_code != 200:
            logger.warning(f"[Danelfin] Error getting top stocks: {response.status_code}")
            return {}
        
        data = response.json()
        
        if not data:
            return {}
        
        # Parse response - format is {date: {ticker: scores, ...}}
        results = {}
        
        # Handle different response formats
        if isinstance(data, dict):
            for date_key, tickers_data in data.items():
                if isinstance(tickers_data, dict):
                    for ticker, scores in list(tickers_data.items())[:limit]:
                        if isinstance(scores, dict):
                            results[ticker] = DanelfinScore(
                                ticker=ticker,
                                date=date_key,
                                ai_score=int(scores.get("aiscore", 0)),
                                technical=int(scores.get("technical", 0)),
                                fundamental=int(scores.get("fundamental", 0)),
                                sentiment=int(scores.get("sentiment", 0)),
                                low_risk=int(scores.get("low_risk", 0)),
                                success=True,
                            )
        
        logger.info(f"[Danelfin] Got {len(results)} top stocks")
        return results
        
    except Exception as e:
        logger.error(f"[Danelfin] Error getting top stocks: {e}")
        return {}


def get_sectors() -> list:
    """Get list of available sectors."""
    api_key = get_danelfin_api_key()
    if not api_key:
        return []
    
    try:
        headers = {"x-api-key": api_key}
        response = requests.get(
            f"{DANELFIN_API_BASE}/sectors",
            headers=headers,
            timeout=15,
        )
        
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        logger.error(f"[Danelfin] Error getting sectors: {e}")
        return []


def get_industries() -> list:
    """Get list of available industries."""
    api_key = get_danelfin_api_key()
    if not api_key:
        return []
    
    try:
        headers = {"x-api-key": api_key}
        response = requests.get(
            f"{DANELFIN_API_BASE}/industries",
            headers=headers,
            timeout=15,
        )
        
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        logger.error(f"[Danelfin] Error getting industries: {e}")
        return []


# Sector mapping: Danelfin slugs to common sector names
SECTOR_SLUG_MAP = {
    "technology": "Technology",
    "healthcare": "Healthcare",
    "financial-services": "Financials",
    "consumer-cyclical": "Consumer Discretionary",
    "consumer-defensive": "Consumer Staples",
    "industrials": "Industrials",
    "energy": "Energy",
    "utilities": "Utilities",
    "basic-materials": "Materials",
    "real-estate": "Real Estate",
    "communication-services": "Communication Services",
}

# Reverse map for lookups
SECTOR_NAME_TO_SLUG = {v: k for k, v in SECTOR_SLUG_MAP.items()}

# Cache for sector top stocks
_sector_stocks_cache: Dict[str, tuple] = {}
SECTOR_CACHE_TTL = 3600  # 1 hour for sector data


def get_dynamic_sector_stocks(
    min_ai_score: int = 6,
    stocks_per_sector: int = 7,
    use_cache: bool = True,
) -> Dict[str, list]:
    """
    Get top-ranked stocks per sector from Danelfin API.
    
    This replaces the static SECTOR_STOCKS with dynamic AI-scored picks.
    
    Args:
        min_ai_score: Minimum AI score for inclusion (default 6)
        stocks_per_sector: Max stocks per sector (default 7)
        use_cache: Whether to use cached results
    
    Returns:
        Dict mapping sector names to list of ticker symbols
        e.g., {"Technology": ["AAPL", "MSFT", ...], ...}
    """
    cache_key = f"all_sectors_{min_ai_score}_{stocks_per_sector}"
    
    # Check cache
    if use_cache and cache_key in _sector_stocks_cache:
        timestamp, data = _sector_stocks_cache[cache_key]
        if time.time() - timestamp < SECTOR_CACHE_TTL:
            logger.debug("[Danelfin] Using cached sector stocks")
            return data
    
    api_key = get_danelfin_api_key()
    if not api_key:
        logger.warning("[Danelfin] No API key, returning empty sector stocks")
        return {}
    
    result = {}
    
    # Try each sector
    for slug, sector_name in SECTOR_SLUG_MAP.items():
        try:
            top_stocks = get_top_stocks(
                sector=slug,
                min_ai_score=min_ai_score,
                limit=stocks_per_sector,
            )
            
            if top_stocks:
                # Sort by AI score and take top picks
                sorted_tickers = sorted(
                    top_stocks.keys(),
                    key=lambda t: top_stocks[t].ai_score,
                    reverse=True
                )[:stocks_per_sector]
                result[sector_name] = sorted_tickers
                logger.debug(f"[Danelfin] {sector_name}: {len(sorted_tickers)} stocks")
            else:
                result[sector_name] = []
            
            # Rate limit protection
            time.sleep(0.2)
            
        except Exception as e:
            logger.debug(f"[Danelfin] Error getting {sector_name} stocks: {e}")
            result[sector_name] = []
    
    # Cache results
    _sector_stocks_cache[cache_key] = (time.time(), result)
    
    total_stocks = sum(len(v) for v in result.values())
    logger.info(f"[Danelfin] Dynamic sector stocks: {total_stocks} tickers across {len(result)} sectors")
    
    return result


def get_sector_top_10(sector_name: str, min_ai_score: int = 7) -> list:
    """
    Get top 10 stocks for a specific sector.
    
    Args:
        sector_name: Sector name (e.g., "Technology")
        min_ai_score: Minimum AI score
    
    Returns:
        List of ticker symbols sorted by AI score
    """
    slug = SECTOR_NAME_TO_SLUG.get(sector_name, sector_name.lower().replace(" ", "-"))
    
    try:
        top_stocks = get_top_stocks(sector=slug, min_ai_score=min_ai_score, limit=10)
        
        if top_stocks:
            return sorted(
                top_stocks.keys(),
                key=lambda t: top_stocks[t].ai_score,
                reverse=True
            )
        return []
    except Exception as e:
        logger.debug(f"[Danelfin] Error getting {sector_name} top 10: {e}")
        return []


# ==================== PIPELINE INTEGRATION HELPERS ====================

def get_scores_batch(tickers: list, use_cache: bool = True) -> Dict[str, DanelfinScore]:
    """
    Fetch Danelfin scores for multiple tickers.
    
    Uses caching to minimize API calls. Fetches missing tickers sequentially
    to respect rate limits.
    
    Args:
        tickers: List of ticker symbols
        use_cache: Whether to use cached results
        
    Returns:
        Dict mapping ticker to DanelfinScore
    """
    results = {}
    
    for ticker in tickers:
        score = get_score(ticker, use_cache=use_cache)
        results[ticker] = score
        
        # Small delay between requests to respect rate limits (60/min for basic plan)
        if not use_cache or not _is_cache_valid(ticker):
            time.sleep(0.1)  # 10ms delay between fresh fetches
    
    successful = sum(1 for s in results.values() if s.success)
    logger.info(f"[Danelfin] Batch fetched {len(tickers)} tickers, {successful} successful")
    
    return results


def filter_universe_by_danelfin(
    tickers: list,
    min_ai_score: int = 0,
    min_low_risk: int = 0,
    use_cache: bool = True,
) -> tuple:
    """
    Filter a list of tickers by Danelfin scores.
    
    Args:
        tickers: List of ticker symbols
        min_ai_score: Minimum AI score required (0 = no filter)
        min_low_risk: Minimum Low Risk score required (0 = no filter)
        use_cache: Whether to use cached scores
        
    Returns:
        Tuple of (filtered_tickers, scores_dict, filtered_out_tickers)
    """
    if not tickers:
        return [], {}, []
    
    # Check if Danelfin is configured
    api_key = get_danelfin_api_key()
    if not api_key:
        logger.debug("[Danelfin] Not configured, skipping universe filter")
        return tickers, {}, []
    
    scores = get_scores_batch(tickers, use_cache=use_cache)
    
    filtered = []
    filtered_out = []
    
    for ticker in tickers:
        score = scores.get(ticker)
        
        # If no score available, include ticker (fail-open)
        if not score or not score.success:
            filtered.append(ticker)
            continue
        
        # Apply filters
        passes = True
        if min_ai_score > 0 and score.ai_score < min_ai_score:
            passes = False
        if min_low_risk > 0 and score.low_risk < min_low_risk:
            passes = False
        
        if passes:
            filtered.append(ticker)
        else:
            filtered_out.append(ticker)
            logger.debug(
                f"[Danelfin] Filtered out {ticker}: AI={score.ai_score}, LowRisk={score.low_risk} "
                f"(min AI={min_ai_score}, min LowRisk={min_low_risk})"
            )
    
    if filtered_out:
        logger.info(f"[Danelfin] Filtered out {len(filtered_out)} tickers below thresholds")
    
    return filtered, scores, filtered_out


def prioritize_by_danelfin(
    tickers: list,
    scores: Dict[str, DanelfinScore] = None,
    limit: int = None,
) -> list:
    """
    Sort and prioritize tickers by Danelfin AI score (highest first).
    
    Args:
        tickers: List of ticker symbols
        scores: Pre-fetched scores dict (will fetch if None)
        limit: Maximum number of tickers to return
        
    Returns:
        Sorted list of tickers (highest AI score first)
    """
    if not tickers:
        return []
    
    # Fetch scores if not provided
    if scores is None:
        api_key = get_danelfin_api_key()
        if not api_key:
            return tickers[:limit] if limit else tickers
        scores = get_scores_batch(tickers)
    
    # Sort by AI score (descending), then by low_risk (descending) for ties
    def sort_key(ticker):
        score = scores.get(ticker)
        if not score or not score.success:
            return (0, 0)  # Put failed lookups at the end
        return (score.ai_score, score.low_risk)
    
    sorted_tickers = sorted(tickers, key=sort_key, reverse=True)
    
    if limit:
        sorted_tickers = sorted_tickers[:limit]
    
    return sorted_tickers


def check_signal_agreement(
    ticker: str,
    our_signal: str,  # "buy", "sell", "hold"
    danelfin_score: DanelfinScore = None,
    disagreement_threshold: int = 4,
) -> Dict[str, Any]:
    """
    Check if Danelfin agrees with our trading signal.
    
    Args:
        ticker: Ticker symbol
        our_signal: Our signal direction ("buy", "sell", "hold")
        danelfin_score: Pre-fetched score (will fetch if None)
        disagreement_threshold: AI score below which we flag disagreement for BUY signals
        
    Returns:
        Dict with agreement status, confidence adjustment, and reasoning
    """
    if danelfin_score is None:
        danelfin_score = get_score(ticker)
    
    if not danelfin_score.success:
        return {
            "agrees": True,  # Fail-open
            "confidence_multiplier": 1.0,
            "reason": "Danelfin unavailable, proceeding with internal signal",
            "danelfin_score": None,
        }
    
    ai_score = danelfin_score.ai_score
    our_signal_lower = our_signal.lower()
    
    # Check agreement based on signal direction
    if our_signal_lower in ("buy", "long"):
        # For buy signals, Danelfin should have decent AI score
        if ai_score < disagreement_threshold:
            return {
                "agrees": False,
                "confidence_multiplier": 0.7,  # 30% penalty
                "reason": f"Danelfin AI Score {ai_score}/10 is low for a BUY signal (threshold: {disagreement_threshold})",
                "danelfin_score": danelfin_score.to_dict(),
                "flag_for_review": True,
            }
        elif ai_score >= 8:
            return {
                "agrees": True,
                "confidence_multiplier": 1.1,  # 10% boost for strong agreement
                "reason": f"Danelfin AI Score {ai_score}/10 strongly supports BUY signal",
                "danelfin_score": danelfin_score.to_dict(),
            }
    elif our_signal_lower in ("sell", "short"):
        # For sell signals, low AI score is actually agreement
        if ai_score >= 7:
            return {
                "agrees": False,
                "confidence_multiplier": 0.8,  # 20% penalty
                "reason": f"Danelfin AI Score {ai_score}/10 is high for a SELL signal",
                "danelfin_score": danelfin_score.to_dict(),
                "flag_for_review": True,
            }
    
    # Default: agrees
    return {
        "agrees": True,
        "confidence_multiplier": 1.0,
        "reason": f"Danelfin AI Score {ai_score}/10 aligns with {our_signal.upper()} signal",
        "danelfin_score": danelfin_score.to_dict(),
    }


def get_size_adjustment(
    danelfin_score: DanelfinScore,
    high_score_boost: float = 1.25,
    low_score_reduction: float = 0.75,
) -> Dict[str, Any]:
    """
    Calculate position size adjustment based on Danelfin scores.
    
    Args:
        danelfin_score: Danelfin score for the ticker
        high_score_boost: Multiplier for high scores (AI >= 8, LowRisk >= 6)
        low_score_reduction: Multiplier for low scores (AI <= 4)
        
    Returns:
        Dict with size_multiplier and reasoning
    """
    if not danelfin_score.success:
        return {
            "size_multiplier": 1.0,
            "reason": "Danelfin unavailable, using standard sizing",
        }
    
    ai = danelfin_score.ai_score
    low_risk = danelfin_score.low_risk
    
    # High conviction: AI >= 8 AND Low Risk >= 6
    if ai >= 8 and low_risk >= 6:
        return {
            "size_multiplier": high_score_boost,
            "reason": f"Danelfin high conviction (AI={ai}, LowRisk={low_risk}): +{int((high_score_boost-1)*100)}% size",
        }
    
    # Low conviction: AI <= 4
    if ai <= 4:
        return {
            "size_multiplier": low_score_reduction,
            "reason": f"Danelfin low conviction (AI={ai}): -{int((1-low_score_reduction)*100)}% size",
        }
    
    # Moderate: no adjustment
    return {
        "size_multiplier": 1.0,
        "reason": f"Danelfin moderate conviction (AI={ai}, LowRisk={low_risk}): standard sizing",
    }


def format_for_agent_prompt(danelfin_score: DanelfinScore, ticker: str = None) -> str:
    """
    Format Danelfin score for inclusion in agent prompts.
    
    Args:
        danelfin_score: Danelfin score object
        ticker: Ticker symbol (uses score.ticker if not provided)
        
    Returns:
        Formatted string for agent prompts
    """
    ticker = ticker or danelfin_score.ticker
    
    if not danelfin_score.success:
        return f"[Danelfin AI Scoring for {ticker}: Not available]"
    
    signal = danelfin_score.signal
    signal_emoji = {
        "strong_buy": "🟢🟢",
        "buy": "🟢",
        "hold": "🟡",
        "sell": "🔴",
        "strong_sell": "🔴🔴",
    }.get(signal, "⚪")
    
    return f"""[External AI Validation - Danelfin for {ticker}]
AI Score: {danelfin_score.ai_score}/10 {signal_emoji} Signal: {signal.upper().replace('_', ' ')}
Breakdown:
  - Technical: {danelfin_score.technical}/10
  - Fundamental: {danelfin_score.fundamental}/10
  - Sentiment: {danelfin_score.sentiment}/10
  - Low Risk: {danelfin_score.low_risk}/10
(Consider this external AI opinion alongside your analysis)"""


def is_danelfin_enabled() -> bool:
    """Check if Danelfin integration is enabled."""
    try:
        from src.trading.config import get_danelfin_config
        config = get_danelfin_config()
        if not config.enabled:
            return False
    except ImportError:
        pass
    
    # Check if API key exists
    return get_danelfin_api_key() is not None
