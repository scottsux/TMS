import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import Depends, File, HTTPException, Query, UploadFile

from .. import config
from ..core.permissions import ensure_customer_scope, require_permission
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def login(req: LoginReq):
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.password_hash, u.role, u.customer_id, c.name AS customer_name
            FROM users u
            LEFT JOIN customers c ON c.id = u.customer_id
            WHERE lower(u.email) = lower(?)
            """,
            (req.email.strip(),),
        ).fetchone()
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

