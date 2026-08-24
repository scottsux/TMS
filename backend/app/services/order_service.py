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

def create_order(body: OrderCreate, user: sqlite3.Row = Depends(require_permission("order:create"))):
    ensure_customer_scope(user, body.customer_id)
    conn = get_conn()
    try:
        ensure_customer_exists(conn, body.customer_id)
        return create_order_record(conn, body.customer_id, body.parcel_ids)
    finally:
        conn.close()


def list_orders(
    customer_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    page: int = 1,
    page_size: int = 50,
    user: sqlite3.Row = Depends(require_permission("order:view")),
):
    conn = get_conn()
    try:
        effective_customer_id = customer_id
        if user["role"] == UserRole.customer.value:
            effective_customer_id = user["customer_id"]
        sql = """
            SELECT o.*, c.name AS customer_name
            FROM orders o
            LEFT JOIN customers c ON c.id = o.customer_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if effective_customer_id is not None:
            sql += " AND o.customer_id = ?"
            params.append(effective_customer_id)
        if status is not None:
            sql += " AND o.status = ?"
            params.append(status.value)
        sql += " ORDER BY o.id DESC LIMIT ? OFFSET ?"
        params.extend([page_size, max(0, (page - 1) * page_size)])
        rows = conn.execute(sql, params).fetchall()
        return [row_to_order(row, get_order_parcel_ids(conn, row["id"])) for row in rows]
    finally:
        conn.close()


def get_order(oid: int, user: sqlite3.Row = Depends(require_permission("order:view"))):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        return row_to_order(row, get_order_parcel_ids(conn, oid))
    finally:
        conn.close()


def patch_order_parcels(
    oid: int,
    body: OrderParcelsPatch,
    user: sqlite3.Row = Depends(require_permission("order:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        current = get_order_parcel_ids(conn, oid)
        remove_ids = list(dict.fromkeys(body.remove or []))
        add_ids = body.add or []
        if len(add_ids) != len(set(add_ids)):
            raise HTTPException(status_code=400, detail="parcel_ids must not contain duplicates")
        add_ids = [pid for pid in add_ids if pid not in current]
        validate_order_parcels(conn, row["customer_id"], add_ids, exclude_order_id=oid)
        remove_order_parcels(conn, oid, remove_ids)
        add_order_parcels(conn, oid, add_ids)
        parcel_ids = sync_legacy_order_parcel_ids(conn, oid)
        conn.commit()
        return row_to_order(get_order_or_404(conn, oid), parcel_ids)
    finally:
        conn.close()


def patch_order_no(
    oid: int,
    body: OrderNoPatch,
    user: sqlite3.Row = Depends(require_permission("order:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        value = body.order_no.strip() or None
        conn.execute("UPDATE orders SET order_no = ? WHERE id = ?", (value, oid))
        conn.commit()
        return {"order_no": value}
    finally:
        conn.close()


def auto_create_order(
    req: AutoOrderReq,
    user: sqlite3.Row = Depends(require_permission("order:create")),
):
    ensure_customer_scope(user, req.customer_id)
    conn = get_conn()
    try:
        default_statuses = {ParcelStatus.SUBMITTED.value, ParcelStatus.IN_TRANSIT.value, ParcelStatus.ARRIVED.value}
        allow = {status.value for status in req.statuses} if req.statuses else default_statuses
        rows = conn.execute("SELECT * FROM parcels WHERE customer_id = ?", (req.customer_id,)).fetchall()
        selectable = [row for row in rows if row["status"] in allow and not is_parcel_assigned(conn, row["id"])]
        if not selectable:
            raise HTTPException(status_code=400, detail="no eligible parcels to create order")
        return create_order_record(conn, req.customer_id, [row["id"] for row in selectable])
    finally:
        conn.close()


def ship_order(oid: int, user: sqlite3.Row = Depends(require_permission("order:ship"))):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_scope(user, order["customer_id"])
        if order["status"] != OrderStatus.READY_TO_SHIP.value:
            raise HTTPException(status_code=400, detail="order is not ready to ship")
        ensure_no_open_exceptions(conn, oid)
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (OrderStatus.COMPLETED.value, oid))
        conn.execute("UPDATE tasks SET status = ? WHERE order_id = ?", (TaskStatus.DONE.value, oid))
        now = utc_now_iso()
        for pid in get_order_parcel_ids(conn, oid):
            conn.execute("UPDATE parcels SET shipped_at = ? WHERE id = ?", (now, pid))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def customers(
    page: int = 1,
    page_size: int = 50,
    q: Optional[str] = None,
    user: sqlite3.Row = Depends(require_permission("customer:view")),
):
    conn = get_conn()
    try:
        sql = "SELECT * FROM customers WHERE 1 = 1"
        params: list[Any] = []
        if q:
            sql += " AND lower(name) LIKE ?"
            params.append(f"%{q.lower()}%")
        sql += " ORDER BY id LIMIT ? OFFSET ?"
        params.extend([page_size, max(0, (page - 1) * page_size)])
        rows = conn.execute(sql, params).fetchall()
        return [Customer(id=row["id"], name=row["name"]) for row in rows]
    finally:
        conn.close()


def customer_detail(cid: int, user: sqlite3.Row = Depends(require_permission("customer:view"))):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="customer not found")
        return Customer(id=row["id"], name=row["name"])
    finally:
        conn.close()

