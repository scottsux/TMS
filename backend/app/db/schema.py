"""SQLite schema bootstrap, compatibility migration, and demo seed data."""

from .. import config
from ..core.security import make_password_hash
from ..models.enums import ParcelStatus, UserRole
from ..repositories.order_repository import migrate_order_parcels
from .connection import get_conn


def init_db() -> None:
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


def seed() -> None:
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
