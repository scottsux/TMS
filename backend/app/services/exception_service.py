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

def create_order_exception(
    oid: int,
    body: OrderExceptionCreate,
    user: sqlite3.Row = Depends(require_permission("exception:create")),
):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_scope(user, order["customer_id"])
        role = UserRole(user["role"])
        if body.type not in exception_types_for_role(role):
            raise HTTPException(status_code=403, detail="exception type is not allowed for this role")
        cursor = conn.execute(
            """
            INSERT INTO order_exceptions (order_id, type, status, reason, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (oid, body.type.value, ExceptionStatus.OPEN.value, body.reason.strip(), user["id"], utc_now_iso()),
        )
        exception_id = cursor.lastrowid
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
    user: sqlite3.Row = Depends(require_permission("exception:view")),
):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_scope(user, order["customer_id"])
        rows = conn.execute(
            """
            SELECT e.*, creator.email AS created_by_email, resolver.email AS resolved_by_email
            FROM order_exceptions e
            JOIN users creator ON creator.id = e.created_by
            LEFT JOIN users resolver ON resolver.id = e.resolved_by
            WHERE e.order_id = ?
            ORDER BY e.id DESC
            """,
            (oid,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_exceptions(
    status: Optional[ExceptionStatus] = None,
    user: sqlite3.Row = Depends(require_permission("exception:view")),
):
    conn = get_conn()
    try:
        sql = """
            SELECT e.*, o.customer_id, o.order_no, creator.email AS created_by_email,
                   resolver.email AS resolved_by_email
            FROM order_exceptions e
            JOIN orders o ON o.id = e.order_id
            JOIN users creator ON creator.id = e.created_by
            LEFT JOIN users resolver ON resolver.id = e.resolved_by
            WHERE 1 = 1
        """
        params: list[Any] = []
        if user["role"] == UserRole.customer.value:
            sql += " AND o.customer_id = ?"
            params.append(user["customer_id"])
        if status is not None:
            sql += " AND e.status = ?"
            params.append(status.value)
        sql += " ORDER BY CASE e.status WHEN 'OPEN' THEN 0 ELSE 1 END, e.id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def resolve_order_exception(
    eid: int,
    body: OrderExceptionResolve,
    user: sqlite3.Row = Depends(require_permission("exception:resolve")),
):
    conn = get_conn()
    try:
        exception = conn.execute("SELECT * FROM order_exceptions WHERE id = ?", (eid,)).fetchone()
        if not exception:
            raise HTTPException(status_code=404, detail="order exception not found")
        if exception["status"] != ExceptionStatus.OPEN.value:
            raise HTTPException(status_code=400, detail="exception is already resolved")
        resolved_at = utc_now_iso()
        conn.execute(
            """
            UPDATE order_exceptions
            SET status = ?, resolved_by = ?, resolution_note = ?, resolved_at = ?
            WHERE id = ?
            """,
            (ExceptionStatus.RESOLVED.value, user["id"], body.resolution_note.strip(), resolved_at, eid),
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
    user: sqlite3.Row = Depends(require_permission("audit:view")),
):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_scope(user, order["customer_id"])
        rows = conn.execute(
            """
            SELECT a.*, u.email AS actor_email
            FROM order_audits a
            JOIN users u ON u.id = a.actor_id
            WHERE a.order_id = ?
            ORDER BY a.id DESC
            """,
            (oid,),
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["before_value"] = decode_json(item["before_value"])
            item["after_value"] = decode_json(item["after_value"])
            items.append(item)
        return items
    finally:
        conn.close()

