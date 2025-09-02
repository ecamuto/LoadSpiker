#!/bin/bash
# LoadSpiker Environment Setup

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOADSPIKER_ROOT="$SCRIPT_DIR"

export PYTHONPATH="$LOADSPIKER_ROOT:$PYTHONPATH"
export PATH="$LOADSPIKER_ROOT:$PATH"

echo "🚀 LoadSpiker environment activated"
echo "   LoadSpiker root: $LOADSPIKER_ROOT"
echo "   PYTHONPATH includes: $LOADSPIKER_ROOT"
echo "   You can now run: python3 cli.py [args]"
echo "   Or import loadspiker in Python scripts"

# Start a new shell with the environment
exec "$SHELL"
