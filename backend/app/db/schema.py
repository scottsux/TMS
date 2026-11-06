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
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS warehouses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(tenant_id, name),
                FOREIGN KEY(tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tenant_id INTEGER REFERENCES tenants(id),
                warehouse_id INTEGER REFERENCES warehouses(id)
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                customer_id INTEGER,
                tenant_id INTEGER REFERENCES tenants(id),
                warehouse_id INTEGER REFERENCES warehouses(id),
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
        _migrate_tenant_warehouse_scope(conn)
        migrate_order_parcels(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate_tenant_warehouse_scope(conn) -> None:
    """Add tenant/warehouse ownership to existing MVP databases safely."""
    customer_columns = {row["name"] for row in conn.execute("PRAGMA table_info(customers)")}
    if "tenant_id" not in customer_columns:
        conn.execute("ALTER TABLE customers ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)")
    if "warehouse_id" not in customer_columns:
        conn.execute("ALTER TABLE customers ADD COLUMN warehouse_id INTEGER REFERENCES warehouses(id)")

    user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "tenant_id" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)")
    if "warehouse_id" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN warehouse_id INTEGER REFERENCES warehouses(id)")

    tenant = conn.execute("SELECT id FROM tenants ORDER BY id LIMIT 1").fetchone()
    if tenant is None:
        conn.execute("INSERT INTO tenants (name) VALUES (?)", ("Default Company",))
        tenant_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        tenant_id = tenant["id"]
    warehouse = conn.execute(
        "SELECT id FROM warehouses WHERE tenant_id = ? ORDER BY id LIMIT 1", (tenant_id,)
    ).fetchone()
    if warehouse is None:
        conn.execute("INSERT INTO warehouses (tenant_id, name) VALUES (?, ?)", (tenant_id, "Default Warehouse"))
        warehouse_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        warehouse_id = warehouse["id"]

    conn.execute(
        "UPDATE customers SET tenant_id = ?, warehouse_id = ? WHERE tenant_id IS NULL",
        (tenant_id, warehouse_id),
    )
    for customer_tenant in conn.execute(
        "SELECT DISTINCT tenant_id FROM customers WHERE warehouse_id IS NULL AND tenant_id IS NOT NULL"
    ).fetchall():
        customer_tenant_id = customer_tenant["tenant_id"]
        customer_warehouse = conn.execute(
            "SELECT id FROM warehouses WHERE tenant_id = ? ORDER BY id LIMIT 1",
            (customer_tenant_id,),
        ).fetchone()
        if customer_warehouse is None:
            conn.execute(
                "INSERT INTO warehouses (tenant_id, name) VALUES (?, ?)",
                (customer_tenant_id, "Default Warehouse"),
            )
            customer_warehouse_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            customer_warehouse_id = customer_warehouse["id"]
        conn.execute(
            "UPDATE customers SET warehouse_id = ? WHERE tenant_id = ? AND warehouse_id IS NULL",
            (customer_warehouse_id, customer_tenant_id),
        )
    conn.execute(
        "UPDATE users SET tenant_id = COALESCE(tenant_id, ?), "
        "warehouse_id = COALESCE(warehouse_id, (SELECT id FROM warehouses "
        "WHERE tenant_id = COALESCE(users.tenant_id, ?) ORDER BY id LIMIT 1)) "
        "WHERE role != 'customer' AND (tenant_id IS NULL OR warehouse_id IS NULL)",
        (tenant_id, tenant_id),
    )
    conn.execute(
        """UPDATE users SET tenant_id = (SELECT tenant_id FROM customers WHERE customers.id = users.customer_id),
           warehouse_id = (SELECT warehouse_id FROM customers WHERE customers.id = users.customer_id)
           WHERE role = 'customer' AND customer_id IS NOT NULL"""
    )
    for user_tenant in conn.execute(
        "SELECT DISTINCT tenant_id FROM users WHERE warehouse_id IS NULL AND tenant_id IS NOT NULL"
    ).fetchall():
        user_tenant_id = user_tenant["tenant_id"]
        assigned_warehouse = conn.execute(
            "SELECT id FROM warehouses WHERE tenant_id = ? ORDER BY id LIMIT 1",
            (user_tenant_id,),
        ).fetchone()
        if assigned_warehouse is not None:
            conn.execute(
                "UPDATE users SET warehouse_id = ? WHERE tenant_id = ? AND warehouse_id IS NULL",
                (assigned_warehouse["id"], user_tenant_id),
            )

    conn.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS customers_scope_insert
        BEFORE INSERT ON customers
        WHEN NEW.tenant_id IS NULL OR NEW.warehouse_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM warehouses
            WHERE id = NEW.warehouse_id AND tenant_id = NEW.tenant_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'customer warehouse must belong to customer tenant');
        END;

        CREATE TRIGGER IF NOT EXISTS customers_scope_update
        BEFORE UPDATE OF tenant_id, warehouse_id ON customers
        WHEN NEW.tenant_id IS NULL OR NEW.warehouse_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM warehouses
            WHERE id = NEW.warehouse_id AND tenant_id = NEW.tenant_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'customer warehouse must belong to customer tenant');
        END;

        CREATE TRIGGER IF NOT EXISTS users_scope_insert
        BEFORE INSERT ON users
        WHEN NEW.tenant_id IS NULL
          OR (NEW.warehouse_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM warehouses
              WHERE id = NEW.warehouse_id AND tenant_id = NEW.tenant_id
          ))
          OR (NEW.role = 'operator' AND NEW.warehouse_id IS NULL)
          OR (NEW.role = 'customer' AND NOT EXISTS (
              SELECT 1 FROM customers
              WHERE id = NEW.customer_id AND tenant_id = NEW.tenant_id
                AND warehouse_id = NEW.warehouse_id
          ))
        BEGIN
            SELECT RAISE(ABORT, 'user scope must match tenant and warehouse');
        END;

        CREATE TRIGGER IF NOT EXISTS users_scope_update
        BEFORE UPDATE OF customer_id, role, tenant_id, warehouse_id ON users
        WHEN NEW.tenant_id IS NULL
          OR (NEW.warehouse_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM warehouses
              WHERE id = NEW.warehouse_id AND tenant_id = NEW.tenant_id
          ))
          OR (NEW.role = 'operator' AND NEW.warehouse_id IS NULL)
          OR (NEW.role = 'customer' AND NOT EXISTS (
              SELECT 1 FROM customers
              WHERE id = NEW.customer_id AND tenant_id = NEW.tenant_id
                AND warehouse_id = NEW.warehouse_id
          ))
        BEGIN
            SELECT RAISE(ABORT, 'user scope must match tenant and warehouse');
        END;
        """
    )


def seed() -> None:
    conn = get_conn()
    try:
        if conn.execute("SELECT COUNT(*) AS count FROM customers").fetchone()["count"]:
            return

        tenant_id = conn.execute("SELECT id FROM tenants ORDER BY id LIMIT 1").fetchone()["id"]
        warehouse_id = conn.execute(
            "SELECT id FROM warehouses WHERE tenant_id = ? ORDER BY id LIMIT 1", (tenant_id,)
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO customers (name, tenant_id, warehouse_id) VALUES (?, ?, ?)",
            ("Acme", tenant_id, warehouse_id),
        )
        conn.execute(
            "INSERT INTO customers (name, tenant_id, warehouse_id) VALUES (?, ?, ?)",
            ("Globex", tenant_id, warehouse_id),
        )
        conn.execute(
            """INSERT INTO users (email, password_hash, role, customer_id, tenant_id, warehouse_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("customer@example.com", make_password_hash("demo123"), UserRole.customer.value, 1, tenant_id, warehouse_id),
        )
        conn.execute(
            """INSERT INTO users (email, password_hash, role, customer_id, tenant_id, warehouse_id)
               VALUES (?, ?, ?, NULL, ?, ?)""",
            ("staff@example.com", make_password_hash("demo123"), UserRole.staff.value, tenant_id, warehouse_id),
        )
        conn.execute(
            """INSERT INTO users (email, password_hash, role, customer_id, tenant_id, warehouse_id)
               VALUES (?, ?, ?, NULL, ?, ?)""",
            ("operator@example.com", make_password_hash("demo123"), UserRole.operator.value, tenant_id, warehouse_id),
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
