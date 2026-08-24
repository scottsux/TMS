import json
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .. import config
from ..db.connection import get_conn
from ..core.security import make_password_hash, utc_now_iso
from ..models.enums import OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..schemas import Order, Parcel, Task

def encode_json(value: Optional[Dict[str, Any]]) -> Optional[str]:
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


def fetch_customer_name(conn: sqlite3.Connection, customer_id: int) -> Optional[str]:
    row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
    return row["name"] if row else None


def ensure_customer_exists(conn: sqlite3.Connection, customer_id: int):
    if not conn.execute("SELECT 1 FROM customers WHERE id = ?", (customer_id,)).fetchone():
        raise HTTPException(status_code=400, detail="customer not found")


def ensure_unique_tracking(conn: sqlite3.Connection, tracking: str, exclude_id: Optional[int] = None):
    sql = "SELECT id FROM parcels WHERE lower(tracking_number) = lower(?)"
    params: list[Any] = [tracking]
    if exclude_id is not None:
        sql += " AND id != ?"
        params.append(exclude_id)
    row = conn.execute(sql, params).fetchone()
    if row:
        raise HTTPException(status_code=400, detail="tracking_number must be unique")


def ensure_transition(old: ParcelStatus, new: ParcelStatus):
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


def get_order_parcel_ids(conn: sqlite3.Connection, order_id: int) -> List[int]:
    rows = conn.execute(
        "SELECT parcel_id FROM order_parcels WHERE order_id = ? ORDER BY rowid", (order_id,)
    ).fetchall()
    return [row["parcel_id"] for row in rows]


def sync_legacy_order_parcel_ids(conn: sqlite3.Connection, order_id: int) -> List[int]:
    parcel_ids = get_order_parcel_ids(conn, order_id)
    conn.execute("UPDATE orders SET parcel_ids = ? WHERE id = ?", (encode_json(parcel_ids), order_id))
    return parcel_ids


def is_parcel_assigned(conn: sqlite3.Connection, pid: int, exclude_order_id: Optional[int] = None) -> bool:
    sql = "SELECT 1 FROM order_parcels WHERE parcel_id = ?"
    params: list[Any] = [pid]
    if exclude_order_id is not None:
        sql += " AND order_id != ?"
        params.append(exclude_order_id)
    return conn.execute(sql, params).fetchone() is not None


def validate_order_parcels(
    conn: sqlite3.Connection,
    customer_id: int,
    parcel_ids: List[int],
    exclude_order_id: Optional[int] = None,
):
    if len(parcel_ids) != len(set(parcel_ids)):
        raise HTTPException(status_code=400, detail="parcel_ids must not contain duplicates")
    for pid in parcel_ids:
        parcel = get_parcel_or_404(conn, pid)
        if parcel["customer_id"] != customer_id:
            raise HTTPException(status_code=400, detail=f"parcel {pid} belongs to a different customer")
        if is_parcel_assigned(conn, pid, exclude_order_id=exclude_order_id):
            raise HTTPException(status_code=400, detail=f"parcel {pid} already in another order")


def add_order_parcels(conn: sqlite3.Connection, order_id: int, parcel_ids: List[int]):
    if parcel_ids:
        conn.executemany(
            "INSERT INTO order_parcels (order_id, parcel_id, created_at) VALUES (?, ?, ?)",
            [(order_id, pid, utc_now_iso()) for pid in parcel_ids],
        )


def remove_order_parcels(conn: sqlite3.Connection, order_id: int, parcel_ids: List[int]):
    if parcel_ids:
        placeholders = ", ".join("?" for _ in parcel_ids)
        conn.execute(
            f"DELETE FROM order_parcels WHERE order_id = ? AND parcel_id IN ({placeholders})",
            [order_id, *parcel_ids],
        )


def migrate_order_parcels(conn: sqlite3.Connection):
    orders = conn.execute("SELECT id, parcel_ids FROM orders ORDER BY id").fetchall()
    for order in orders:
        legacy_ids = [int(pid) for pid in decode_json(order["parcel_ids"]) or []]
        if len(legacy_ids) != len(set(legacy_ids)):
            raise RuntimeError(f"order {order['id']} has duplicate legacy parcel IDs")
        relation_ids = get_order_parcel_ids(conn, order["id"])
        if relation_ids:
            sync_legacy_order_parcel_ids(conn, order["id"])
            continue
        for pid in legacy_ids:
            if is_parcel_assigned(conn, pid):
                raise RuntimeError(f"parcel {pid} is assigned to multiple legacy orders")
        add_order_parcels(conn, order["id"], legacy_ids)


