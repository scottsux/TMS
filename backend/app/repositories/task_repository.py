import sqlite3
from typing import Any, List, Optional


def get_task_by_id(conn: sqlite3.Connection, task_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def list_tasks(
    conn: sqlite3.Connection,
    customer_id: Optional[int] = None,
    order_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> List[sqlite3.Row]:
    sql = """
        SELECT t.*
        FROM tasks t
        JOIN orders o ON o.id = t.order_id
        JOIN customers c ON c.id = o.customer_id
        WHERE 1 = 1
    """
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND o.customer_id = ?"
        params.append(customer_id)
    if order_id is not None:
        sql += " AND t.order_id = ?"
        params.append(order_id)
    if tenant_id is not None:
        sql += " AND c.tenant_id = ?"
        params.append(tenant_id)
    if warehouse_id is not None:
        sql += " AND c.warehouse_id = ?"
        params.append(warehouse_id)
    sql += " ORDER BY t.id DESC"
    return conn.execute(sql, params).fetchall()


def mark_started(conn: sqlite3.Connection, task_id: int, status: str) -> None:
    conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))


def update_completion(
    conn: sqlite3.Connection,
    task_id: int,
    actual_weight: Optional[float],
    status: str,
) -> None:
    conn.execute(
        "UPDATE tasks SET actual_weight = ?, status = ? WHERE id = ?",
        (actual_weight, status, task_id),
    )


def mark_done_for_order(conn: sqlite3.Connection, order_id: int, status: str) -> None:
    conn.execute("UPDATE tasks SET status = ? WHERE order_id = ?", (status, order_id))
