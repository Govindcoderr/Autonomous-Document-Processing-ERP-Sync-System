
# backend/main.py

import os
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Local imports
from backend.ocr_extractor import extract_text_from_image
from backend.llm_extractor import extract_fields
from backend.data_validator import validate_invoice_data
from backend.db import (
    init_db,
    save_invoice_to_db,
    get_user_by_id,
    get_user_by_username,
    create_user,
)
from backend.erp_integration import push_to_erp
from backend.query_engine import question_to_answer
from backend import login_auth
from backend.doc_identify.llm_groq_classifier import classify_document_llm

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Invoice + Multi-User Chatbot")


# ==========================================================
#  FIX — MOVE ALL INITIALIZATION INTO FASTAPI STARTUP EVENT
# This code runs ONLY ONCE when the server starts.
# It will NOT run again on each chatbot call.
# ==========================================================
@app.on_event("startup")
async def startup_event():
    logging.info(" Server starting... running one-time setup.")

    #  FIX — DB initialization moved here
    init_db()

    logging.info("✅ One-time setup completed.")
# ==========================================================


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Models

class RegisterPayload(BaseModel):
    username: str
    password: str
    email: str | None = None

class LoginPayload(BaseModel):
    username: str
    password: str

class ChatPayload(BaseModel):
    question: str



# Auth Dependency

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Invalid Authorization format")

    token = parts[1]
    payload = login_auth.decode_access_token(token)

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(401, "Invalid token")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User does not exist")

    return user



# Invoice Processing Pipeline

def process_invoice(invoice_bytes: bytes, user_id: int):
    try:
        raw_text = extract_text_from_image(invoice_bytes)
        logging.info("1 OCR completed")

        check_doc_type = classify_document_llm(raw_text)
        logging.info(f"Document Type: {check_doc_type}")
        
        if check_doc_type != "invoice": 
            logging.error("doc type")
            return {"status": "failed", "error": f"Uploaded document is not an invoice your doc type is {check_doc_type}"}

        #  Field Extraction using LLM
        
        extracted = extract_fields(raw_text)
        logging.info("2 Field extraction done")

        validated = validate_invoice_data(extracted)
        if not validated:
            logging.error("Validation failed")
            return {"status": "failed", "error": "Invalid invoice data"}

        validated["user_id"] = user_id

        invoice_id = save_invoice_to_db(validated, user_id)
        logging.info(f"4 Invoice saved ID={invoice_id}")

        push_to_erp(validated)

        return {
            "status": "success",
            "invoice_id": invoice_id,
            "saved_to_db": True,
            "push_to_erp": True,
            "data": validated,
        }

    except Exception as e:
        logging.error(str(e))
        raise



# POST — Invoice Upload
@app.post("/process-invoice/")
async def process_invoice_api(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    content = await file.read()
    return process_invoice(content, current_user["id"])

#document type classification
@app.post("/classify-document/")
async def classify_document_api(
    file: UploadFile = File(...),
    
):
    content = await file.read()
    raw_text = extract_text_from_image(content)
    doc_type = classify_document_llm(raw_text)
    return {"status": "success", "document_type": doc_type}


# Authentication APIs

@app.post("/auth/register")
def register(payload: RegisterPayload):
    if get_user_by_username(payload.username):
        raise HTTPException(400, "Username already exists")

    pwd_hash = login_auth.hash_password(payload.password)
    user_id = create_user(payload.username, pwd_hash, payload.email)

    return {"status": "ok", "user_id": user_id}


@app.post("/auth/login")
def login(payload: LoginPayload):
    user = get_user_by_username(payload.username)
    if not user:
        raise HTTPException(401, "Invalid username")

    if not login_auth.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid password")

    token = login_auth.create_access_token({
        "user_id": user["id"],
        "username": user["username"]
    })
    return {"status": "ok", "access_token": token}


# Chatbot API

#  FIX: accept both /chatbot/query and /chatbot/query/ so frontend trailing slash won't 307 redirect
@app.post("/chatbot/query")
@app.post("/chatbot/query/")
def chatbot_query(payload: ChatPayload, current_user=Depends(get_current_user)):
    try:
        # FIX: Chatbot must only call the query engine. No invoice processing here.
        result = question_to_answer(payload.question, current_user["id"])

        if not result.get("ok"):
            # result may contain error info from query engine
            raise Exception(result.get("error") or "Unknown error from query engine")

    except Exception as e:
        print(" CHATBOT ERROR:", str(e))
        raise HTTPException(500, f"Chatbot crashed: {str(e)}")

    # FIX: return compact response (avoid sending large ERP payloads back to UI)
    return {
        "status": "ok",
        "answer": result["answer"],
        "sql": result.get("sql"),
        "data": result.get("result")
    }
