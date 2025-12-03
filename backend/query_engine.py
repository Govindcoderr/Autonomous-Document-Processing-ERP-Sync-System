# backend/query_engine.py

import os
import sqlite3
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ----------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("GROQ_MODEL")
DB_PATH = os.getenv("INVOICE_DB_PATH")
ROW_LIMIT = int(os.getenv("SQL_ROW_LIMIT", "1050"))


# ---------------- LLM CALL ----------------
def call_groq(messages, temperature=0.0, timeout=30):
    headers = {
        "Authorization": f"Bearer " + GROQ_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature
    }

    res = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=timeout)
    res.raise_for_status()

    data = res.json()
    return data["choices"][0]["message"]["content"].strip()


# ---------------- SCHEMA ----------------
def get_user_schema():
    return (
        "Table: invoices\n"
        " - id (INTEGER)\n"
        " - invoice_number (TEXT)\n"
        " - reference_number (TEXT)\n"
        " - customer_name (TEXT)\n"
        " - email (TEXT)\n"
        " - invoice_date (TEXT)\n"
        " - total (REAL)\n"
        " - user_id (INTEGER)\n\n"
        " - Table: invoice_items\n"
        " - id (INTEGER)\n"
        " - invoice_id (INTEGER)\n"
        " - description (TEXT)\n"
        " - quantity (REAL)\n"
        " - rate (REAL)\n"
    )


# ---------------- SQL SAFETY ----------------
FORBIDDEN = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH", "PRAGMA"]

def is_safe_select(sql: str):
    sql_u = sql.upper().strip()
    return sql_u.startswith("SELECT") and not any(x in sql_u for x in FORBIDDEN)


# ---------------- SQL CLEANING ----------------
def clean_llm_sql(raw: str):
    raw = raw.strip()

    # Case 1: Code block
    if raw.startswith("```"):
        lines = raw.strip("`").splitlines()
        # Remove first word like "sql"
        if len(lines) > 0 and lines[0].lower().strip() in ["sql", "sqlite", "query"]:
            lines = lines[1:]
        cleaned = "\n".join(lines).strip()
    else:
        cleaned = raw

    # Case 2: JSON output
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and "sql" in parsed:
            cleaned = parsed["sql"]
    except:
        pass  # Not JSON

    return cleaned.strip().rstrip(";")


# ---------------- SQL GENERATION ----------------
def generate_user_sql(question: str):
    schema = get_user_schema()

    # system_msg = {
    #     "role": "system",
    #     "content": (
    #         "Generate a valid SQLite SELECT query only.\n"
    #         "Always join invoices and invoice_items:\n"
    #         " FROM invoices\n"
    #         " LEFT JOIN invoice_items ON invoices.id = invoice_items.invoice_id\n"
    #         "Do NOT output JSON. Do NOT explain. Output ONLY SQL."
    #     )
    # }
    
    system_msg = {
    "role": "system",
    "content": (
        "You are an intelligent SQL generator.\n"
        "\n"
        "Your task:\n"
        "1. Analyze the user's question.\n"
        "2. Understand the intent.\n"
        "3. Generate a complete, correct, and executable SQLite SELECT query.\n"
        "4. If the user question is incomplete or unclear, you must repair it logically.\n"
        "\n"
        "STRICT SQL RULES:\n"
        "- Output ONLY SQL. No explanation. No JSON. No natural language.\n"
        "- The query must NEVER be incomplete.\n"
        "- NEVER end with WHERE, AND, OR, or any incomplete condition.\n"
        "- NEVER generate syntax errors.\n"
        "\n"
        "TABLE RULES:\n"
        "- Always use this table structure:\n"
        "    FROM invoices\n"
        "    LEFT JOIN invoice_items ON invoices.id = invoice_items.invoice_id\n"
        "- Always SELECT from these tables.\n"
        "- If the user requests totals, use SUM(invoice_items.amount).\n"
        "\n"
        "LOGIC RULES:\n"
        "- If the user mentions a date, filter with:\n"
        "    invoices.invoice_date = 'YYYY-MM-DD'\n"
        "- If the user mentions a customer name, filter with:\n"
        "    invoices.customer_name LIKE '%name%'\n"
        "- If user mentions invoice number / reference number, filter with:\n"
        "    invoices.invoice_number = 'value'\n"
        "- If the user does not specify any filter, return a valid full SELECT query WITHOUT a WHERE clause.\n"
        "- If the user gives an incomplete filter (e.g., 'invoice of', 'customer is', 'date is'), you MUST complete it logically.\n"
        "- If the user gives only a date like '2012-11-23', assume invoice_date.\n"
        "\n"
        "OUTPUT FORMAT:\n"
        "- Always return a single complete SQL query.\n"
        "- Never include explanation, notes, markdown, or text.\n"
    )
}

    user_msg = {
        "role": "user",
        "content": f"Schema:\n{schema}\n\nQuestion:\n{question}\n\nSQL only:"
    }

    raw_sql = call_groq([system_msg, user_msg])
    sql = clean_llm_sql(raw_sql)
 
    # Auto JOIN fix
    if "JOIN" not in sql.upper():
        if "FROM invoices" in sql:
            sql = sql.replace(
                "FROM invoices",
                "FROM invoices LEFT JOIN invoice_items ON invoices.id = invoice_items.invoice_id"
            )

    return sql


