import sqlite3
from typing import Any, List, Optional

from ..models.enums import ParcelStatus


def get_parcel_by_id(conn: sqlite3.Connection, parcel_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.*, c.name AS customer_name
        FROM parcels p
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE p.id = ?
        """,
        (parcel_id,),
    ).fetchone()


def find_by_tracking(
    conn: sqlite3.Connection,
    tracking: str,
    exclude_id: Optional[int] = None,
) -> Optional[sqlite3.Row]:
    sql = "SELECT id FROM parcels WHERE lower(tracking_number) = lower(?)"
    params: list[Any] = [tracking]
    if exclude_id is not None:
        sql += " AND id != ?"
        params.append(exclude_id)
    return conn.execute(sql, params).fetchone()


def insert_parcel(
    conn: sqlite3.Connection,
    customer_id: int,
    tracking_number: str,
    courier_company: Optional[str],
    item_category: Optional[str],
    item_description: Optional[str],
    note: Optional[str],
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO parcels (
            customer_id, tracking_number, status, courier_company,
            item_category, item_description, note,
            arrived_at, pack_requested_at, packed_at, shipped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
        """,
        (
            customer_id,
            tracking_number,
            ParcelStatus.IN_TRANSIT.value,
            courier_company,
            item_category,
            item_description,
            note,
        ),
    )
    return int(cursor.lastrowid)


def list_parcels(
    conn: sqlite3.Connection,
    customer_id: Optional[int] = None,
    status: Optional[ParcelStatus] = None,
    page: int = 1,
    page_size: int = 50,
    tenant_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> List[sqlite3.Row]:
    sql = """
        SELECT p.*, c.name AS customer_name
        FROM parcels p
        JOIN customers c ON c.id = p.customer_id
        WHERE 1 = 1
    """
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND p.customer_id = ?"
        params.append(customer_id)
    if tenant_id is not None:
        sql += " AND c.tenant_id = ?"
        params.append(tenant_id)
    if warehouse_id is not None:
        sql += " AND c.warehouse_id = ?"
        params.append(warehouse_id)
    if status is not None:
        sql += " AND p.status = ?"
        params.append(status.value)
    sql += " ORDER BY p.id DESC LIMIT ? OFFSET ?"
    params.extend([page_size, max(0, (page - 1) * page_size)])
    return conn.execute(sql, params).fetchall()


def list_customer_parcels(
    conn: sqlite3.Connection,
    customer_id: int,
    status: Optional[ParcelStatus] = None,
) -> List[sqlite3.Row]:
    sql = """
        SELECT p.*, c.name AS customer_name
        FROM parcels p
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE p.customer_id = ?
    """
    params: list[Any] = [customer_id]
    if status is not None:
        sql += " AND p.status = ?"
        params.append(status.value)
    sql += " ORDER BY p.id DESC"
    return conn.execute(sql, params).fetchall()


def list_available_arrived(
    conn: sqlite3.Connection,
    customer_id: int,
    parcel_ids: Optional[set[int]] = None,
) -> List[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT p.*, c.name AS customer_name
        FROM parcels p
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE p.customer_id = ?
          AND p.status = ?
          AND NOT EXISTS (
              SELECT 1 FROM order_parcels op WHERE op.parcel_id = p.id
          )
        """,
        (customer_id, ParcelStatus.ARRIVED.value),
    ).fetchall()
    if parcel_ids is None:
        return rows
    return [row for row in rows if row["id"] in parcel_ids]


def update_status_timestamps(
    conn: sqlite3.Connection,
    parcel_id: int,
    status: ParcelStatus,
    arrived_at: Optional[str],
    pack_requested_at: Optional[str],
    packed_at: Optional[str],
) -> None:
    conn.execute(
        """
        UPDATE parcels
        SET status = ?, arrived_at = ?, pack_requested_at = ?, packed_at = ?
        WHERE id = ?
        """,
        (status.value, arrived_at, pack_requested_at, packed_at, parcel_id),
    )


def mark_pack_requested(conn: sqlite3.Connection, parcel_id: int, timestamp: str) -> None:
    conn.execute(
        "UPDATE parcels SET status = ?, pack_requested_at = ? WHERE id = ?",
        (ParcelStatus.PACK_REQUESTED.value, timestamp, parcel_id),
    )


def mark_packed(conn: sqlite3.Connection, parcel_id: int, timestamp: str) -> None:
    conn.execute(
        "UPDATE parcels SET status = ?, packed_at = ? WHERE id = ?",
        (ParcelStatus.PACKED.value, timestamp, parcel_id),
    )


def mark_shipped(conn: sqlite3.Connection, parcel_id: int, timestamp: str) -> None:
    conn.execute("UPDATE parcels SET shipped_at = ? WHERE id = ?", (timestamp, parcel_id))
