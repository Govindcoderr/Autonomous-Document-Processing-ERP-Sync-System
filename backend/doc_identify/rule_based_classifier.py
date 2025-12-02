"""
Rule-based document classifier based on keyword matching.
Used as a fallback when ML-based classifier is not confident.
"""

# Rule-based keyword dictionary
DOCUMENT_PATTERNS = {
    "invoice": [
        "invoice", "invoice no", "gstin", "subtotal", "amount due", "bill to",
        "taxable value", "hsn", "gst", "qty", "rate" , "total amount", "purchase order",
        "due date", "payment terms", "tax invoice", "supplier", "customer","billing address"
        "bill to", "ship to", "item description", "unit price" , "invoice date", ""

    ],
    "cheque": [
        "cheque", "cheque number","micr", "ifsc", "pay to", "rupees", "bearer", "a/c payee",
        "signature", "drawer", "bank of" , "AC/ NO."
    ],
    "bank_document": [
        "statement period", "available balance", "account summary",
        "transaction details", "account no", "branch code", "balance",
        "withdrawal", "deposit", "neft", "rtgs"
    ],
    "id_document": [
        "government", "identity", "dob", "date of birth", "pan", "aadhaar",
        "passport", "father name", "uidai", "address"
    ]
}

def classify_document_rule_based(ocr_text: str) -> str:
    """
    Classify document using rule-based keyword matching.
    Returns one of:
    - invoice
    - cheque
    - bank_document
    - id_document
    - others
    """
    # cleaned = clean_text(ocr_text) now not needed as keywords are in lowercase
    cleaned = ocr_text.lower()

    for doc_type, keywords in DOCUMENT_PATTERNS.items():
        for keyword in keywords:
            if keyword in cleaned:
                return doc_type

    return "others"
