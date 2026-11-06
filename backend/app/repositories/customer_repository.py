import sqlite3
from typing import Any, List, Optional


def get_customer_by_id(conn: sqlite3.Connection, customer_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()


def list_customers(
    conn: sqlite3.Connection,
    page: int = 1,
    page_size: int = 50,
    query: Optional[str] = None,
    tenant_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> List[sqlite3.Row]:
    sql = "SELECT * FROM customers WHERE 1 = 1"
    params: list[Any] = []
    if query:
        sql += " AND lower(name) LIKE ?"
        params.append(f"%{query.lower()}%")
    if tenant_id is not None:
        sql += " AND tenant_id = ?"
        params.append(tenant_id)
    if warehouse_id is not None:
        sql += " AND warehouse_id = ?"
        params.append(warehouse_id)
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params.extend([page_size, max(0, (page - 1) * page_size)])
    return conn.execute(sql, params).fetchall()
