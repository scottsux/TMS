import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

from .. import config
from ..db.connection import get_conn


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def make_password_hash(password: str, salt: Optional[str] = None) -> str:
    raw_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), raw_salt.encode("utf-8"), config.PBKDF2_ROUNDS
    )
    return f"{raw_salt}${base64.urlsafe_b64encode(digest).decode('utf-8')}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(make_password_hash(password, salt), stored)


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(user_row: sqlite3.Row) -> str:
    payload = {
        "sub": user_row["id"], "role": user_row["role"], "customer_id": user_row["customer_id"],
        "exp": int((utc_now() + timedelta(hours=config.TOKEN_TTL_HOURS)).timestamp()),
    }
    body = b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signature = hmac.new(config.TOKEN_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{b64url_encode(signature)}"


def parse_token(token: str) -> Dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    expected = b64url_encode(
        hmac.new(config.TOKEN_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="invalid token")
    payload = json.loads(b64url_decode(body).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(utc_now().timestamp()):
        raise HTTPException(status_code=401, detail="token expired")
    return payload


def get_current_user(authorization: Optional[str] = Header(default=None)) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    payload = parse_token(authorization.split(" ", 1)[1].strip())
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.role, u.customer_id, c.name AS customer_name
            FROM users u LEFT JOIN customers c ON c.id = u.customer_id WHERE u.id = ?
            """, (payload["sub"],)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="user not found")
    return row
