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

def create_parcel(body: ParcelCreate, user: sqlite3.Row = Depends(require_permission("parcel:create"))):
    ensure_customer_scope(user, body.customer_id)
    conn = get_conn()
    try:
        ensure_customer_exists(conn, body.customer_id)
        ensure_unique_tracking(conn, body.tracking_number)
        cursor = conn.execute(
            """
            INSERT INTO parcels (
                customer_id, tracking_number, status, courier_company,
                item_category, item_description, note,
                arrived_at, pack_requested_at, packed_at, shipped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
            """,
            (
                body.customer_id,
                body.tracking_number,
                ParcelStatus.IN_TRANSIT.value,
                body.courier_company,
                body.item_category,
                body.item_description,
                body.note,
            ),
        )
        conn.commit()
        return row_to_parcel(get_parcel_or_404(conn, cursor.lastrowid))
    finally:
        conn.close()


def patch_parcel_status(
    pid: int,
    body: ParcelStatusPatch,
    user: sqlite3.Row = Depends(require_permission("parcel:arrived")),
):
    conn = get_conn()
    try:
        row = get_parcel_or_404(conn, pid)
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
        conn.execute(
            """
            UPDATE parcels
            SET status = ?, arrived_at = ?, pack_requested_at = ?, packed_at = ?
            WHERE id = ?
            """,
            (
                updates["status"],
                updates["arrived_at"],
                updates["pack_requested_at"],
                updates["packed_at"],
                pid,
            ),
        )
        conn.commit()
        return row_to_parcel(get_parcel_or_404(conn, pid))
    finally:
        conn.close()


def list_parcels(
    customer_id: Optional[int] = None,
    status: Optional[ParcelStatus] = None,
    page: int = 1,
    page_size: int = 50,
    user: sqlite3.Row = Depends(require_permission("parcel:view")),
):
    conn = get_conn()
    try:
        effective_customer_id = customer_id
        if user["role"] == UserRole.customer.value:
            effective_customer_id = user["customer_id"]
        sql = """
            SELECT p.*, c.name AS customer_name
            FROM parcels p
            LEFT JOIN customers c ON c.id = p.customer_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if effective_customer_id is not None:
            sql += " AND p.customer_id = ?"
            params.append(effective_customer_id)
        if status is not None:
            sql += " AND p.status = ?"
            params.append(status.value)
        sql += " ORDER BY p.id DESC LIMIT ? OFFSET ?"
        params.extend([page_size, max(0, (page - 1) * page_size)])
        rows = conn.execute(sql, params).fetchall()
        return [row_to_parcel(row) for row in rows]
    finally:
        conn.close()


def parcels_by_customer(
    cid: int,
    status: Optional[ParcelStatus] = None,
    user: sqlite3.Row = Depends(require_permission("parcel:view")),
):
    ensure_customer_scope(user, cid)
    conn = get_conn()
    try:
        sql = """
            SELECT p.*, c.name AS customer_name
            FROM parcels p
            LEFT JOIN customers c ON c.id = p.customer_id
            WHERE p.customer_id = ?
        """
        params: list[Any] = [cid]
        if status:
            sql += " AND p.status = ?"
            params.append(status.value)
        sql += " ORDER BY p.id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [row_to_parcel(row) for row in rows]
    finally:
        conn.close()


async def upload_parcel_files(
    pid: int,
    files: List[UploadFile] = File(...),
    user: sqlite3.Row = Depends(require_permission("parcel:create")),
):
    conn = get_conn()
    try:
        parcel = get_parcel_or_404(conn, pid)
        ensure_customer_scope(user, parcel["customer_id"])
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

