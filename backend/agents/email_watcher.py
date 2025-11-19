# backend/agents/email_watcher.py
import imaplib
import email
import os
import time
import logging
from backend.main import process_invoice 
from dotenv import load_dotenv 
load_dotenv()

logging.basicConfig(level=logging.INFO)

EMAIL_USER = os.getenv("INVOICE_EMAIL_USER")
EMAIL_PASS = os.getenv("INVOICE_EMAIL_PASS")
INBOX_FOLDER = "INBOX"
DOWNLOAD_DIR = "incoming_invoices"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def fetch_invoices_from_email():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select(INBOX_FOLDER)

        # Search for unread emails
        _, search_data = mail.search(None, '(UNSEEN)')

        for num in search_data[0].split():
            _, data = mail.fetch(num, "(RFC822)")
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get("Content-Disposition") is None:
                    continue

                filename = part.get_filename()
                if filename and (filename.endswith(".pdf") or filename.endswith(".jpg") or filename.endswith(".png")):
                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(part.get_payload(decode=True))

                    logging.info(f" Downloaded new invoice: {filename}")

                    try:
                        result = process_invoice(filepath)
                        logging.info(f"Processed invoice from email: {result}")
                    except Exception as e:
                        logging.error(f" Error processing {filename}: {e}")

        mail.logout()

    except Exception as e:
        logging.error(f" Email watcher error: {e}")


def start_email_watcher(interval=600):
    logging.info(" Starting email watcher (checks every 10 min)...")
    while True:
        fetch_invoices_from_email()
        time.sleep(interval)
