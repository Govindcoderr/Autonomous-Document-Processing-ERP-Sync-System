# backend/query_engine.py
import os
import sqlite3
import requests
import json
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("GROQ_MODEL")

DB_PATH = os.getenv("INVOICE_DB_PATH")  # adjust as needed
ROW_LIMIT = int(os.getenv("SQL_ROW_LIMIT", "250"))  # maximum rows to return

# ---------- Utilities ----------
def call_groq(messages, temperature=0.0, timeout=30):
    """
    messages: list of {"role": "system"/"user", "content": "..."}
    returns: str (assistant content)
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature
    }
    resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    # defensive access
    content = data["choices"][0]["message"]["content"]
    return content.strip()


# ---------- Safety checks ----------
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH",
    "DETACH", "PRAGMA", "VACUUM", "REINDEX", "REPLACE", "TRUNCATE"
]

def is_select_only(sql: str) -> bool:
    s = sql.strip().upper()
    # Must start with SELECT
    if not s.startswith("SELECT"):
        return False
    # Must not contain forbidden keywords
    for kw in FORBIDDEN_KEYWORDS:
        if kw in s:
            return False
    # Prevent multiple statements: disallow ';' except maybe ending
    if ";" in s[:-1]:
        return False
    return True

def enforce_limit(sql: str, default_limit=100):
    """
    If SQL has no LIMIT clause, append a LIMIT to avoid huge outputs.
    If limit present but greater than ROW_LIMIT, reduce it.
    """
    s = sql.strip()
    up = s.upper()
    if "LIMIT" in up:
        # Try to parse existing limit, reduce if too large
        try:
            # simple heuristic: find last "LIMIT" and parse integer after it
            idx = up.rfind("LIMIT")
            tail = s[idx+5:].strip()
            # get first token
            token = tail.split()[0].strip().strip(";")
            cur = int(token)
            if cur > ROW_LIMIT:
                s = s[:idx] + f"LIMIT {ROW_LIMIT}"
        except Exception:
            # if parse fails, replace with safe limit
            s = s + f" LIMIT {default_limit}"
    else:
        s = s + f" LIMIT {default_limit}"
    return s

# Schema text
def get_schema_text(db_path: str = DB_PATH) -> str:
    conn = sqlite3.connect(db_path); cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    schema = ""
    for (tname,) in tables:
        schema += f"Table: {tname}\n"
        cur.execute(f"PRAGMA table_info('{tname}');")
        cols = cur.fetchall()
        for col in cols:
            schema += f" - {col[1]} ({col[2]})\n"
        schema += "\n"
    conn.close()
    return schema or "No tables found."

# ---------- SQL Generation (LLM) ----------
def generate_sql_from_question(question: str, schema_text: str) -> str:
    """
    Ask Groq to generate a SELECT SQL query for the provided schema and question.
    Returns SQL string.
    """
    system = {
        "role": "system",
        "content": (
            "You are a helpful SQL generator for SQLite databases. "
            "Given a natural language question and a database schema, "
            "return a single valid SQLite SELECT statement only. "
            "Do NOT return any explanation or commentary. "
            "If the question cannot be answered with SQL, return: SELECT null;"
        )
    }

    user = {
        "role": "user",
        "content": (
            f"Database schema:\n{schema_text}\n\n"
            f"User question:\n{question}\n\n"
            "Return a single SQLite SELECT statement only."
        )
    }

    sql = call_groq([system, user], temperature=0.0)
    # Chomp code fences if any
    sql = sql.strip().strip("`").strip()
    return sql


# ---------- DB helpers ----------
def get_schema_text(db_path: str = DB_PATH) -> str:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    schema = ""
    for (tname,) in tables:
        schema += f"Table: {tname}\n"
        cur.execute(f"PRAGMA table_info('{tname}');")
        cols = cur.fetchall()
        for col in cols:
            cid, name, ctype, notnull, dflt, pk = col
            schema += f"  - {name} ({ctype})\n"
        schema += "\n"
    conn.close()
    return schema if schema else "No tables found in database."

def run_sql(sql: str, db_path: str = DB_PATH):
    """
    Execute SQL and return dict with 'columns' and 'rows' or {'error': msg}
    """
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        return {"columns": columns, "rows": rows}
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return {"error": str(e)}


# ---------- Result interpretation (LLM) ----------
def interpret_result_with_llm(question: str, sql: str, result: dict) -> str:
    """
    Use Groq to convert raw SQL result into a human-friendly answer.
    Include the SQL and a brief representation of results in the prompt.
    """
    # Prepare a compact textual version of the result
    columns = result.get("columns", [])
    rows = result.get("rows", [])
    if not rows:
        results_text = "No rows returned."
    else:
        # Limit representation to first N rows to avoid huge context
        max_preview = 20
        rows_preview = rows[:max_preview]
        rows_str_lines = []
        for r in rows_preview:
            # map columns to values
            row_map = {columns[i]: r[i] if i < len(r) else None for i in range(len(columns))}
            rows_str_lines.append(json.dumps(row_map, ensure_ascii=False))
        results_text = "\n".join(rows_str_lines)
        if len(rows) > max_preview:
            results_text += f"\n... ({len(rows) - max_preview} more rows truncated)"

    system = {
        "role": "system",
        "content": (
            "You are a concise data analyst. Use only the provided SQL and DB output to "
            "answer the user's question. If the data does not provide an answer, say "
            "'I don't have that information in the data.' Be concise and mention notable numbers."
        )
    }

    user_content = (
        f"User question:\n{question}\n\n"
        f"Executed SQL:\n{sql}\n\n"
        f"SQL Output (preview):\n{results_text}\n\n"
        "Provide a short, clear answer and list any assumptions. If listing rows, show no more than 5."
    )

    user = {"role": "user", "content": user_content}

    answer = call_groq([system, user], temperature=0.0)
    return answer


# ---------- Orchestrator ----------
def question_to_answer(question: str, db_path: str = DB_PATH) -> dict:
    """
    Full flow: question -> SQL -> execute -> interpret
    Returns:
      {
        "ok": True/False,
        "sql": "...",
        "result": {...},
        "answer": "..."
      }
    """
    schema = get_schema_text(db_path)
    sql = generate_sql_from_question(question, schema)

    # sanitize SQL and safety
    sql_clean = sql.strip().strip(";")
    if not is_select_only(sql_clean):
        return {"ok": False, "error": "Generated SQL is not a safe SELECT statement.", "sql": sql}

    sql_limited = enforce_limit(sql_clean, default_limit=100)
    exec_result = run_sql(sql_limited, db_path=db_path)

    if "error" in exec_result:
        return {"ok": False, "error": exec_result["error"], "sql": sql_limited}

    answer = interpret_result_with_llm(question, sql_limited, exec_result)
    return {"ok": True, "sql": sql_limited, "result": exec_result, "answer": answer}

