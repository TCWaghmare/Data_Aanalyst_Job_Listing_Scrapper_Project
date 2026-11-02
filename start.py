"""
Convenient one-click launcher for the Job Finder Web Application.
Automatically sets working directory to this folder and launches the server.
"""

import os
import sys

# Ensure this project folder is the working directory and in sys.path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import uvicorn
from app import app

if __name__ == "__main__":
    print(f"Starting Data Analyst Job Finder Server...")
    print(f"Working Directory: {PROJECT_DIR}")
    print(f"Web Dashboard URL: http://127.0.0.1:8000")
    use_reload = "--reload" in sys.argv or os.environ.get("RELOAD", "false").lower() in ("true", "1")
    if use_reload:
        uvicorn.run(
            "app:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            reload_excludes=["*.db", "*.db-journal", "*.log", "*.sqlite", "jobs.db*", "tests/*", ".venv/*"]
        )
    else:
        uvicorn.run(app, host="127.0.0.1", port=8000)

