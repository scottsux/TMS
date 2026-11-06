import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .. import config
from ..core.permissions import ensure_customer_access
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories import parcel_repository
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def create_parcel(body: ParcelCreate, user: sqlite3.Row):
    conn = get_conn()
    try:
        ensure_customer_access(conn, user, body.customer_id)
        ensure_customer_exists(conn, body.customer_id)
        ensure_unique_tracking(conn, body.tracking_number)
        parcel_id = parcel_repository.insert_parcel(
            conn,
            body.customer_id,
            body.tracking_number,
            body.courier_company,
            body.item_category,
            body.item_description,
            body.note,
        )
        conn.commit()
        return row_to_parcel(get_parcel_or_404(conn, parcel_id))
    finally:
        conn.close()


def patch_parcel_status(
    pid: int,
    body: ParcelStatusPatch,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        row = get_parcel_or_404(conn, pid)
        ensure_customer_access(conn, user, row["customer_id"])
        ensure_transition(ParcelStatus(row["status"]), body.status)
        now = utc_now_iso()
        updates = {
            "status": body.status.value,
            "arrived_at": row["arrived_at"],
            "pack_requested_at": row["pack_requested_at"],
            "packed_at": row["packed_at"],
        }
        if body.status == ParcelStatus.ARRIVED:
            updates["arrived_at"] = now
        elif body.status == ParcelStatus.PACK_REQUESTED:
            updates["pack_requested_at"] = now
        elif body.status == ParcelStatus.PACKED:
            updates["packed_at"] = now
        parcel_repository.update_status_timestamps(
            conn,
            pid,
            body.status,
            updates["arrived_at"],
            updates["pack_requested_at"],
            updates["packed_at"],
        )
        conn.commit()
        return row_to_parcel(get_parcel_or_404(conn, pid))
    finally:
        conn.close()


def list_parcels(
    user: sqlite3.Row,
    customer_id: Optional[int] = None,
    status: Optional[ParcelStatus] = None,
    page: int = 1,
    page_size: int = 50,
):
    conn = get_conn()
    try:
        effective_customer_id = user["customer_id"] if user["role"] == UserRole.customer.value else customer_id
        rows = parcel_repository.list_parcels(
            conn, effective_customer_id, status, page, page_size,
            tenant_id=user["tenant_id"],
            warehouse_id=user["warehouse_id"] if user["role"] == UserRole.operator.value else None,
        )
        return [row_to_parcel(row) for row in rows]
    finally:
        conn.close()


def get_parcel(pid: int, user: sqlite3.Row):
    conn = get_conn()
    try:
        row = get_parcel_or_404(conn, pid)
        ensure_customer_access(conn, user, row["customer_id"])
        return row_to_parcel(row)
    finally:
        conn.close()


def parcels_by_customer(
    cid: int,
    user: sqlite3.Row,
    status: Optional[ParcelStatus] = None,
):
    conn = get_conn()
    try:
        ensure_customer_access(conn, user, cid)
        rows = parcel_repository.list_customer_parcels(conn, cid, status)
        return [row_to_parcel(row) for row in rows]
    finally:
        conn.close()


async def upload_parcel_files(
    pid: int,
    files: List[Any],
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        parcel = get_parcel_or_404(conn, pid)
        ensure_customer_access(conn, user, parcel["customer_id"])
    finally:
        conn.close()
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="max 5 files")
    ok_types = {"image/png", "image/jpeg", "image/webp"}
    saved = []
    directory = config.UPLOAD_DIR / str(pid)
    directory.mkdir(parents=True, exist_ok=True)
    for upload in files:
        if upload.content_type not in ok_types:
            raise HTTPException(status_code=400, detail=f"unsupported type: {upload.content_type}")
        data = await upload.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{upload.filename} exceeds 5MB")
        path = directory / upload.filename
        path.write_bytes(data)
        saved.append({"filename": upload.filename, "size": len(data)})
    return {"saved": saved}
