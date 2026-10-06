import sqlite3
from typing import Any, Dict, List, Optional

from ..models.enums import OrderStatus, TaskStatus
from ..schemas import Order
from ..core.security import utc_now_iso
from .common import decode_json, encode_json, row_to_order
from .parcel_repository import get_parcel_by_id


def get_order_by_id(conn: sqlite3.Connection, order_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT o.*, c.name AS customer_name
        FROM orders o
        LEFT JOIN customers c ON c.id = o.customer_id
        WHERE o.id = ?
        """,
        (order_id,),
    ).fetchone()


def list_orders(
    conn: sqlite3.Connection,
    customer_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    page: int = 1,
    page_size: int = 50,
) -> List[sqlite3.Row]:
    sql = """
        SELECT o.*, c.name AS customer_name
        FROM orders o
        LEFT JOIN customers c ON c.id = o.customer_id
        WHERE 1 = 1
    """
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND o.customer_id = ?"
        params.append(customer_id)
    if status is not None:
        sql += " AND o.status = ?"
        params.append(status.value)
    sql += " ORDER BY o.id DESC LIMIT ? OFFSET ?"
    params.extend([page_size, max(0, (page - 1) * page_size)])
    return conn.execute(sql, params).fetchall()


def get_order_parcel_ids(conn: sqlite3.Connection, order_id: int) -> List[int]:
    rows = conn.execute(
        "SELECT parcel_id FROM order_parcels WHERE order_id = ? ORDER BY rowid", (order_id,)
    ).fetchall()
    return [row["parcel_id"] for row in rows]


def sync_legacy_parcel_ids(conn: sqlite3.Connection, order_id: int) -> List[int]:
    parcel_ids = get_order_parcel_ids(conn, order_id)
    conn.execute("UPDATE orders SET parcel_ids = ? WHERE id = ?", (encode_json(parcel_ids), order_id))
    return parcel_ids


def is_parcel_assigned(
    conn: sqlite3.Connection,
    parcel_id: int,
    exclude_order_id: Optional[int] = None,
) -> bool:
    sql = "SELECT 1 FROM order_parcels WHERE parcel_id = ?"
    params: list[Any] = [parcel_id]
    if exclude_order_id is not None:
        sql += " AND order_id != ?"
        params.append(exclude_order_id)
    return conn.execute(sql, params).fetchone() is not None


def add_order_parcels(conn: sqlite3.Connection, order_id: int, parcel_ids: List[int], timestamp: str) -> None:
    if parcel_ids:
        conn.executemany(
            "INSERT INTO order_parcels (order_id, parcel_id, created_at) VALUES (?, ?, ?)",
            [(order_id, parcel_id, timestamp) for parcel_id in parcel_ids],
        )


def remove_order_parcels(conn: sqlite3.Connection, order_id: int, parcel_ids: List[int]) -> None:
    if parcel_ids:
        placeholders = ", ".join("?" for _ in parcel_ids)
        conn.execute(
            f"DELETE FROM order_parcels WHERE order_id = ? AND parcel_id IN ({placeholders})",
            [order_id, *parcel_ids],
        )


def create_order_record(
    conn: sqlite3.Connection,
    customer_id: int,
    parcel_ids: List[int],
    status: OrderStatus = OrderStatus.DRAFT,
    forwarding: Optional[Dict[str, Any]] = None,
) -> Order:
    now = utc_now_iso()
    cursor = conn.execute(
        """
        INSERT INTO orders (
            customer_id, parcel_ids, status, actual_weight, final_price,
            volumetric_weight, forwarding, created_at, order_no
        ) VALUES (?, ?, ?, 0, NULL, 0, ?, ?, NULL)
        """,
        (customer_id, encode_json(parcel_ids), status.value, encode_json(forwarding), now),
    )
    order_id = cursor.lastrowid
    add_order_parcels(conn, order_id, parcel_ids, now)
    conn.execute(
        "INSERT INTO tasks (order_id, status, actual_weight) VALUES (?, ?, NULL)",
        (order_id, TaskStatus.TODO.value),
    )
    conn.commit()
    row = get_order_by_id(conn, order_id)
    return row_to_order(row, get_order_parcel_ids(conn, order_id))


def update_order_no(conn: sqlite3.Connection, order_id: int, order_no: Optional[str]) -> None:
    conn.execute("UPDATE orders SET order_no = ? WHERE id = ?", (order_no, order_id))


def update_status(conn: sqlite3.Connection, order_id: int, status: OrderStatus) -> None:
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status.value, order_id))


def update_status_and_forwarding(
    conn: sqlite3.Connection,
    order_id: int,
    status: OrderStatus,
    forwarding: Dict[str, Any],
) -> None:
    conn.execute(
        "UPDATE orders SET status = ?, forwarding = ? WHERE id = ?",
        (status.value, encode_json(forwarding), order_id),
    )


def update_actual_weight_and_status(
    conn: sqlite3.Connection,
    order_id: int,
    actual_weight: float,
    status: OrderStatus,
) -> None:
    conn.execute(
        "UPDATE orders SET actual_weight = ?, status = ? WHERE id = ?",
        (actual_weight, status.value, order_id),
    )


def update_weights(
    conn: sqlite3.Connection,
    order_id: int,
    actual_weight: Optional[float] = None,
    volumetric_weight: Optional[float] = None,
    forwarding: Optional[Dict[str, Any]] = None,
) -> None:
    if actual_weight is not None:
        conn.execute(
            "UPDATE orders SET actual_weight = ?, forwarding = ? WHERE id = ?",
            (actual_weight, encode_json(forwarding), order_id),
        )
    else:
        conn.execute(
            "UPDATE orders SET volumetric_weight = ?, forwarding = ? WHERE id = ?",
            (volumetric_weight, encode_json(forwarding), order_id),
        )


def update_final_price(conn: sqlite3.Connection, order_id: int, final_price: float) -> None:
    conn.execute("UPDATE orders SET final_price = ? WHERE id = ?", (final_price, order_id))


def get_draft_order(conn: sqlite3.Connection, customer_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM orders WHERE customer_id = ? AND status = ? ORDER BY id LIMIT 1",
        (customer_id, OrderStatus.DRAFT.value),
    ).fetchone()


def migrate_order_parcels(conn: sqlite3.Connection) -> None:
    orders = conn.execute("SELECT id, parcel_ids FROM orders ORDER BY id").fetchall()
    for order in orders:
        legacy_ids = [int(pid) for pid in decode_json(order["parcel_ids"]) or []]
        if len(legacy_ids) != len(set(legacy_ids)):
            raise RuntimeError(f"order {order['id']} has duplicate legacy parcel IDs")
        relation_ids = get_order_parcel_ids(conn, order["id"])
        if relation_ids:
            sync_legacy_parcel_ids(conn, order["id"])
            continue
        for parcel_id in legacy_ids:
            if is_parcel_assigned(conn, parcel_id):
                raise RuntimeError(f"parcel {parcel_id} is assigned to multiple legacy orders")
        created_at = order["created_at"] if "created_at" in order.keys() else None
        add_order_parcels(conn, order["id"], legacy_ids, created_at or utc_now_iso())
