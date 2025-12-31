#!/usr/bin/env python3
"""
Data Provider Health Check Script

Verifies that all required API keys are configured and data providers are accessible.
Run this before starting the trading system to catch configuration issues early.

Usage:
    python scripts/check-data-providers.py
    
    # Or with verbose output:
    python scripts/check-data-providers.py --verbose
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment
from dotenv import load_dotenv
load_dotenv()


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_status(name: str, status: bool, message: str = ""):
    """Print a status line with checkmark or X."""
    icon = "✅" if status else "❌"
    msg = f" - {message}" if message else ""
    print(f"  {icon} {name}{msg}")


def check_api_key(name: str, env_var: str, required: bool = True) -> bool:
    """Check if an API key is configured."""
    key = os.environ.get(env_var, "")
    
    if not key:
        print_status(name, False, "Not configured")
        return False
    
    # Check for placeholder values
    if key.startswith("your-") or key in ["xxx", "YOUR_KEY_HERE", "placeholder"]:
        print_status(name, False, "Placeholder value detected")
        return False
    
    # Mask the key for display
    masked = key[:4] + "*" * (len(key) - 8) + key[-4:] if len(key) > 12 else "****"
    print_status(name, True, f"Configured ({masked})")
    return True


def test_fmp_connection(verbose: bool = False) -> bool:
    """Test FMP API connection with a simple request."""
    try:
        from src.tools.fmp_data import get_fmp_data_client
        
        client = get_fmp_data_client()
        if not client.is_configured():
            print_status("FMP Connection", False, "API key not configured")
            return False
        
        # Try to fetch a quote
        quote = client.get_quote("AAPL")
        if quote and quote.get("price"):
            price = quote.get("price")
            print_status("FMP Connection", True, f"AAPL price: ${price:.2f}")
            return True
        else:
            print_status("FMP Connection", False, "No data returned")
            return False
            
    except Exception as e:
        print_status("FMP Connection", False, str(e)[:50])
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def test_alpaca_connection(verbose: bool = False) -> bool:
    """Test Alpaca API connection."""
    try:
        from src.tools.alpaca_data import get_alpaca_data_client
        
        client = get_alpaca_data_client()
        if not client.is_configured():
            print_status("Alpaca Connection", False, "API keys not configured")
            return False
        
        # Try to get account info or a snapshot
        snapshot = client.get_snapshots(["AAPL"])
        if snapshot and len(snapshot) > 0:
            print_status("Alpaca Connection", True, "Connected successfully")
            return True
        else:
            print_status("Alpaca Connection", False, "No data returned")
            return False
            
    except Exception as e:
        print_status("Alpaca Connection", False, str(e)[:50])
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def test_financial_datasets_connection(verbose: bool = False) -> bool:
    """Test Financial Datasets API connection."""
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if not api_key:
        print_status("Financial Datasets", False, "Not configured (optional)")
        return False
    
    try:
        import requests
        url = "https://api.financialdatasets.ai/prices/snapshot/?ticker=AAPL"
        response = requests.get(url, headers={"X-API-KEY": api_key}, timeout=10)
        
        if response.status_code == 200:
            print_status("Financial Datasets", True, "Connected successfully")
            return True
        elif response.status_code == 402:
            print_status("Financial Datasets", False, "Credits exhausted")
            return False
        else:
            print_status("Financial Datasets", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_status("Financial Datasets", False, str(e)[:50])
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def check_cache_connection() -> bool:
    """Check Redis cache connection."""
    try:
        from src.data.cache import get_cache
        
        cache = get_cache()
        stats = cache.get_stats()
        
        backend = stats.get("backend", "unknown")
        if backend == "redis":
            keys = stats.get("redis_keys", 0)
            print_status("Redis Cache", True, f"{keys} keys cached")
            return True
        else:
            print_status("Redis Cache", False, "Using in-memory fallback")
            return False
            
    except Exception as e:
        print_status("Redis Cache", False, str(e)[:50])
        return False


def check_primary_data_source() -> str:
    """Check which primary data source is configured."""
    source = os.environ.get("PRIMARY_DATA_SOURCE", "fmp")
    print(f"  📊 Primary Data Source: {source.upper()}")
    return source


def main():
    parser = argparse.ArgumentParser(description="Check data provider configuration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed error messages")
    args = parser.parse_args()
    
    print_header("Mazo Pantheon - Data Provider Health Check")
    
    # Check configuration
    print("🔑 API Key Configuration:")
    print("-" * 40)
    
    required_ok = True
    required_ok &= check_api_key("FMP Ultimate", "FMP_API_KEY", required=True)
    required_ok &= check_api_key("OpenAI (LLM)", "OPENAI_API_KEY", required=True)
    required_ok &= check_api_key("Alpaca API Key", "ALPACA_API_KEY", required=True)
    required_ok &= check_api_key("Alpaca Secret", "ALPACA_SECRET_KEY", required=True)
    
    print("\n📦 Optional API Keys:")
    print("-" * 40)
    check_api_key("Financial Datasets", "FINANCIAL_DATASETS_API_KEY", required=False)
    check_api_key("Anthropic (Claude)", "ANTHROPIC_API_KEY", required=False)
    check_api_key("Groq", "GROQ_API_KEY", required=False)
    check_api_key("Tavily (Search)", "TAVILY_API_KEY", required=False)
    
    print("\n🌐 Connection Tests:")
    print("-" * 40)
    
    fmp_ok = test_fmp_connection(args.verbose)
    alpaca_ok = test_alpaca_connection(args.verbose)
    fd_ok = test_financial_datasets_connection(args.verbose)
    
    print("\n💾 Infrastructure:")
    print("-" * 40)
    cache_ok = check_cache_connection()
    
    print("\n⚙️ Configuration:")
    print("-" * 40)
    primary_source = check_primary_data_source()
    
    # Summary
    print_header("Summary")
    
    all_required_ok = required_ok and fmp_ok and alpaca_ok
    
    if all_required_ok:
        print("  ✅ All required data providers are configured and accessible!")
        print(f"  ✅ Primary source: {primary_source.upper()}")
        print(f"  ✅ Fallback chain: {primary_source.upper()} → Alpaca → Yahoo Finance")
        print("\n  🚀 Ready to start trading!\n")
        return 0
    else:
        print("  ⚠️  Some required providers are not configured or accessible.")
        print("  Please check the issues above and update your .env file.")
        print("\n  📝 Required keys:")
        print("     - FMP_API_KEY (primary data)")
        print("     - OPENAI_API_KEY (AI agents)")
        print("     - ALPACA_API_KEY + ALPACA_SECRET_KEY (trading)")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
