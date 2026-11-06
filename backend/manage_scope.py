"""Local administrative commands for tenant and warehouse assignments.

Run with ``backend/.venv/bin/python -m backend.manage_scope``. This is a local
operator utility, not an HTTP API and must not be exposed to Agent Tools.
"""

import argparse
import sqlite3
from typing import Sequence

from .app.db.connection import get_conn
from .app.db.schema import init_db


def _require_tenant(conn: sqlite3.Connection, tenant_id: int) -> None:
    if conn.execute("SELECT 1 FROM tenants WHERE id = ?", (tenant_id,)).fetchone() is None:
        raise ValueError(f"tenant {tenant_id} does not exist")


def _require_warehouse(conn: sqlite3.Connection, warehouse_id: int, tenant_id: int) -> None:
    if conn.execute(
        "SELECT 1 FROM warehouses WHERE id = ? AND tenant_id = ?",
        (warehouse_id, tenant_id),
    ).fetchone() is None:
        raise ValueError(f"warehouse {warehouse_id} does not belong to tenant {tenant_id}")


def create_tenant(name: str) -> int:
    conn = get_conn()
    try:
        existing = conn.execute("SELECT id FROM tenants WHERE name = ?", (name,)).fetchone()
        if existing:
            return int(existing["id"])
        cursor = conn.execute("INSERT INTO tenants (name) VALUES (?)", (name,))
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def create_warehouse(tenant_id: int, name: str) -> int:
    conn = get_conn()
    try:
        _require_tenant(conn, tenant_id)
        existing = conn.execute(
            "SELECT id FROM warehouses WHERE tenant_id = ? AND name = ?",
            (tenant_id, name),
        ).fetchone()
        if existing:
            return int(existing["id"])
        cursor = conn.execute(
            "INSERT INTO warehouses (tenant_id, name) VALUES (?, ?)",
            (tenant_id, name),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def assign_customer(customer_id: int, tenant_id: int, warehouse_id: int) -> None:
    conn = get_conn()
    try:
        _require_tenant(conn, tenant_id)
        _require_warehouse(conn, warehouse_id, tenant_id)
        customer = conn.execute("SELECT 1 FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if customer is None:
            raise ValueError(f"customer {customer_id} does not exist")
        conn.execute(
            "UPDATE customers SET tenant_id = ?, warehouse_id = ? WHERE id = ?",
            (tenant_id, warehouse_id, customer_id),
        )
        conn.execute(
            "UPDATE users SET tenant_id = ?, warehouse_id = ? WHERE role = 'customer' AND customer_id = ?",
            (tenant_id, warehouse_id, customer_id),
        )
        conn.commit()
    finally:
        conn.close()


def assign_user(
    email: str,
    role: str,
    tenant_id: int,
    warehouse_id: int | None = None,
    customer_id: int | None = None,
) -> None:
    if role not in {"customer", "staff", "operator"}:
        raise ValueError("role must be customer, staff, or operator")
    if role == "operator" and warehouse_id is None:
        raise ValueError("operator assignment requires --warehouse-id")
    if role == "customer" and customer_id is None:
        raise ValueError("customer assignment requires --customer-id")
    if role != "customer" and customer_id is not None:
        raise ValueError("--customer-id is only valid for a customer user")

    conn = get_conn()
    try:
        _require_tenant(conn, tenant_id)
        if warehouse_id is not None:
            _require_warehouse(conn, warehouse_id, tenant_id)
        user = conn.execute("SELECT id FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()
        if user is None:
            raise ValueError(f"user {email} does not exist")
        if role == "customer":
            customer = conn.execute(
                "SELECT tenant_id, warehouse_id FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            if customer is None:
                raise ValueError(f"customer {customer_id} does not exist")
            if customer["tenant_id"] != tenant_id or customer["warehouse_id"] != warehouse_id:
                raise ValueError("customer user scope must match the assigned customer")
        conn.execute(
            "UPDATE users SET role = ?, customer_id = ?, tenant_id = ?, warehouse_id = ? WHERE id = ?",
            (role, customer_id, tenant_id, warehouse_id, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local TMS tenant and warehouse assignments")
    commands = parser.add_subparsers(dest="command", required=True)

    tenant = commands.add_parser("create-tenant", help="create or look up a company tenant")
    tenant.add_argument("--name", required=True)

    warehouse = commands.add_parser("create-warehouse", help="create or look up a tenant warehouse")
    warehouse.add_argument("--tenant-id", required=True, type=int)
    warehouse.add_argument("--name", required=True)

    customer = commands.add_parser("assign-customer", help="assign a customer and its login to a warehouse")
    customer.add_argument("--customer-id", required=True, type=int)
    customer.add_argument("--tenant-id", required=True, type=int)
    customer.add_argument("--warehouse-id", required=True, type=int)

    user = commands.add_parser("assign-user", help="assign staff/operator/customer login scope")
    user.add_argument("--email", required=True)
    user.add_argument("--role", required=True, choices=["customer", "staff", "operator"])
    user.add_argument("--tenant-id", required=True, type=int)
    user.add_argument("--warehouse-id", type=int)
    user.add_argument("--customer-id", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    init_db()
    try:
        if args.command == "create-tenant":
            print(create_tenant(args.name))
        elif args.command == "create-warehouse":
            print(create_warehouse(args.tenant_id, args.name))
        elif args.command == "assign-customer":
            assign_customer(args.customer_id, args.tenant_id, args.warehouse_id)
            print("customer assignment updated")
        else:
            assign_user(args.email, args.role, args.tenant_id, args.warehouse_id, args.customer_id)
            print("user assignment updated")
    except (sqlite3.IntegrityError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
