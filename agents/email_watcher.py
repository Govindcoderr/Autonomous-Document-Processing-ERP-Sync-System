# # backend/agents/email_watcher.py
# import imaplib
# import email
# import os
# import time
# import logging
# from backend.main import process_invoice 
# from dotenv import load_dotenv 
# load_dotenv()

# logging.basicConfig(level=logging.INFO)

# EMAIL_USER = os.getenv("INVOICE_EMAIL_USER")
# EMAIL_PASS = os.getenv("INVOICE_EMAIL_PASS")
# INBOX_FOLDER = "INBOX"
# DOWNLOAD_DIR = "incoming_invoices"

# os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# def fetch_invoices_from_email():
#     try:
#         mail = imaplib.IMAP4_SSL("imap.gmail.com")
#         mail.login(EMAIL_USER, EMAIL_PASS)
#         mail.select(INBOX_FOLDER)

#         # Search for unread emails
#         _, search_data = mail.search(None, '(UNSEEN)')

#         for num in search_data[0].split():
#             _, data = mail.fetch(num, "(RFC822)")
#             raw_email = data[0][1]
#             msg = email.message_from_bytes(raw_email)

#             for part in msg.walk():
#                 if part.get_content_maintype() == "multipart":
#                     continue
#                 if part.get("Content-Disposition") is None:
#                     continue

#                 filename = part.get_filename()
#                 if filename and (filename.endswith(".pdf") or filename.endswith(".jpg") or filename.endswith(".png")):
#                     filepath = os.path.join(DOWNLOAD_DIR, filename)
#                     with open(filepath, "wb") as f:
#                         f.write(part.get_payload(decode=True))

#                     logging.info(f" Downloaded new invoice: {filename}")

#                     try:
#                         result = process_invoice(filepath)
#                         logging.info(f"Processed invoice from email: {result}")
#                     except Exception as e:
#                         logging.error(f" Error processing {filename}: {e}")

#         mail.logout()

#     except Exception as e:
#         logging.error(f" Email watcher error: {e}")


# def start_email_watcher(interval=600):
#     logging.info(" Starting email watcher (checks every 10 min)...")
#     while True:
#         fetch_invoices_from_email()
#         time.sleep(interval)


# agents/email_watcher.py
import imaplib, email, os, time, logging, sqlite3
from backend.db import get_conn
from backend.main import process_invoice  # ensure relative path works when running from project root

logging.basicConfig(level=logging.INFO)
DOWNLOAD_DIR = "incoming_invoices"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_users_with_imap():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id, imap_host, imap_user, imap_pass FROM users WHERE imap_user IS NOT NULL AND imap_user != ''")
    rows = cur.fetchall()
    conn.close()
    return rows

def fetch_for_user(user_row):
    user_id, host, imap_user, imap_pass = user_row
    try:
        mail = imaplib.IMAP4_SSL(host, timeout=30)
        mail.login(imap_user, imap_pass)
        mail.select("INBOX")
        typ, data = mail.search(None, '(UNSEEN)')
        if typ != 'OK':
            mail.logout()
            return
        for num in data[0].split():
            typ, msg_data = mail.fetch(num, "(RFC822)")
            if typ != 'OK':
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            for part in msg.walk():
                if part.get_content_maintype() == "multipart": continue
                if part.get("Content-Disposition") is None: continue
                filename = part.get_filename()
                if filename and filename.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
                    local_path = os.path.join(DOWNLOAD_DIR, f"user{user_id}_{int(time.time())}_{filename}")
                    with open(local_path, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    logging.info(f"Downloaded invoice for user {user_id}: {local_path}")
                    try:
                        validated = process_invoice(local_path, user_id=user_id)
                        logging.info(f"Processed invoice for user {user_id}: {validated}")
                    except Exception as e:
                        logging.exception(f"Processing failed for {local_path}: {e}")
            mail.store(num, '+FLAGS', '\\Seen')
        mail.logout()
    except Exception:
        logging.exception(f"Failed to fetch emails for user {user_id}")

def run_email_watcher(interval=600):
    logging.info("Starting multi-user email watcher...")
    while True:
        users = get_users_with_imap()
        for u in users:
            fetch_for_user(u)
        time.sleep(interval)

if __name__ == "__main__":
    run_email_watcher(600)
