"""Shared persistence helpers and compatibility shims.

Domain SQL lives in the repositories named after each domain. This module
keeps row conversion, JSON helpers, and the old helper surface used by
``backend.main`` and a small amount of cross-domain validation.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from ..models.enums import OrderStatus, ParcelStatus, TaskStatus
from ..schemas import Order, Parcel, Task


def encode_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def decode_json(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    return json.loads(value)


def row_to_parcel(row: sqlite3.Row) -> Parcel:
    return Parcel(
        id=row["id"],
        customer_id=row["customer_id"],
        customer_name=row["customer_name"],
        tracking_number=row["tracking_number"],
        status=ParcelStatus(row["status"]),
        courier_company=row["courier_company"],
        item_category=row["item_category"],
        item_description=row["item_description"],
        note=row["note"],
        arrived_at=row["arrived_at"],
        pack_requested_at=row["pack_requested_at"],
        packed_at=row["packed_at"],
        shipped_at=row["shipped_at"],
    )


def row_to_order(row: sqlite3.Row, parcel_ids: Optional[List[int]] = None) -> Order:
    return Order(
        id=row["id"],
        customer_id=row["customer_id"],
        customer_name=row["customer_name"],
        parcel_ids=parcel_ids if parcel_ids is not None else [int(pid) for pid in decode_json(row["parcel_ids"]) or []],
        status=OrderStatus(row["status"]),
        actual_weight=float(row["actual_weight"] or 0),
        final_price=float(row["final_price"]) if row["final_price"] is not None else None,
        volumetric_weight=float(row["volumetric_weight"] or 0),
        forwarding=decode_json(row["forwarding"]),
        created_at=row["created_at"],
        order_no=row["order_no"],
    )


def row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        order_id=row["order_id"],
        status=TaskStatus(row["status"]),
        actual_weight=float(row["actual_weight"]) if row["actual_weight"] is not None else None,
    )


def ensure_transition(old: ParcelStatus, new: ParcelStatus) -> None:
    allowed = {
        ParcelStatus.SUBMITTED: {ParcelStatus.IN_TRANSIT, ParcelStatus.REJECTED},
        ParcelStatus.IN_TRANSIT: {ParcelStatus.ARRIVED},
        ParcelStatus.ARRIVED: {ParcelStatus.PACK_REQUESTED, ParcelStatus.PACKED},
        ParcelStatus.PACK_REQUESTED: {ParcelStatus.PACKED},
        ParcelStatus.REJECTED: set(),
        ParcelStatus.PACKED: set(),
    }
    if new not in allowed[old]:
        raise HTTPException(status_code=400, detail=f"invalid transition {old} -> {new}")


def fetch_customer_name(conn: sqlite3.Connection, customer_id: int) -> Optional[str]:
    from .customer_repository import get_customer_by_id

    row = get_customer_by_id(conn, customer_id)
    return row["name"] if row else None


def ensure_customer_exists(conn: sqlite3.Connection, customer_id: int) -> None:
    from .customer_repository import get_customer_by_id

    if not get_customer_by_id(conn, customer_id):
        raise HTTPException(status_code=400, detail="customer not found")


def ensure_unique_tracking(
    conn: sqlite3.Connection,
    tracking: str,
    exclude_id: Optional[int] = None,
) -> None:
    from .parcel_repository import find_by_tracking

    if find_by_tracking(conn, tracking, exclude_id):
        raise HTTPException(status_code=400, detail="tracking_number must be unique")


def get_parcel_or_404(conn: sqlite3.Connection, pid: int) -> sqlite3.Row:
    from .parcel_repository import get_parcel_by_id

    row = get_parcel_by_id(conn, pid)
    if not row:
        raise HTTPException(status_code=404, detail="parcel not found")
    return row


def get_order_or_404(conn: sqlite3.Connection, oid: int) -> sqlite3.Row:
    from .order_repository import get_order_by_id

    row = get_order_by_id(conn, oid)
    if not row:
        raise HTTPException(status_code=404, detail="order not found")
    return row


def get_task_or_404(conn: sqlite3.Connection, tid: int) -> sqlite3.Row:
    from .task_repository import get_task_by_id

    row = get_task_by_id(conn, tid)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    return row


def get_order_parcel_ids(conn: sqlite3.Connection, order_id: int) -> List[int]:
    from .order_repository import get_order_parcel_ids as repository_get_order_parcel_ids

    return repository_get_order_parcel_ids(conn, order_id)


def sync_legacy_order_parcel_ids(conn: sqlite3.Connection, order_id: int) -> List[int]:
    from .order_repository import sync_legacy_parcel_ids

    return sync_legacy_parcel_ids(conn, order_id)


def is_parcel_assigned(conn: sqlite3.Connection, pid: int, exclude_order_id: Optional[int] = None) -> bool:
    from .order_repository import is_parcel_assigned as repository_is_parcel_assigned

    return repository_is_parcel_assigned(conn, pid, exclude_order_id)


def validate_order_parcels(
    conn: sqlite3.Connection,
    customer_id: int,
    parcel_ids: List[int],
    exclude_order_id: Optional[int] = None,
) -> None:
    from .parcel_repository import get_parcel_by_id
    from .order_repository import is_parcel_assigned

    if len(parcel_ids) != len(set(parcel_ids)):
        raise HTTPException(status_code=400, detail="parcel_ids must not contain duplicates")
    for pid in parcel_ids:
        parcel = get_parcel_by_id(conn, pid)
        if not parcel:
            raise HTTPException(status_code=404, detail="parcel not found")
        if parcel["customer_id"] != customer_id:
            raise HTTPException(status_code=400, detail=f"parcel {pid} belongs to a different customer")
        if is_parcel_assigned(conn, pid, exclude_order_id=exclude_order_id):
            raise HTTPException(status_code=400, detail=f"parcel {pid} already in another order")


def add_order_parcels(conn: sqlite3.Connection, order_id: int, parcel_ids: List[int]) -> None:
    from .order_repository import add_order_parcels as repository_add_order_parcels
    from ..core.security import utc_now_iso

    repository_add_order_parcels(conn, order_id, parcel_ids, utc_now_iso())


def remove_order_parcels(conn: sqlite3.Connection, order_id: int, parcel_ids: List[int]) -> None:
    from .order_repository import remove_order_parcels as repository_remove_order_parcels

    repository_remove_order_parcels(conn, order_id, parcel_ids)


def migrate_order_parcels(conn: sqlite3.Connection) -> None:
    from .order_repository import migrate_order_parcels as repository_migrate_order_parcels

    repository_migrate_order_parcels(conn)


def create_order_record(
    conn: sqlite3.Connection,
    customer_id: int,
    parcel_ids: List[int],
    status: OrderStatus = OrderStatus.DRAFT,
    forwarding: Optional[Dict[str, Any]] = None,
) -> Order:
    from .order_repository import create_order_record as repository_create_order_record

    validate_order_parcels(conn, customer_id, parcel_ids)
    return repository_create_order_record(conn, customer_id, parcel_ids, status, forwarding)
