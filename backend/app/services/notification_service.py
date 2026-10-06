import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .. import config
from ..core.permissions import ensure_customer_scope
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories import notification_repository, order_repository, parcel_repository
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def upsert_notification(conn: sqlite3.Connection, type_: str, customer_id: int, payload: Dict[str, Any]):
    notification_repository.upsert(conn, type_, customer_id, payload)


def notify_ready(
    body: ReadyNotify,
    user: sqlite3.Row,
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
    user: sqlite3.Row,
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
    user: sqlite3.Row,
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
            selectable = parcel_repository.list_available_arrived(conn, body.customer_id, ids)
        else:
            selectable = parcel_repository.list_available_arrived(conn, body.customer_id)

        created_order_id = None
        draft = order_repository.get_draft_order(conn, body.customer_id)

        now_iso = utc_now_iso()
        if draft is not None:
            current_ids = set(order_repository.get_order_parcel_ids(conn, draft["id"]))
            add_ids = [row["id"] for row in selectable if row["id"] not in current_ids]
            validate_order_parcels(conn, body.customer_id, add_ids, exclude_order_id=draft["id"])
            order_repository.add_order_parcels(conn, draft["id"], add_ids, now_iso)
            order_repository.sync_legacy_parcel_ids(conn, draft["id"])
            order_repository.update_status_and_forwarding(
                conn,
                draft["id"],
                OrderStatus.READY_TO_PACK,
                {
                    "channel": body.channel,
                    "destination": body.destination,
                    "service": body.service,
                    "consignee": payload["consignee"],
                },
            )
            created_order_id = draft["id"]
        elif selectable:
            order = order_repository.create_order_record(
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
            parcel_repository.mark_pack_requested(conn, row["id"], now_iso)
        conn.commit()
        return {"ok": True, "order_id": created_order_id}
    finally:
        conn.close()


def get_notifications(
    user: sqlite3.Row,
    type: Optional[str] = None,
    customer_id: Optional[int] = None,
):
    conn = get_conn()
    try:
        effective_customer_id = customer_id
        if user["role"] == UserRole.customer.value:
            effective_customer_id = user["customer_id"]
        if type:
            rows = notification_repository.list_notifications(conn, type, effective_customer_id)
        else:
            rows = notification_repository.list_notifications(conn, None, effective_customer_id)
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
    user: sqlite3.Row,
    type: Optional[str] = None,
):
    conn = get_conn()
    try:
        notification_repository.delete_notifications(conn, type)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
