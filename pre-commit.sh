#!/usr/bin/env bash

# Runs Python linting & formatting (Ruff) and Python tests.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running pre-commit checks...${NC}"

# 1. Python Linting & Formatting (Ruff)
echo -e "${YELLOW}[1/3] Running Ruff (Lint & Format)...${NC}"
if [ -f "venv/bin/ruff" ]; then
    ./venv/bin/ruff check . --fix
    ./venv/bin/ruff format .
else
    ruff check . --fix
    ruff format .
fi

# 2. Static API Docs (Regenerate to ensure web/api.html is fresh)
echo -e "${YELLOW}[2/3] Regenerating API docs...${NC}"
if [ -f "venv/bin/python3" ]; then
    PYTHONPATH=src ./venv/bin/python3 src/xteink/generate_api_docs.py
else
    PYTHONPATH=src python3 src/xteink/generate_api_docs.py
fi

# 3. Python Tests
echo -e "${YELLOW}[3/3] Running tests...${NC}"
if [ -f "venv/bin/python3" ]; then
    ./venv/bin/python3 -m unittest discover -s tests -p "test_*.py" -v
else
    python3 -m unittest discover -s tests -p "test_*.py" -v
fi

echo -e "${GREEN}All checks passed! Proceeding with commit.${NC}"
git add web/api.html # Ensure regenerated docs are staged
