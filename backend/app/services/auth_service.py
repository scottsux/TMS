import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .. import config
from ..core.permissions import ensure_customer_scope
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories.auth_repository import get_user_by_email
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def login(req: LoginReq):
    conn = get_conn()
    try:
        row = get_user_by_email(conn, req.email.strip())
    finally:
        conn.close()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")
    return LoginResp(
        token=create_token(row),
        role=UserRole(row["role"]),
        user={
            "id": row["customer_id"] if row["role"] == UserRole.customer.value else row["id"],
            "user_id": row["id"],
            "email": row["email"],
            "name": row["customer_name"] or row["email"],
        },
    )
