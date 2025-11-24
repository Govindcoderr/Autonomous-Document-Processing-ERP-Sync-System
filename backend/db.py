
import sqlite3
from typing import Dict, List
import os
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("INVOICE_DB_PATH")

CREATE_TABLE_INVOICES = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT,
    reference_number TEXT,
    customer_name TEXT,
    email TEXT,
    invoice_date TEXT,
    total REAL
);
"""

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


def save_invoice_to_db(data: Dict) -> int:
    """
    Saves validated invoice + line items to local SQLite database.
    """
    with sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()

        cursor.execute(CREATE_TABLE_INVOICES)
        cursor.execute(CREATE_TABLE_ITEMS)

        # Insert invoice record
        cursor.execute(
            """
            INSERT INTO invoices
            (invoice_number, reference_number, customer_name, email, invoice_date, total)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("invoice_number"),
                data.get("reference_number"),
                data.get("customer_name"),
                data.get("email"),
                data.get("invoice_date"),
                data.get("total", 0.0),
            )
        )
        invoice_id = cursor.lastrowid

        # Insert line items
        line_items: List[Dict] = data.get("line_items", [])
        for item in line_items:
            cursor.execute(
                """
                INSERT INTO invoice_items (invoice_id, description, quantity, rate)
                VALUES (?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    item.get("description"),
                    item.get("quantity", 1),
                    item.get("rate", 0.0)
                )
            )

        conn.commit()
        return invoice_id
