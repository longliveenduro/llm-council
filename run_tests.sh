#!/bin/bash
set -e

# Load nvm if available to ensure Node 20 is used
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"
    nvm use 20 > /dev/null
fi

echo "=== Running Backend Tests ==="
# Ensure backend dependencies are installed generally
# This assumes the user has uv/pip installed and the venv active or available
# We will just use uv sync to be safe if available, or just run pytest
if command -v uv >/dev/null 2>&1; then
    uv sync
    PYTHONPATH=. uv run pytest backend/tests/
else
    # Fallback to direct python execution
    pip install -r requirements.txt
    pip install pytest
    PYTHONPATH=. python -m pytest backend/tests/
fi

echo "=== Running Frontend Tests ==="
cd frontend
npm install
npm run test -- --run

echo "=== All Tests Passed ==="