# ---------------- EXECUTE SQL ----------------
def execute_for_user(sql: str, user_id: int):
    if not is_safe_select(sql):
        return {"error": "Unsafe SQL generated"}

    sql_final = sql.strip()
    sql_upper = sql_final.upper()

    # FIX: split before GROUP BY / ORDER BY
    tail = ""
    if " GROUP BY " in sql_upper:
        parts = sql_final.rsplit(" GROUP BY ", 1)
        sql_base = parts[0]
        tail = " GROUP BY " + parts[1]
    elif " ORDER BY " in sql_upper:
        parts = sql_final.rsplit(" ORDER BY ", 1)
        sql_base = parts[0]
        tail = " ORDER BY " + parts[1]
    else:
        sql_base = sql_final

    # Append user_id filter safely
    if " WHERE " in sql_base.upper():
        sql_base += f" AND invoices.user_id = {user_id}"
    else:
        sql_base += f" WHERE invoices.user_id = {user_id}"

    # Add back any GROUP BY / ORDER BY
    sql_final = sql_base + tail

    # Always limit rows
    sql_final += f" LIMIT {ROW_LIMIT}"

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql_final)
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        conn.close()

        return {"columns": columns, "rows": rows, "sql_final": sql_final}

    except Exception as e:
        return {"error": str(e)}


# ---------------- INTERPRET RESULT ----------------
def interpret_answer(question: str, sql_final: str, result):
    preview = json.dumps(result["rows"][:5], ensure_ascii=False)

    system_msg = {
        "role": "system",
        "content": (
            "You are a data analyst. Use ONLY the provided SQL and results to answer the user's question. "
            "If the data does not provide an answer, say 'I don't have that information in the data.' "
            "Be concise and mention notable numbers."
        )
    }

    user_msg = {
        "role": "user",
        "content": f"Question:\n{question}\nSQL:\n{sql_final}\nResults:\n{preview}"
    }

    return call_groq([system_msg, user_msg])


# ---------------- FALLBACK REASONING ----------------
def fallback_reasoning_llm(question: str, user_id: int):
    """
    When SQL fails, this function loads **all invoices & item details**
    for the user and lets LLM answer using reasoning.
    """

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                invoices.invoice_number,
                invoices.reference_number,
                invoices.customer_name,
                invoices.email,
                invoices.invoice_date,
                invoices.total,
                invoice_items.description,
                invoice_items.quantity,
                invoice_items.rate
            FROM invoices
            LEFT JOIN invoice_items 
                ON invoices.id = invoice_items.invoice_id
            WHERE invoices.user_id = ?
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

    except Exception as e:
        return f"Database read error: {str(e)}"

    # Format DB rows into readable text
    rows_text = "\n".join([str(r) for r in rows])

    prompt = [
        {
            "role": "system",
            "content": (
                "You are a financial analyst AI.\n"
                "You MUST answer the user's question using the raw invoice data provided.\n\n"
                "Rules:\n"
                "- If user asks TOTAL REVENUE → sum invoices.total\n"
                "- If user asks customer-specific → filter by customer_name\n"
                "- If date provided → filter by invoice_date\n"
                "- If item details needed → use quantity * rate\n"
                "- If incomplete question → interpret logically and answer.\n"
                "- Never mention SQL. Only give final answer.\n"
            )
        },
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Here is ALL raw DB data:\n{rows_text}\n\n"
                "Give final answer:"
            )
        }
    ]

    return call_groq(prompt)


# ---------------- MAIN FASTAPI HOOK ----------------
def question_to_answer(question: str, user_id: int):
    try:
        # 1️ Generate SQL from LLM
        sql = generate_user_sql(question)

        # 2️ Execute SQL
        exec_result = execute_for_user(sql, user_id)

        # 3️ If SQL failed → fallback to reasoning
        if "error" in exec_result:
            print(" SQL FAILED → Switching to Reasoning Mode")
            answer = fallback_reasoning_llm(question, user_id)

            return {
                "ok": True,
                "answer": answer,
                "sql": sql,
                "fallback": True
            }

        # 4 SQL succeeded → normal LLM answer
        answer = interpret_answer(question, exec_result["sql_final"], exec_result)

        return {
            "ok": True,
            "answer": answer,
            "sql": exec_result["sql_final"],
            "result": exec_result,
            "fallback": False
        }

    except Exception as e:
        return {"ok": False, "error": str(e), "sql": ""}
