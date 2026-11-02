import os
import sys

# Ensure project root directory is at the front of sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Expose app and handler for universal Vercel / serverless ASGI runtime compatibility
handler = app

