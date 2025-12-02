import os
# from groq import Groq
from backend.llm_extractor import sanitize_text
import requests
from dotenv import load_dotenv
import logging
load_dotenv()

"""
LLM-Based Document Type Classifier using Groq API

This classifier works on ANY OCR text and identifies
the most likely document type using model reasoning.
"""

# Load API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable not set at doc type .")


# List of supported categories (LLM will choose best match)
DOC_TYPES = [
    "invoice",
    "bank_statement",
    "id_document",
    "aadhaar_card",
    "pan_card",
    "passport",    
    "driving_license",
    "voter_id",
    "rent_agreement",
    "utility_bill",
    "certificate",
    "property_document",
    "cheque",
    "salary_slip",
    "offer_letter",
    "admission_letter",
    "medical_report",
    "prescription",
    "exam_mark_sheet",
    "insurance_document",
    "legal_affidavit",
    "agreement",
    "tax_document",
    "purchase_order",
    "delivery_note",
    "others"
]

def classify_document_llm(ocr_text: str) -> str:
    cleaned = sanitize_text(ocr_text)
   
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are an AI document classifier. Based on this OCR text, identify the MOST LIKELY document type.

OCR TEXT:
\"\"\"{cleaned}\"\"\"

Choose ONLY ONE label from this fixed list:

{DOC_TYPES}

Return EXACTLY one label with no explanation.
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
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            logging.error(f"Groq API error: {response.text}")
            return "others"

        # Extract JSON correctly
        data = response.json()

        # CORRECT: extract LLM output
        label = data["choices"][0]["message"]["content"].strip().lower()

        logging.info(f"LLM predicted type: {label}")

        if label not in DOC_TYPES:
            return "others"

        return label

    except Exception as e:
        logging.error(f"LLM classify error: {str(e)}")
        return "others"
