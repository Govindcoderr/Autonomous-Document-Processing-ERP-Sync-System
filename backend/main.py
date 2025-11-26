# # backend/main.py
# import logging
# import os
# from fastapi import FastAPI, File, UploadFile, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from backend.ocr_extractor import extract_text_from_image
# from backend.llm_extractor import extract_fields
# from backend.data_validator import validate_invoice_data
# from backend.db import save_invoice_to_db
# from backend.erp_integration import push_to_erp 
# from backend.query_engine import question_to_answer 


# logging.basicConfig(level=logging.INFO)

# app = FastAPI(title="Document Processing Agent")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# #  Common pipeline logic (used by both API + Autonomous Agents)
# def process_invoice(file_path_or_bytes):
#     """
#     Runs full pipeline for both API uploads and background agents.
#     """
#     try:
#         # Step 1: OCR Extraction
#         if isinstance(file_path_or_bytes, bytes):
#             raw_text = extract_text_from_image(file_path_or_bytes)
#         elif os.path.exists(file_path_or_bytes):
#             with open(file_path_or_bytes, "rb") as f:
#                 raw_text = extract_text_from_image(f.read())
#         else:
#             raise ValueError("Invalid input type for OCR")

#         logging.info(" OCR extraction completed")

#         # Step 2: Field Extraction (LLM)
#         fields = extract_fields(raw_text)
#         logging.info(f" Extracted Fields: {fields}")

#         # Step 3: Validation
#         validated = validate_invoice_data(fields)
#         logging.info(f" Validated Data: {validated}")

       
#         # STOP PIPELINE IF VALIDATION FAILED
  
#         if validated is None:
#             logging.warning("Validation failed → Skipping DB save & ERP Push")
#             return {
#                 "status": "failed",
#                 "reason": "Required invoice fields missing. Invoice skipped.",
#                 "push_to_erp": False,
#                 "saved_to_db": False
#             }

#         # Step 4: Save to DB
#         row_id = save_invoice_to_db(validated)
#         logging.info(f"Saved invoice to DB (ID: {row_id})")

#         # Step 5: Push to ERP
#         erp_resp = push_to_erp(validated)
#         logging.info(f" ERP Push Response: {erp_resp}")

#         return {
#             "status": "success",
#             "data": validated,
#             "db_id": row_id,
#             "erp_response": erp_resp,
#             "push_to_erp": True,
#             "saved_to_db": True
#         }

#     except Exception as e:
#         logging.error(f" Processing error: {e}")
#         raise e


# #  FastAPI route (manual API trigger)
# @app.post("/process-invoice/")
# async def process_invoice_api(file: UploadFile = File(...)):
#     """
#     Manual API route (works with Postman or frontend)
#     """
#     try:
#         contents = await file.read()
#         result = process_invoice(contents)
#         return {"status": "success", **result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # Chatbot / Natural Language Query Endpoint 
# @app.post("/chatbot/query")
# async def chatbot_query(payload: dict):
#     question = payload.get("question") or payload.get("q") or ""
#     if not question or not isinstance(question, str):
#         raise HTTPException(status_code=400, detail="question is required in payload")

#     try:
#         out = question_to_answer(question, db_path=os.getenv("INVOICE_DB_PATH", "db/invoices.db"))
#         if not out.get("ok"):
#             raise Exception(out.get("error") or "Unknown error")
#         return {"status": "success", "answer": out["answer"], "sql": out["sql"], "raw_result": out["result"]}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))  


# # backend/main.py

# import os
# import logging
# from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv

# # Local imports
# from backend.ocr_extractor import extract_text_from_image
# from backend.llm_extractor import extract_fields
# from backend.data_validator import validate_invoice_data
# from backend.db import (
#     init_db,
#     save_invoice_to_db,
#     get_user_by_id,
#     get_user_by_username,
#     create_user,
# )  
# #answer_user_question
# from backend.erp_integration import push_to_erp
# from backend.query_engine import question_to_answer
# from backend import auth


# load_dotenv()
# logging.basicConfig(level=logging.INFO)

# app = FastAPI(title="Invoice + Multi-User Chatbot")

# # Init DB
# init_db()

# # CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Later restrict to frontend URL for security
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # ------------------------- #
# # Pydantic Models
# # ------------------------- #
# class RegisterPayload(BaseModel):
#     username: str
#     password: str
#     email: str | None = None

# class LoginPayload(BaseModel):
#     username: str
#     password: str

# class ChatPayload(BaseModel):
#     question: str


# # ------------------------- #
# # Auth Dependency
# # ------------------------- #
# def get_current_user(authorization: str = Header(None)):
#     if not authorization:
#         raise HTTPException(401, "Missing Authorization header")

#     parts = authorization.split()
#     if len(parts) != 2 or parts[0].lower() != "bearer":
#         raise HTTPException(401, "Invalid Authorization format")

#     token = parts[1]
#     payload = auth.decode_access_token(token)

#     user_id = payload.get("user_id")
#     if not user_id:
#         raise HTTPException(401, "Invalid token")

#     user = get_user_by_id(user_id)
#     if not user:
#         raise HTTPException(401, "User does not exist")

#     return user


