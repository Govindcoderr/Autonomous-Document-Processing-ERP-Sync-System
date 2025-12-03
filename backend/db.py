# database.py

import sqlite3
from typing import Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("INVOICE_DB_PATH", "DB/invoices.db")


# USERS TABLE

CREATE_TABLE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT
);
"""



# INVOICES TABLE

CREATE_TABLE_INVOICES = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    invoice_number TEXT,
    reference_number TEXT,
    customer_name TEXT,
    email TEXT,
    invoice_date TEXT,
    total REAL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""



# LINE ITEMS TABLE

CREATE_TABLE_ITEMS = """
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER,
    description TEXT,
    quantity REAL,
    rate REAL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
);
"""


# INIT DB

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_TABLE_USERS)
        cursor.execute(CREATE_TABLE_INVOICES)
        cursor.execute(CREATE_TABLE_ITEMS)
        conn.commit()


# USER AUTH DB FUNCTIONS


def create_user(username: str, password_hash: str, email: Optional[str] = None) -> int:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        return cursor.lastrowid


def get_user_by_username(username: str):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        return dict(user) if user else None


def get_user_by_id(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None




# SAVE INVOICE (USER LINKED)

def save_invoice_to_db(data: Dict, user_id: int) -> int:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO invoices (user_id, invoice_number, reference_number, customer_name, email, invoice_date, total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                data.get("invoice_number"),
                data.get("reference_number"),
                data.get("customer_name"),
                data.get("email"),
                data.get("invoice_date"),
                data.get("total", 0.0),
            )
        )
        invoice_id = cursor.lastrowid

        for item in data.get("line_items", []):
            cursor.execute(
                """
                INSERT INTO invoice_items (invoice_id, description, quantity, rate)
                VALUES (?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    item.get("description"),
                    item.get("quantity", 1),
                    item.get("rate", 0.0),
                )
            )

        conn.commit()
        return invoice_id


# FETCH USER INVOICES

def fetch_user_invoices(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE user_id = ?", (user_id,))
        return [dict(row) for row in cursor.fetchall()]

