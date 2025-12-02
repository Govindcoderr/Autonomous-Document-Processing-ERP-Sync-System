# backend/auth.py

import os
import time
import jwt
from passlib.context import CryptContext
from typing import Dict
from dotenv import load_dotenv
from backend import db

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-please")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "3600"))

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- FIX: bcrypt supports only first 72 bytes ---
def _truncate(password: str) -> str:
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")

def hash_password(password: str) -> str:
    password = _truncate(password)
    return pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    plain = _truncate(plain)
    return pwd_ctx.verify(plain, hashed)

def create_access_token(data: Dict, expires_in: int = JWT_EXPIRE_SECONDS) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": int(time.time()) + int(expires_in)})
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode()
    return token

def decode_access_token(token: str) -> Dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        raise

# --- DB wrappers ---
def register_user(username: str, password: str, email: str = None):
    existing = db.get_user_by_username(username)
    if existing:
        raise ValueError("Username already exists")
    phash = hash_password(password)
    return db.create_user(username, phash, email)

def authenticate_user(username: str, password: str):
    u = db.get_user_by_username(username)
    if not u:
        return None
    if not verify_password(password, u["password_hash"]):
        return None
    return u
