#!/bin/bash
# LoadSpiker Environment Setup
export PYTHONPATH="/Users/enzo/src/LoadSpiker:$PYTHONPATH"
export PATH="/Users/enzo/src/LoadSpiker:$PATH"

echo "🚀 LoadSpiker environment activated"
echo "   PYTHONPATH includes: /Users/enzo/src/LoadSpiker"
echo "   You can now run: python3 cli.py [args]"
echo "   Or import loadspiker in Python scripts"

# Start a new shell with the environment
exec "$SHELL"
