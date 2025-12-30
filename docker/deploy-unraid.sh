#!/bin/bash
# ============================================================================
# MAZO PANTHEON - Unraid Deployment Script
# ============================================================================
# 
# Usage:
#   ./deploy-unraid.sh [command]
#
# Commands:
#   deploy    - Full deployment (build + start)
#   start     - Start all services
#   stop      - Stop all services  
#   restart   - Restart all services
#   logs      - View logs
#   status    - Check status
#   build     - Rebuild images
#
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.unraid.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║            🤖 MAZO PANTHEON - AI HEDGE FUND 🤖               ║"
    echo "║                  Unraid Deployment                           ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_env() {
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        echo -e "${YELLOW}Warning: .env file not found!${NC}"
        echo "Please create .env with your API keys:"
        echo ""
        echo "  cp $PROJECT_DIR/.env.example $PROJECT_DIR/.env"
        echo "  nano $PROJECT_DIR/.env"
        echo ""
        exit 1
    fi
}

deploy() {
    print_banner
    check_env
    
    echo -e "${GREEN}🚀 Building and deploying...${NC}"
    cd "$PROJECT_DIR"
    
    docker-compose -f "$COMPOSE_FILE" build
    docker-compose -f "$COMPOSE_FILE" up -d
    
    echo ""
    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo ""
    echo "Services:"
    echo "  Frontend:  http://$(hostname):5173"
    echo "  Backend:   http://$(hostname):8000"
    echo "  API Docs:  http://$(hostname):8000/docs"
    echo ""
    echo "Run '$0 logs' to view logs"
}

start() {
    print_banner
    check_env
    echo -e "${GREEN}▶️  Starting services...${NC}"
    docker-compose -f "$COMPOSE_FILE" up -d
    status
}

stop() {
    print_banner
    echo -e "${YELLOW}⏹️  Stopping services...${NC}"
    docker-compose -f "$COMPOSE_FILE" down
    echo -e "${GREEN}Services stopped.${NC}"
}

restart() {
    stop
    start
}

logs() {
    docker-compose -f "$COMPOSE_FILE" logs -f --tail=100
}

status() {
    print_banner
    echo -e "${BLUE}📊 Service Status:${NC}"
    echo ""
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    
    # Check health
    echo -e "${BLUE}🏥 Health Checks:${NC}"
    for service in backend frontend postgres redis; do
        if docker ps --filter "name=mazo-$service" --format "{{.Status}}" | grep -q "healthy\|Up"; then
            echo -e "  $service: ${GREEN}✅ Healthy${NC}"
        else
            echo -e "  $service: ${RED}❌ Down${NC}"
        fi
    done
}

build() {
    print_banner
    echo -e "${BLUE}🔨 Building images...${NC}"
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    echo -e "${GREEN}Build complete!${NC}"
}

# Main
case "${1:-deploy}" in
    deploy)  deploy ;;
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    logs)    logs ;;
    status)  status ;;
    build)   build ;;
    *)
        echo "Usage: $0 {deploy|start|stop|restart|logs|status|build}"
        exit 1
        ;;
esac
