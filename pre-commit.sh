#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Running all checks...${NC}"

# 1. JS/HTML Checks
echo -e "${YELLOW}[1/3] JS Checks (Prettier & Syntax)...${NC}"
if ! command -v npx >/dev/null 2>&1; then
    echo "Error: npx not found!"
    exit 1
fi

# Format all web assets
npx -y prettier --write "web/**/*.{js,json,html}" --log-level warn

# Check syntax of all JS files
find web/js -name "*.js" -exec node --check {} \;

# 2. Python Checks
echo -e "${YELLOW}[2/3] Python Checks (Ruff)...${NC}"
if [ -f "venv/bin/ruff" ]; then
    ./venv/bin/ruff check . --fix
    ./venv/bin/ruff format .
elif command -v ruff >/dev/null 2>&1; then
    ruff check . --fix
    ruff format .
else
    echo "Error: Ruff not found!"
    exit 1
fi

# 3. Tests & Docs
echo -e "${YELLOW}[3/3] Tests & Docs...${NC}"
CMD_PYTHON="python3"
if [ -f "venv/bin/python3" ]; then
    CMD_PYTHON="./venv/bin/python3"
fi

# Docs
PYTHONPATH=src $CMD_PYTHON src/xteink/generate_api_docs.py

# Tests
$CMD_PYTHON -m coverage run -m pytest
$CMD_PYTHON -m coverage report -m

echo -e "${GREEN}All checks passed!${NC}"
