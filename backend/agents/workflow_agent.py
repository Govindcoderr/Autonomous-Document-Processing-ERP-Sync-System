import sys
import os
import threading
import time
import logging
import uvicorn

# Make sure backend imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.agents.folder_watcher import start_folder_watcher
from backend.agents.email_watcher import start_email_watcher
from backend.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run_api():
    """Run FastAPI app"""
    logging.info(" Starting FastAPI Backend (Document Processing Agent)...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)


def run_folder_agent():
    """Run Folder Watcher"""
    logging.info(" Starting Folder Watcher Agent...")
    start_folder_watcher()


def run_email_agent():
    """Run Email Watcher Agent"""
    logging.info(" Starting Email Watcher Agent...")
    start_email_watcher(interval=600)  # every 10 minutes


if __name__ == "__main__":
    logging.info(" Initializing Autonomous Workflow Agent...")

    # Run all in parallel
    api_thread = threading.Thread(target=run_api, daemon=True)
    folder_thread = threading.Thread(target=run_folder_agent, daemon=True)
    email_thread = threading.Thread(target=run_email_agent, daemon=True)

    api_thread.start()
    folder_thread.start()
    email_thread.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logging.info(" Workflow Agent stopped manually.")
