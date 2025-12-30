#!/bin/bash
# ============================================================================
# MAZO PANTHEON - Pre-Market Health Check & Startup Script
# Run this 30 minutes before market open to ensure everything is ready
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  MAZO PANTHEON - Pre-Market Health Check  ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
ERRORS=0
WARNINGS=0

# Function to check endpoint
check_endpoint() {
    local name="$1"
    local url="$2"
    local response
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    
    if [ "$response" = "200" ]; then
        echo -e "  ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name (HTTP $response)"
        return 1
    fi
}

# Function to get JSON value
get_json_value() {
    echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print($2)" 2>/dev/null
}

# ============================================================================
# 1. Check Container Status
# ============================================================================
echo -e "${YELLOW}[1/6] Checking Docker Containers...${NC}"

containers=("mazo-backend" "mazo-frontend" "mazo-postgres" "mazo-redis" "mazo-scheduler")
for container in "${containers[@]}"; do
    status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "not found")
    health=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
    
    if [ "$status" = "running" ]; then
        if [ "$health" = "healthy" ] || [ "$health" = "none" ]; then
            echo -e "  ${GREEN}✓${NC} $container: running"
        else
            echo -e "  ${YELLOW}!${NC} $container: running but $health"
            ((WARNINGS++))
        fi
    else
        echo -e "  ${RED}✗${NC} $container: $status"
        ((ERRORS++))
    fi
done
echo ""

# ============================================================================
# 2. Check Core API Endpoints
# ============================================================================
echo -e "${YELLOW}[2/6] Checking API Endpoints...${NC}"

check_endpoint "Health endpoint" "$BACKEND_URL/health" || ((ERRORS++))
check_endpoint "Trading status" "$BACKEND_URL/trading/automated/status" || ((ERRORS++))
check_endpoint "Scheduler status" "$BACKEND_URL/trading/scheduler/status" || ((ERRORS++))
check_endpoint "Portfolio" "$BACKEND_URL/trading/portfolio" || ((ERRORS++))
check_endpoint "Monitoring" "$BACKEND_URL/monitoring/system/status" || ((ERRORS++))
echo ""

# ============================================================================
# 3. Check API Keys
# ============================================================================
echo -e "${YELLOW}[3/6] Checking API Keys...${NC}"

required_keys=("OPENAI_API_KEY" "FINANCIAL_DATASETS_API_KEY" "ALPACA_API_KEY" "ALPACA_SECRET_KEY")
for key in "${required_keys[@]}"; do
    response=$(curl -s "$BACKEND_URL/api-keys/$key" 2>/dev/null)
    is_active=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('is_active', False))" 2>/dev/null || echo "false")
    
    if [ "$is_active" = "True" ]; then
        echo -e "  ${GREEN}✓${NC} $key configured"
    else
        echo -e "  ${RED}✗${NC} $key missing or inactive"
        ((ERRORS++))
    fi
done
echo ""

# ============================================================================
# 4. Check Alpaca Connection
# ============================================================================
echo -e "${YELLOW}[4/6] Checking Alpaca Connection...${NC}"

portfolio=$(curl -s "$BACKEND_URL/trading/portfolio" 2>/dev/null)
if echo "$portfolio" | grep -q '"success":true'; then
    equity=$(echo "$portfolio" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('equity', 0))" 2>/dev/null || echo "0")
    cash=$(echo "$portfolio" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cash', 0))" 2>/dev/null || echo "0")
    positions=$(echo "$portfolio" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('positions', [])))" 2>/dev/null || echo "0")
    
    echo -e "  ${GREEN}✓${NC} Alpaca connected"
    echo -e "      Equity: \$${equity}"
    echo -e "      Cash: \$${cash}"
    echo -e "      Positions: ${positions}"
else
    echo -e "  ${RED}✗${NC} Alpaca connection failed"
    ((ERRORS++))
fi
echo ""

# ============================================================================
# 5. Check Rate Limits
# ============================================================================
echo -e "${YELLOW}[5/6] Checking Rate Limits...${NC}"

rate_limits=$(curl -s "$BACKEND_URL/monitoring/system/status" 2>/dev/null)
if [ -n "$rate_limits" ]; then
    for api in financial_datasets openai_proxy alpaca; do
        util=$(echo "$rate_limits" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['rate_limits']['$api']['utilization_pct'])" 2>/dev/null || echo "-1")
        
        if [ "$util" != "-1" ]; then
            util_int=${util%.*}
            if [ "$util_int" -lt 50 ]; then
                echo -e "  ${GREEN}✓${NC} $api: ${util}% used"
            elif [ "$util_int" -lt 80 ]; then
                echo -e "  ${YELLOW}!${NC} $api: ${util}% used (moderate)"
                ((WARNINGS++))
            else
                echo -e "  ${RED}✗${NC} $api: ${util}% used (HIGH)"
                ((ERRORS++))
            fi
        fi
    done
fi
echo ""

# ============================================================================
# 6. Check Autonomous Trading Status
# ============================================================================
echo -e "${YELLOW}[6/6] Checking Autonomous Trading...${NC}"

auto_status=$(curl -s "$BACKEND_URL/trading/automated/status" 2>/dev/null)
is_running=$(echo "$auto_status" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('is_running', False))" 2>/dev/null || echo "false")
total_runs=$(echo "$auto_status" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_runs', 0))" 2>/dev/null || echo "0")

if [ "$is_running" = "True" ]; then
    echo -e "  ${GREEN}✓${NC} Autonomous trading: ENABLED"
    echo -e "      Total runs: ${total_runs}"
else
    echo -e "  ${YELLOW}!${NC} Autonomous trading: DISABLED"
    echo -e "      Enable via UI or run: curl -X POST $BACKEND_URL/trading/automated/start"
    ((WARNINGS++))
fi

scheduler=$(curl -s "$BACKEND_URL/trading/scheduler/status" 2>/dev/null)
sched_running=$(echo "$scheduler" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('is_running', False))" 2>/dev/null || echo "false")
num_tasks=$(echo "$scheduler" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('scheduled_tasks', [])))" 2>/dev/null || echo "0")

if [ "$sched_running" = "True" ]; then
    echo -e "  ${GREEN}✓${NC} Scheduler: RUNNING"
    echo -e "      Scheduled tasks: ${num_tasks}"
else
    echo -e "  ${RED}✗${NC} Scheduler: NOT RUNNING"
    ((ERRORS++))
fi
echo ""

# ============================================================================
# Summary
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  SUMMARY${NC}"
echo -e "${BLUE}============================================${NC}"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All systems ready for trading!${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}! System ready with $WARNINGS warning(s)${NC}"
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s) and $WARNINGS warning(s) found${NC}"
    echo ""
    echo "Suggested fixes:"
    echo "  1. Restart containers: docker-compose -f docker-compose.unraid.yml restart"
    echo "  2. Check logs: docker logs mazo-backend"
    echo "  3. Enable trading: curl -X POST $BACKEND_URL/trading/automated/start"
    exit 1
fi