def get_parcel_or_404(conn: sqlite3.Connection, pid: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT p.*, c.name AS customer_name
        FROM parcels p
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE p.id = ?
        """,
        (pid,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="parcel not found")
    return row


def get_order_or_404(conn: sqlite3.Connection, oid: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT o.*, c.name AS customer_name
        FROM orders o
        LEFT JOIN customers c ON c.id = o.customer_id
        WHERE o.id = ?
        """,
        (oid,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="order not found")
    return row


def get_task_or_404(conn: sqlite3.Connection, tid: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    return row


def create_order_record(
    conn: sqlite3.Connection,
    customer_id: int,
    parcel_ids: List[int],
    status: OrderStatus = OrderStatus.DRAFT,
    forwarding: Optional[Dict[str, Any]] = None,
) -> Order:
    validate_order_parcels(conn, customer_id, parcel_ids)
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
    add_order_parcels(conn, order_id, parcel_ids)
    conn.execute(
        "INSERT INTO tasks (order_id, status, actual_weight) VALUES (?, ?, NULL)",
        (order_id, TaskStatus.TODO.value),
    )
    conn.commit()
    return row_to_order(get_order_or_404(conn, order_id), get_order_parcel_ids(conn, order_id))


def init_db():
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                customer_id INTEGER,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                tracking_number TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                courier_company TEXT,
                item_category TEXT,
                item_description TEXT,
                note TEXT,
                arrived_at TEXT,
                pack_requested_at TEXT,
                packed_at TEXT,
                shipped_at TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                parcel_ids TEXT NOT NULL,
                status TEXT NOT NULL,
                actual_weight REAL NOT NULL DEFAULT 0,
                final_price REAL,
                volumetric_weight REAL NOT NULL DEFAULT 0,
                forwarding TEXT,
                created_at TEXT NOT NULL,
                order_no TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS order_parcels (
                order_id INTEGER NOT NULL,
                parcel_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(order_id, parcel_id),
                UNIQUE(parcel_id),
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY(parcel_id) REFERENCES parcels(id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                actual_weight REAL,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(type, customer_id),
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS order_exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                resolved_by INTEGER,
                resolution_note TEXT,
                resolved_at TEXT,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY(created_by) REFERENCES users(id),
                FOREIGN KEY(resolved_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS order_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                exception_id INTEGER,
                action TEXT NOT NULL,
                actor_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                before_value TEXT,
                after_value TEXT,
                reason TEXT,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY(exception_id) REFERENCES order_exceptions(id) ON DELETE SET NULL,
                FOREIGN KEY(actor_id) REFERENCES users(id)
            );
            """
        )
        migrate_order_parcels(conn)
        conn.commit()
    finally:
        conn.close()


def seed():
    conn = get_conn()
    try:
        if conn.execute("SELECT COUNT(*) AS count FROM customers").fetchone()["count"]:
            return

        conn.execute("INSERT INTO customers (name) VALUES (?)", ("Acme",))
        conn.execute("INSERT INTO customers (name) VALUES (?)", ("Globex",))
        conn.execute(
            "INSERT INTO users (email, password_hash, role, customer_id) VALUES (?, ?, ?, ?)",
            ("customer@example.com", make_password_hash("demo123"), UserRole.customer.value, 1),
        )
        conn.execute(
            "INSERT INTO users (email, password_hash, role, customer_id) VALUES (?, ?, ?, NULL)",
            ("staff@example.com", make_password_hash("demo123"), UserRole.staff.value),
        )
        conn.execute(
            "INSERT INTO users (email, password_hash, role, customer_id) VALUES (?, ?, ?, NULL)",
            ("operator@example.com", make_password_hash("demo123"), UserRole.operator.value),
        )
        conn.execute(
            """
            INSERT INTO parcels (
                customer_id, tracking_number, status, courier_company,
                item_category, item_description, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "SF123", ParcelStatus.IN_TRANSIT.value, "SF", "cosmetics", "lipstick", None),
        )
        conn.execute(
            """
            INSERT INTO parcels (
                customer_id, tracking_number, status, courier_company,
                item_category, item_description, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "SF124", ParcelStatus.IN_TRANSIT.value, None, None, None, None),
        )
        conn.commit()
    finally:
        conn.close()
