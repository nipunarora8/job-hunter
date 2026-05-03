#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  Job Hunter — Setup${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${YELLOW}▸ Installing Python dependencies...${NC}"
uv sync

echo -e "\n${YELLOW}▸ Installing Playwright Chromium...${NC}"
uv run playwright install chromium

echo -e "\n${YELLOW}▸ Installing Chromium system dependencies...${NC}"
uv run playwright install-deps chromium

if [ ! -f .env ]; then
    echo -e "\n${YELLOW}▸ No .env found — copying .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}  !! Edit .env and add your OPENROUTER_API_KEY before running ./run.sh${NC}"
fi

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}  Next: edit .env, then run ./run.sh${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
