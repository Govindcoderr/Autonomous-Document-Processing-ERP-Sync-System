# backend/main.py
import logging
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.ocr_extractor import extract_text_from_image
from backend.llm_extractor import extract_fields
from backend.data_validator import validate_invoice_data
from backend.db import save_invoice_to_db
from backend.erp_integration import push_to_erp 
from backend.query_engine import question_to_answer 


logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Document Processing Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#  Common pipeline logic (used by both API + Autonomous Agents)
def process_invoice(file_path_or_bytes):
    """
    Runs full pipeline for both API uploads and background agents.
    """
    try:
        # Step 1: OCR Extraction
        if isinstance(file_path_or_bytes, bytes):
            raw_text = extract_text_from_image(file_path_or_bytes)
        elif os.path.exists(file_path_or_bytes):
            with open(file_path_or_bytes, "rb") as f:
                raw_text = extract_text_from_image(f.read())
        else:
            raise ValueError("Invalid input type for OCR")

        logging.info(" OCR extraction completed")

        # Step 2: Field Extraction (LLM)
        fields = extract_fields(raw_text)
        logging.info(f" Extracted Fields: {fields}")

        # Step 3: Validation
        validated = validate_invoice_data(fields)
        logging.info(f" Validated Data: {validated}")

       
        # STOP PIPELINE IF VALIDATION FAILED
  
        if validated is None:
            logging.warning("Validation failed → Skipping DB save & ERP Push")
            return {
                "status": "failed",
                "reason": "Required invoice fields missing. Invoice skipped.",
                "push_to_erp": False,
                "saved_to_db": False
            }

        # Step 4: Save to DB
        row_id = save_invoice_to_db(validated)
        logging.info(f"Saved invoice to DB (ID: {row_id})")

        # Step 5: Push to ERP
        erp_resp = push_to_erp(validated)
        logging.info(f" ERP Push Response: {erp_resp}")

        return {
            "status": "success",
            "data": validated,
            "db_id": row_id,
            "erp_response": erp_resp,
            "push_to_erp": True,
            "saved_to_db": True
        }

    except Exception as e:
        logging.error(f" Processing error: {e}")
        raise e


#  FastAPI route (manual API trigger)
@app.post("/process-invoice/")
async def process_invoice_api(file: UploadFile = File(...)):
    """
    Manual API route (works with Postman or frontend)
    """
    try:
        contents = await file.read()
        result = process_invoice(contents)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chatbot / Natural Language Query Endpoint 
@app.post("/chatbot/query")
async def chatbot_query(payload: dict):
    question = payload.get("question") or payload.get("q") or ""
    if not question or not isinstance(question, str):
        raise HTTPException(status_code=400, detail="question is required in payload")

    try:
        out = question_to_answer(question, db_path=os.getenv("INVOICE_DB_PATH", "db/invoices.db"))
        if not out.get("ok"):
            raise Exception(out.get("error") or "Unknown error")
        return {"status": "success", "answer": out["answer"], "sql": out["sql"], "raw_result": out["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))