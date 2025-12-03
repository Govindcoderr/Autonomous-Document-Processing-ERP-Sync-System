# # backend/llm_extractor.py   : Regex-based extractor (OLD - DEPRECATED)
# import re
# from datetime import datetime

# def extract_fields(text: str) -> dict:
#     """
#     Regex-based extractor (same structure as LLM extraction output).
#     """

#     clean_text = text.replace("\n", " ").replace("\r", " ")
#     print("Cleaned OCR Text:", clean_text[:300])

#     # ---------------- CUSTOMER NAME (simple) ----------------
#     name_match = re.search(r"(Customer Name|Name|Bill To|Billed To)\s*[:\-]?\s*([A-Za-z\s.]+)", clean_text, re.I)
#     customer_name = name_match.group(2).strip() if name_match else None

#     # ---------------- EMAIL ----------------
#     email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", clean_text)
#     email = email_match.group() if email_match else None

#     # ---------------- INVOICE DATE ----------------
#     date_match = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", clean_text)
#     invoice_date = None

#     if date_match:
#         raw = date_match.group(1).replace("/", "-")
#         # Convert to YYYY-MM-DD
#         for fmt in ("%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d"):
#             try:
#                 invoice_date = datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
#                 break
#             except:
#                 pass

#     # ---------------- REFERENCE NUMBER / INVOICE NO ----------------
#     ref_match = re.search(
#         r"(Invoice\s*No|Invoice\s*Number|Bill\s*No|Token\s*No|Reference\s*No)\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
#         clean_text,
#         re.I
#     )
#     reference_number = ref_match.group(2).strip() if ref_match else None

#     # ---------------- ITEMS (description / qty / rate) ----------------
#     item_pattern = r"([A-Za-z\s]+?)\s{1,}(\d{1,4})\s{1,}([0-9,.]{2,20})"
#     items = []

#     for desc, qty, rate in re.findall(item_pattern, clean_text):
#         items.append({
#             "description": desc.strip(),
#             "quantity": int(qty),
#             "rate": float(rate.replace(",", ""))
#         })

#     # ---------------- FINAL OUTPUT (MATCHES LLM) ----------------
#     extracted = {
#         "customer_name": customer_name,
#         "email": email,
#         "invoice_date": invoice_date,
#         "reference_number": reference_number,
#         "items": items
#     }

#     print("Extracted fields:", extracted)
#     return extracted









# backend/llm_extractor.py  : LLM-based extractor using Groq API
import re
import json
import os
import requests
from dotenv import load_dotenv 

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Clean OCR text without breaking type (fixes your crash)
def sanitize_text(text: str) -> str:
    if not text:
        return ""

    # 1. Convert invalid characters safely
    safe_bytes = text.encode("utf-8", "ignore")

    # 2. Convert back to proper UTF-8 string
    cleaned = safe_bytes.decode("utf-8", "ignore")

    # 3. Remove non-printable Unicode
    cleaned = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", " ", cleaned)

    # 4. Normalize spacing
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()

# Fix JSON from LLM
def force_json_fix(result):
    try:
        cleaned = (
            result.replace("```json", "")
                  .replace("```", "")
                  .strip()
        )
        return json.loads(cleaned)
    except:
        return {
            "customer_name": None,
            "email": None,
            "invoice_date": None,
            "reference_number": None,
            "items": []
        }

def extract_fields(text: str) -> dict:
    """
    Extract all invoice fields using LLM ONLY.
    No regex. Robust for messy OCR.
    """
    text = sanitize_text(text)
    print("Cleaned OCR:", text[:300])

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are an expert document extraction AI.
The text below is OCR output from an invoice.
The OCR may be noisy, broken, or out of order.

Your job:
1. Correct OCR mistakes.
2. Understand date formats like: `Jan 15 2013`, `January 15,2013`, `05/11/2025`
3. Infer missing fields from context.
4. ALWAYS output clean JSON following the structure below.
5. If fields are missing, use null (DO NOT guess unrealistic values).

Return ONLY valid JSON.
Format:
{{
  "customer_name": string | null,
  "email": string | null,
  "invoice_date": string | null,       // always YYYY-MM-DD
  "reference_number": string | null,
  "items": [
    {{
      "description": string,
      "quantity": number,
      "rate": number
    }}
  ]
}}

OCR TEXT:
{text}
"""

    payload = {
        "model": "groq/compound-mini",
        "messages": [
            {"role": "system", "content": "You extract structured invoice data."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        data = resp.json()
        result = data["choices"][0]["message"]["content"]

        
        return force_json_fix(result)

    except Exception as e:
        print("LLM Extraction Error:", e)
        return {
            "customer_name": None,
            "email": None,
            "invoice_date": None,
            "reference_number": None,
            "items": []
        }
