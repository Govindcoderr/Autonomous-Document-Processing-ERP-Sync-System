# backend/agents/folder_watcher.py
import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from backend.main import process_invoice

logging.basicConfig(level=logging.INFO)

WATCH_DIR = "backend/agents/incoming_invoices"

class InvoiceHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        if not (event.src_path.endswith(".pdf") or event.src_path.endswith(".jpg") or event.src_path.endswith(".png")):
            return

        filepath = event.src_path
        logging.info(f" New file detected: {filepath}")

        try:
            time.sleep(1)  # Wait for file to finish writing
            result = process_invoice(filepath)
            logging.info(f" Processed invoice successfully: {result}")
        except Exception as e:
            logging.error(f" Error processing invoice {filepath}: {e}")


def start_folder_watcher():
    os.makedirs(WATCH_DIR, exist_ok=True)
    event_handler = InvoiceHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    observer.start()

    logging.info(f" Watching folder: {WATCH_DIR}")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
