#!/bin/bash
# LoadSpiker Environment Setup

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
export PATH="$SCRIPT_DIR:$PATH"

echo "🚀 LoadSpiker environment activated"
echo "   PYTHONPATH includes: $SCRIPT_DIR"
echo "   You can now run: python3 cli.py [args]"
echo "   Or import loadspiker in Python scripts"

# Start a new shell with the environment
exec "$SHELL"
