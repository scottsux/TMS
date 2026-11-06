import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .. import config
from ..core.permissions import ensure_customer_access
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories import customer_repository, order_repository, parcel_repository, task_repository
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def create_order(body: OrderCreate, user: sqlite3.Row):
    conn = get_conn()
    try:
        ensure_customer_access(conn, user, body.customer_id)
        ensure_customer_exists(conn, body.customer_id)
        validate_order_parcels(conn, body.customer_id, body.parcel_ids)
        return order_repository.create_order_record(conn, body.customer_id, body.parcel_ids)
    finally:
        conn.close()


def list_orders(
    user: sqlite3.Row,
    customer_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    page: int = 1,
    page_size: int = 50,
):
    conn = get_conn()
    try:
        effective_customer_id = user["customer_id"] if user["role"] == UserRole.customer.value else customer_id
        rows = order_repository.list_orders(
            conn, effective_customer_id, status, page, page_size,
            tenant_id=user["tenant_id"],
            warehouse_id=user["warehouse_id"] if user["role"] == UserRole.operator.value else None,
        )
        return [row_to_order(row, order_repository.get_order_parcel_ids(conn, row["id"])) for row in rows]
    finally:
        conn.close()


def get_order(oid: int, user: sqlite3.Row):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_access(conn, user, row["customer_id"])
        return row_to_order(row, order_repository.get_order_parcel_ids(conn, oid))
    finally:
        conn.close()


def patch_order_parcels(
    oid: int,
    body: OrderParcelsPatch,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_access(conn, user, row["customer_id"])
        current = order_repository.get_order_parcel_ids(conn, oid)
        remove_ids = list(dict.fromkeys(body.remove or []))
        add_ids = body.add or []
        if len(add_ids) != len(set(add_ids)):
            raise HTTPException(status_code=400, detail="parcel_ids must not contain duplicates")
        add_ids = [pid for pid in add_ids if pid not in current]
        validate_order_parcels(conn, row["customer_id"], add_ids, exclude_order_id=oid)
        order_repository.remove_order_parcels(conn, oid, remove_ids)
        order_repository.add_order_parcels(conn, oid, add_ids, utc_now_iso())
        parcel_ids = order_repository.sync_legacy_parcel_ids(conn, oid)
        conn.commit()
        return row_to_order(get_order_or_404(conn, oid), parcel_ids)
    finally:
        conn.close()


def patch_order_no(
    oid: int,
    body: OrderNoPatch,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_access(conn, user, row["customer_id"])
        value = body.order_no.strip() or None
        order_repository.update_order_no(conn, oid, value)
        conn.commit()
        return {"order_no": value}
    finally:
        conn.close()


def auto_create_order(
    req: AutoOrderReq,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        ensure_customer_access(conn, user, req.customer_id)
        default_statuses = {ParcelStatus.SUBMITTED.value, ParcelStatus.IN_TRANSIT.value, ParcelStatus.ARRIVED.value}
        allow = {status.value for status in req.statuses} if req.statuses else default_statuses
        rows = parcel_repository.list_customer_parcels(conn, req.customer_id)
        selectable = [
            row
            for row in rows
            if row["status"] in allow and not order_repository.is_parcel_assigned(conn, row["id"])
        ]
        if not selectable:
            raise HTTPException(status_code=400, detail="no eligible parcels to create order")
        parcel_ids = [row["id"] for row in selectable]
        validate_order_parcels(conn, req.customer_id, parcel_ids)
        return order_repository.create_order_record(conn, req.customer_id, parcel_ids)
    finally:
        conn.close()


def ship_order(oid: int, user: sqlite3.Row):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_access(conn, user, order["customer_id"])
        if order["status"] != OrderStatus.READY_TO_SHIP.value:
            raise HTTPException(status_code=400, detail="order is not ready to ship")
        ensure_no_open_exceptions(conn, oid)
        order_repository.update_status(conn, oid, OrderStatus.COMPLETED)
        task_repository.mark_done_for_order(conn, oid, TaskStatus.DONE.value)
        now = utc_now_iso()
        for pid in order_repository.get_order_parcel_ids(conn, oid):
            parcel_repository.mark_shipped(conn, pid, now)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def customers(
    user: sqlite3.Row,
    page: int = 1,
    page_size: int = 50,
    q: Optional[str] = None,
):
    conn = get_conn()
    try:
        rows = customer_repository.list_customers(
            conn, page, page_size, q, tenant_id=user["tenant_id"]
        )
        return [Customer(id=row["id"], name=row["name"]) for row in rows]
    finally:
        conn.close()


def customer_detail(cid: int, user: sqlite3.Row):
    conn = get_conn()
    try:
        row = customer_repository.get_customer_by_id(conn, cid)
        if not row:
            raise HTTPException(status_code=404, detail="customer not found")
        ensure_customer_access(conn, user, cid)
        return Customer(id=row["id"], name=row["name"])
    finally:
        conn.close()
