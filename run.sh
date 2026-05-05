#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/src"

# ── Colors ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  Job Hunter${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── Init DB ──
echo -e "\n${YELLOW}▸ Initializing database...${NC}"
uv run python src/db.py

mkdir -p logs

# ── Cleanup on exit ──
cleanup() {
    echo -e "\n${YELLOW}▸ Shutting down...${NC}"
    kill "$SCHEDULER_PID" "$API_PID" 2>/dev/null
    echo -e "${GREEN}✓ Stopped.${NC}"
}
trap cleanup EXIT INT TERM

# ── Start scheduler (scrapes daily at 08:00 and 20:00, or via Scrape button) ──
echo -e "${YELLOW}▸ Starting scheduler...${NC}"
uv run python src/scheduler.py > logs/scheduler.log 2>&1 &
SCHEDULER_PID=$!
echo -e "${GREEN}✓ Scheduler PID $SCHEDULER_PID${NC}"

# ── Start API ──
echo -e "${YELLOW}▸ Starting API server...${NC}"
uv run python src/api.py > logs/api.log 2>&1 &
API_PID=$!
sleep 2

# Check API came up
if ! kill -0 "$API_PID" 2>/dev/null; then
    echo -e "${RED}✗ API failed to start — check logs/api.log${NC}"
    exit 1
fi

echo -e "${GREEN}✓ API PID $API_PID${NC}"
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Dashboard → http://localhost:8000${NC}"
echo -e "${GREEN}  Logs      → logs/api.log  logs/scheduler.log${NC}"
echo -e "${GREEN}  Stop      → Ctrl+C${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# ── Wait ──
wait "$API_PID"
