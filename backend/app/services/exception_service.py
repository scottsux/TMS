import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .. import config
from ..core.permissions import ensure_customer_scope
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories import audit_repository, exception_repository
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def create_order_exception(
    oid: int,
    body: OrderExceptionCreate,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_scope(user, order["customer_id"])
        role = UserRole(user["role"])
        if body.type not in exception_types_for_role(role):
            raise HTTPException(status_code=403, detail="exception type is not allowed for this role")
        exception_id = exception_repository.insert_exception(
            conn,
            oid,
            body.type.value,
            body.reason.strip(),
            user["id"],
            utc_now_iso(),
        )
        record_order_audit(
            conn,
            oid,
            "exception:create",
            user["id"],
            after_value={"type": body.type.value, "status": ExceptionStatus.OPEN.value},
            reason=body.reason.strip(),
            exception_id=exception_id,
        )
        conn.commit()
        return {"id": exception_id, "status": ExceptionStatus.OPEN.value}
    finally:
        conn.close()


def list_order_exceptions(
    oid: int,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_scope(user, order["customer_id"])
        rows = exception_repository.list_for_order(conn, oid)
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_exceptions(
    user: sqlite3.Row,
    status: Optional[ExceptionStatus] = None,
):
    conn = get_conn()
    try:
        effective_customer_id = None
        if user["role"] == UserRole.customer.value:
            effective_customer_id = user["customer_id"]
        rows = exception_repository.list_all(conn, effective_customer_id, status)
        return [dict(row) for row in rows]
    finally:
        conn.close()


def resolve_order_exception(
    eid: int,
    body: OrderExceptionResolve,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        exception = exception_repository.get_by_id(conn, eid)
        if not exception:
            raise HTTPException(status_code=404, detail="order exception not found")
        if exception["status"] != ExceptionStatus.OPEN.value:
            raise HTTPException(status_code=400, detail="exception is already resolved")
        resolved_at = utc_now_iso()
        exception_repository.resolve(
            conn,
            eid,
            user["id"],
            body.resolution_note.strip(),
            resolved_at,
        )
        record_order_audit(
            conn,
            exception["order_id"],
            "exception:resolve",
            user["id"],
            before_value={"status": ExceptionStatus.OPEN.value},
            after_value={"status": ExceptionStatus.RESOLVED.value},
            reason=body.resolution_note.strip(),
            exception_id=eid,
        )
        conn.commit()
        return {"ok": True, "status": ExceptionStatus.RESOLVED.value, "resolved_at": resolved_at}
    finally:
        conn.close()


def list_order_audits(
    oid: int,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_scope(user, order["customer_id"])
        rows = audit_repository.list_for_order(conn, oid)
        items = []
        for row in rows:
            item = dict(row)
            item["before_value"] = decode_json(item["before_value"])
            item["after_value"] = decode_json(item["after_value"])
            items.append(item)
        return items
    finally:
        conn.close()
