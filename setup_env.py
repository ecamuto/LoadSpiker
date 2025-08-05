#!/usr/bin/env python3
"""
Set up environment for LoadSpiker without pip install
"""
import os
import sys
import shutil

def setup_environment():
    """Set up the environment to use LoadSpiker"""
    
    # Get the current directory
    current_dir = os.path.abspath('.')
    obj_dir = os.path.join(current_dir, 'obj')
    
    # Check if the extension was built
    so_file = os.path.join(obj_dir, 'loadspiker.so')
    if not os.path.exists(so_file):
        print("❌ loadspiker.so not found. Run 'make build' first.")
        return False
    
    # Copy the .so file to the loadspiker directory
    loadspiker_dir = os.path.join(current_dir, 'loadspiker')
    dest_so = os.path.join(loadspiker_dir, 'loadspiker.so')
    
    try:
        shutil.copy2(so_file, dest_so)
        print(f"✅ Copied {so_file} to {dest_so}")
    except Exception as e:
        print(f"❌ Failed to copy extension: {e}")
        return False
    
    # Create a shell script to set up environment
    shell_script = f"""#!/bin/bash
# LoadSpiker Environment Setup
export PYTHONPATH="{current_dir}:$PYTHONPATH"
export PATH="{current_dir}:$PATH"

echo "🚀 LoadSpiker environment activated"
echo "   PYTHONPATH includes: {current_dir}"
echo "   You can now run: python3 cli.py [args]"
echo "   Or import loadspiker in Python scripts"

# Start a new shell with the environment
exec "$SHELL"
"""
    
    env_script_path = os.path.join(current_dir, 'activate_env.sh')
    with open(env_script_path, 'w') as f:
        f.write(shell_script)
    
    os.chmod(env_script_path, 0o755)
    
    print(f"✅ Created activation script: {env_script_path}")
    print("\nTo activate LoadSpiker environment:")
    print(f"   source {env_script_path}")
    print("\nOr run directly:")
    print(f"   PYTHONPATH={current_dir} python3 cli.py --help")
    
    return True

if __name__ == '__main__':
    if setup_environment():
        print("\n🎉 LoadSpiker environment setup complete!")
    else:
        sys.exit(1)
