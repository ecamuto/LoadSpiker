#!/bin/bash
# LoadSpiker Environment Setup
export PYTHONPATH="/Users/enzo/src/load_tests:$PYTHONPATH"
export PATH="/Users/enzo/src/load_tests:$PATH"

echo "🚀 LoadSpiker environment activated"
echo "   PYTHONPATH includes: /Users/enzo/src/load_tests"
echo "   You can now run: python3 cli.py [args]"
echo "   Or import loadspiker in Python scripts"

# Start a new shell with the environment
exec "$SHELL"
