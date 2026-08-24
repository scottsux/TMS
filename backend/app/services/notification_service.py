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

def upsert_notification(conn: sqlite3.Connection, type_: str, customer_id: int, payload: Dict[str, Any]):
    conn.execute(
        """
        INSERT INTO notifications (type, customer_id, payload, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(type, customer_id) DO UPDATE SET
            payload = excluded.payload,
            created_at = excluded.created_at
        """,
        (type_, customer_id, encode_json(payload), utc_now_iso()),
    )


def notify_ready(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("notification:view")),
):
    conn = get_conn()
    try:
        payload = {"customer_id": body.customer_id, "message": body.message or "ready", "ts": utc_now_iso()}
        upsert_notification(conn, "ready_to_ship", body.customer_id, payload)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def notify_shipped(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("order:ship")),
):
    conn = get_conn()
    try:
        payload = {"customer_id": body.customer_id, "message": body.message or "shipped", "ts": utc_now_iso()}
        upsert_notification(conn, "shipped", body.customer_id, payload)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def notify_ready_to_pack(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("notification:create")),
):
    ensure_customer_scope(user, body.customer_id)
    conn = get_conn()
    try:
        ensure_customer_exists(conn, body.customer_id)
        now = utc_now()
        payload = {
            "customer_id": body.customer_id,
            "message": body.message or "ready_to_pack",
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "ts": now.isoformat(),
            "channel": body.channel,
            "destination": body.destination,
            "service": body.service,
            "consignee": {
                "name": body.consignee_name,
                "state": body.consignee_state,
                "city": body.consignee_city,
                "address": body.consignee_address,
                "phone": body.consignee_phone,
                "email": body.consignee_email,
                "postcode": body.consignee_postcode,
            },
        }
        upsert_notification(conn, "ready_to_pack", body.customer_id, payload)

        if body.parcel_ids:
            ids = set(body.parcel_ids)
            rows = conn.execute(
                """
                SELECT p.*
                FROM parcels p
                WHERE p.customer_id = ? AND p.status = ?
                """,
                (body.customer_id, ParcelStatus.ARRIVED.value),
            ).fetchall()
            selectable = [row for row in rows if row["id"] in ids and not is_parcel_assigned(conn, row["id"])]
        else:
            rows = conn.execute(
                "SELECT * FROM parcels WHERE customer_id = ? AND status = ?",
                (body.customer_id, ParcelStatus.ARRIVED.value),
            ).fetchall()
            selectable = [row for row in rows if not is_parcel_assigned(conn, row["id"])]

        created_order_id = None
        draft = conn.execute(
            "SELECT * FROM orders WHERE customer_id = ? AND status = ? ORDER BY id LIMIT 1",
            (body.customer_id, OrderStatus.DRAFT.value),
        ).fetchone()

        now_iso = utc_now_iso()
        if draft is not None:
            current_ids = set(get_order_parcel_ids(conn, draft["id"]))
            add_ids = [row["id"] for row in selectable if row["id"] not in current_ids]
            validate_order_parcels(conn, body.customer_id, add_ids, exclude_order_id=draft["id"])
            add_order_parcels(conn, draft["id"], add_ids)
            sync_legacy_order_parcel_ids(conn, draft["id"])
            conn.execute(
                "UPDATE orders SET status = ?, forwarding = ? WHERE id = ?",
                (
                    OrderStatus.READY_TO_PACK.value,
                    encode_json(
                        {
                            "channel": body.channel,
                            "destination": body.destination,
                            "service": body.service,
                            "consignee": payload["consignee"],
                        }
                    ),
                    draft["id"],
                ),
            )
            created_order_id = draft["id"]
        elif selectable:
            order = create_order_record(
                conn,
                body.customer_id,
                [row["id"] for row in selectable],
                status=OrderStatus.READY_TO_PACK,
                forwarding={
                    "channel": body.channel,
                    "destination": body.destination,
                    "service": body.service,
                    "consignee": payload["consignee"],
                    "actual_weight": 0.0,
                    "volumetric_weight": 0.0,
                },
            )
            created_order_id = order.id

        for row in selectable:
            conn.execute(
                "UPDATE parcels SET status = ?, pack_requested_at = ? WHERE id = ?",
                (ParcelStatus.PACK_REQUESTED.value, now_iso, row["id"]),
            )
        conn.commit()
        return {"ok": True, "order_id": created_order_id}
    finally:
        conn.close()


def get_notifications(
    type: Optional[str] = None,
    customer_id: Optional[int] = None,
    user: sqlite3.Row = Depends(require_permission("notification:view")),
):
    conn = get_conn()
    try:
        effective_customer_id = customer_id
        if user["role"] == UserRole.customer.value:
            effective_customer_id = user["customer_id"]
        sql = "SELECT * FROM notifications WHERE 1 = 1"
        params: list[Any] = []
        if type:
            sql += " AND type = ?"
            params.append(type)
        if effective_customer_id is not None:
            sql += " AND customer_id = ?"
            params.append(effective_customer_id)
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        items = [decode_json(row["payload"]) for row in rows]
        if type:
            return items
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["type"], []).append(decode_json(row["payload"]))
        return grouped
    finally:
        conn.close()


def clear_notifications(
    type: Optional[str] = None,
    user: sqlite3.Row = Depends(require_permission("notification:clear")),
):
    conn = get_conn()
    try:
        if type:
            conn.execute("DELETE FROM notifications WHERE type = ?", (type,))
        else:
            conn.execute("DELETE FROM notifications")
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