# # ------------------------- #
# # Full Invoice Processing Pipeline
# # ------------------------- #
# def process_invoice(invoice_bytes: bytes, user_id: int):
#     try:
#         # 1️⃣ OCR Text Extraction
#         raw_text = extract_text_from_image(invoice_bytes)
#         logging.info("1️⃣ OCR completed")

#         # 2️⃣ Field Extraction using LLM
#         extracted = extract_fields(raw_text)
#         logging.info("2️⃣ Field extraction done")

#         # 3️⃣ Validation
#         validated = validate_invoice_data(extracted)
#         if not validated:
#             logging.error("Validation failed")
#             return {"status": "failed", "error": "Invalid invoice data"}

#         validated["user_id"] = user_id  # Assign user

#         # 4️⃣ Save to DB
#         invoice_id = save_invoice_to_db(validated, user_id)
#         logging.info(f"4️⃣ Invoice saved ID={invoice_id}")

#         # 5️⃣ ERP Push
#         erp_response = push_to_erp(validated)

#         return {
#             "status": "success",
#             "invoice_id": invoice_id,
#             "saved_to_db": True,
#             "push_to_erp": True,
#             "data": validated,
#             # "erp_response": erp_response,
#         }

#     except Exception as e:
#         logging.error(str(e))
#         raise


# # ------------------------- #
# # POST — Invoice Upload
# # ------------------------- #
# @app.post("/process-invoice/")
# async def process_invoice_api(
#     file: UploadFile = File(...),
#     current_user=Depends(get_current_user)
# ):
#     content = await file.read()
#     return process_invoice(content, current_user["id"])


# # ------------------------- #
# # Authentication APIs
# # ------------------------- #
# @app.post("/auth/register")
# def register(payload: RegisterPayload):
#     if get_user_by_username(payload.username):
#         raise HTTPException(400, "Username already exists")

#     pwd_hash = auth.hash_password(payload.password)
#     user_id = create_user(payload.username, pwd_hash, payload.email)

#     return {"status": "ok", "user_id": user_id}


# @app.post("/auth/login")
# def login(payload: LoginPayload):
#     user = get_user_by_username(payload.username)
#     if not user:
#         raise HTTPException(401, "Invalid username")

#     if not auth.verify_password(payload.password, user["password_hash"]):
#         raise HTTPException(401, "Invalid password")

#     token = auth.create_access_token({
#         "user_id": user["id"],
#         "username": user["username"]
#     })
#     return {"status": "ok", "access_token": token}

#  # ------------------------- #
# # Chatbot / Natural Language Query Endpoint
# @app.post("/chatbot/query")
# def chatbot_query(payload: ChatPayload, current_user=Depends(get_current_user)):
#     try:
#         result = question_to_answer(payload.question, current_user["id"])
#         if not result.get("ok"):
#             raise Exception(result.get("error"))
#     except Exception as e:
#         print(" CHATBOT ERROR:", str(e))
#         raise HTTPException(500, f"Chatbot crashed: {str(e)}")

#     return {
#         "status": "ok",
#         "answer": result["answer"],
#         "sql": result["sql"],
#         "data": result["result"]
#     }


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
from backend import auth

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Invoice + Multi-User Chatbot")


# ==========================================================
# 🔥 FIX — MOVE ALL INITIALIZATION INTO FASTAPI STARTUP EVENT
# This code runs ONLY ONCE when the server starts.
# It will NOT run again on each chatbot call.
# ==========================================================
@app.on_event("startup")
async def startup_event():
    logging.info("🚀 Server starting... running one-time setup.")

    # 🔥 FIX — DB initialization moved here
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


# ------------------------- #
# Pydantic Models
# ------------------------- #
class RegisterPayload(BaseModel):
    username: str
    password: str
    email: str | None = None

class LoginPayload(BaseModel):
    username: str
    password: str

class ChatPayload(BaseModel):
    question: str


# ------------------------- #
# Auth Dependency
# ------------------------- #
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Invalid Authorization format")

    token = parts[1]
    payload = auth.decode_access_token(token)

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(401, "Invalid token")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User does not exist")

    return user


# ------------------------- #
# Invoice Processing Pipeline
# ------------------------- #
def process_invoice(invoice_bytes: bytes, user_id: int):
    try:
        raw_text = extract_text_from_image(invoice_bytes)
        logging.info("1️⃣ OCR completed")

        extracted = extract_fields(raw_text)
        logging.info("2️⃣ Field extraction done")

        validated = validate_invoice_data(extracted)
        if not validated:
            logging.error("Validation failed")
            return {"status": "failed", "error": "Invalid invoice data"}

        validated["user_id"] = user_id

        invoice_id = save_invoice_to_db(validated, user_id)
        logging.info(f"4️⃣ Invoice saved ID={invoice_id}")

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


# ------------------------- #
# Authentication APIs
# ------------------------- #
@app.post("/auth/register")
def register(payload: RegisterPayload):
    if get_user_by_username(payload.username):
        raise HTTPException(400, "Username already exists")

    pwd_hash = auth.hash_password(payload.password)
    user_id = create_user(payload.username, pwd_hash, payload.email)

    return {"status": "ok", "user_id": user_id}


@app.post("/auth/login")
def login(payload: LoginPayload):
    user = get_user_by_username(payload.username)
    if not user:
        raise HTTPException(401, "Invalid username")

    if not auth.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid password")

    token = auth.create_access_token({
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
