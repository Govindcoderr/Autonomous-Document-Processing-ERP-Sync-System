# from fastapi import FastAPI, File, UploadFile, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from backend.ocr_extractor import extract_text_from_image
# from backend.llm_extractor import extract_fields
# from backend.data_validator import validate_invoice_data
# from backend.db import save_invoice_to_db
# from backend.erp_integration import push_to_erp
# import logging

# # ---------------- App Setup ----------------
# app = FastAPI(title="Document Processing Agent")
# logging.basicConfig(level=logging.INFO)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ---------------- Main Route ----------------
# @app.post("/process-invoice/")
# async def process_invoice(file: UploadFile = File(...)):
#     """
#     Full pipeline:
#       1. OCR → Extract text (PDF/Image)
#       2. LLM → Extract structured fields
#       3. Validate data
#       4. Save to SQLite
#       5. Push to Zoho ERP (auto customer + invoice)
#     """

#     # Step 1: OCR Extraction
#     try:
#         contents = await file.read()
#         raw_text = extract_text_from_image(contents)
#         logging.info(" OCR extraction completed")
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"OCR error: {e}")

#     print("\n Raw OCR Text (first 500 chars):\n", raw_text[:500])

#     # Step 2: Field Extraction
#     try:
#         fields = extract_fields(raw_text)
#         logging.info(f" Extracted Fields: {fields}")
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Field extraction error: {e}")

#     # Step 3: Validation
#     try:
#         validated = validate_invoice_data(fields)
#         logging.info(f" Validated Data: {validated}")
#     except ValueError as e:
#         raise HTTPException(status_code=422, detail=str(e))

#     # Step 4: Save to Database
#     try:
#         row_id = save_invoice_to_db(validated)
#         logging.info(f"Saved invoice to DB (ID: {row_id})")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Database error: {e}")

#     # Step 5: Push to ERP (Zoho)
#     try:
#         # Directly send validated data to ERP
#         erp_resp = push_to_erp(validated)
#         logging.info(f"ERP Push Response: {erp_resp}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"ERP push failed: {e}")

#     # Step 6: Final Response
#     return {
#         "status": "success",
#         "data": validated,
#         "db_id": row_id,
#         "erp_response": erp_resp
#     }




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

