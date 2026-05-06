#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

RED='\033[0;31m'; CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  Job Hunter — Setup${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── Python 3.11+ ──
echo -e "\n${YELLOW}▸ Checking Python...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python 3 not found.${NC}"
    echo -e "  Install it from https://www.python.org/downloads/ (3.11 or newer)"
    exit 1
fi
PY_VERSION=$(python3 -c "import sys; print(sys.version_info.major * 10 + sys.version_info.minor)")
if [ "$PY_VERSION" -lt 311 ]; then
    echo -e "${RED}✗ Python 3.11+ required (found $(python3 --version)).${NC}"
    echo -e "  Download a newer version from https://www.python.org/downloads/"
    exit 1
fi
echo -e "${GREEN}✓ $(python3 --version)${NC}"

# ── uv ──
echo -e "\n${YELLOW}▸ Checking uv...${NC}"
if ! command -v uv &>/dev/null; then
    echo -e "${YELLOW}  uv not found — installing...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add uv to PATH for the rest of this script
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        echo -e "${RED}✗ uv installation failed.${NC}"
        echo -e "  Try manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi
echo -e "${GREEN}✓ uv $(uv --version)${NC}"

# ── Python dependencies ──
echo -e "\n${YELLOW}▸ Installing Python dependencies...${NC}"
uv sync
echo -e "${GREEN}✓ Dependencies installed${NC}"

# ── Playwright Chromium ──
echo -e "\n${YELLOW}▸ Installing Playwright Chromium...${NC}"
uv run playwright install chromium

# Install system deps (Linux only — no-op on macOS)
if [[ "$OSTYPE" == "linux"* ]]; then
    echo -e "\n${YELLOW}▸ Installing Chromium system dependencies...${NC}"
    uv run playwright install-deps chromium
fi
echo -e "${GREEN}✓ Chromium ready${NC}"

# ── .env ──
if [ ! -f .env ]; then
    echo -e "\n${YELLOW}▸ No .env found — copying .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}  !! Edit .env and add your OPENROUTER_API_KEY before running ./run.sh${NC}"
else
    echo -e "\n${GREEN}✓ .env already exists${NC}"
fi

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}  Next: edit .env, then run ./run.sh${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
