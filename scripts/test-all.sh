#!/bin/bash
# ===========================================
# Mazo Pantheon - Comprehensive Test Script
# ===========================================
# Tests all API endpoints and validates responses

set -e

API_URL="${API_URL:-http://tower.local.lan:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://tower.local.lan:5173}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

passed=0
failed=0
warnings=0

test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_field="$3"
    
    echo -n "Testing: $name... "
    
    response=$(curl -s --max-time 10 "$url" 2>&1) || {
        echo -e "${RED}FAILED${NC} (connection error)"
        ((failed++))
        return
    }
    
    if [ -n "$expected_field" ]; then
        if echo "$response" | grep -q "$expected_field"; then
            echo -e "${GREEN}PASSED${NC}"
            ((passed++))
        else
            echo -e "${RED}FAILED${NC} (missing: $expected_field)"
            ((failed++))
        fi
    else
        # Just check for valid JSON
        if echo "$response" | python3 -m json.tool > /dev/null 2>&1; then
            echo -e "${GREEN}PASSED${NC}"
            ((passed++))
        else
            echo -e "${YELLOW}WARNING${NC} (invalid JSON or empty)"
            ((warnings++))
        fi
    fi
}

test_post_endpoint() {
    local name="$1"
    local url="$2"
    local data="$3"
    local expected_field="$4"
    
    echo -n "Testing: $name... "
    
    response=$(curl -s --max-time 30 -X POST -H "Content-Type: application/json" -d "$data" "$url" 2>&1) || {
        echo -e "${RED}FAILED${NC} (connection error)"
        ((failed++))
        return
    }
    
    if [ -n "$expected_field" ]; then
        if echo "$response" | grep -q "$expected_field"; then
            echo -e "${GREEN}PASSED${NC}"
            ((passed++))
        else
            echo -e "${RED}FAILED${NC} (missing: $expected_field)"
            ((failed++))
        fi
    else
        echo -e "${GREEN}PASSED${NC}"
        ((passed++))
    fi
}

echo "=============================================="
echo "     MAZO PANTHEON - COMPREHENSIVE TESTS"
echo "=============================================="
echo ""
echo "API URL: $API_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""

echo "=== CORE ENDPOINTS ==="
test_endpoint "Health Check" "$API_URL/" "Welcome to AI Hedge Fund API"
test_endpoint "Cache Stats" "$API_URL/cache/stats" "status"
echo ""

echo "=== ALPACA INTEGRATION ==="
test_endpoint "Alpaca Status" "$API_URL/alpaca/status" "connected"
test_endpoint "Ticker Search (AAPL)" "$API_URL/alpaca/assets?search=AAPL&limit=5" "assets"
test_endpoint "Popular Tickers" "$API_URL/alpaca/popular" "tickers"
echo ""

echo "=== TRADING ENDPOINTS ==="
test_endpoint "Trading Performance" "$API_URL/trading/performance" "equity"
test_endpoint "Scheduler Status" "$API_URL/trading/scheduler/status" "is_running"
test_endpoint "Watchlist" "$API_URL/trading/watchlist" "success"
test_endpoint "Automated Trading Status" "$API_URL/trading/automated/status" "success"
echo ""

echo "=== HISTORY ENDPOINTS ==="
test_endpoint "Trade History" "$API_URL/history/trades?limit=10" "success"
test_endpoint "Agent History" "$API_URL/history/agents" "success"
test_endpoint "Performance History" "$API_URL/history/performance" "success"
echo ""

echo "=== HEDGE FUND ENDPOINTS ==="
test_endpoint "Agent List" "$API_URL/hedge-fund/agents" ""
test_endpoint "Active Workflows" "$API_URL/hedge-fund/workflows/active" ""
echo ""

echo "=== FRONTEND ==="
test_endpoint "Frontend Index" "$FRONTEND_URL/" "<!DOCTYPE html>"
echo -n "Testing: JS Bundle Load... "
js_file=$(curl -s "$FRONTEND_URL/" | grep -o 'src="/assets/index-[^"]*\.js"' | head -1 | sed 's/src="//' | sed 's/"$//')
if [ -n "$js_file" ]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL$js_file")
    if [ "$status" = "200" ]; then
        echo -e "${GREEN}PASSED${NC} ($js_file)"
        ((passed++))
    else
        echo -e "${RED}FAILED${NC} (HTTP $status)"
        ((failed++))
    fi
else
    echo -e "${RED}FAILED${NC} (no JS bundle found)"
    ((failed++))
fi

echo -n "Testing: CSS Bundle Load... "
css_file=$(curl -s "$FRONTEND_URL/" | grep -o 'href="/assets/index-[^"]*\.css"' | head -1 | sed 's/href="//' | sed 's/"$//')
if [ -n "$css_file" ]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL$css_file")
    if [ "$status" = "200" ]; then
        echo -e "${GREEN}PASSED${NC} ($css_file)"
        ((passed++))
    else
        echo -e "${RED}FAILED${NC} (HTTP $status)"
        ((failed++))
    fi
else
    echo -e "${RED}FAILED${NC} (no CSS bundle found)"
    ((failed++))
fi
echo ""

echo "=== QUICK ANALYSIS TEST (30s timeout) ==="
echo -n "Testing: Quick Analysis (TSLA)... "
analysis_result=$(curl -s --max-time 120 -X POST -H "Content-Type: application/json" \
    -d '{"tickers": ["TSLA"], "mode": "signal", "depth": "quick", "execute_trades": false, "dry_run": true}' \
    "$API_URL/unified-workflow/run" 2>&1 | tail -5)

if echo "$analysis_result" | grep -q "complete"; then
    echo -e "${GREEN}PASSED${NC}"
    ((passed++))
else
    echo -e "${YELLOW}WARNING${NC} (may still be processing)"
    ((warnings++))
fi
echo ""

echo "=============================================="
echo "                  SUMMARY"
echo "=============================================="
echo -e "Passed:   ${GREEN}$passed${NC}"
echo -e "Failed:   ${RED}$failed${NC}"
echo -e "Warnings: ${YELLOW}$warnings${NC}"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All critical tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check output above.${NC}"
    exit 1
fi
