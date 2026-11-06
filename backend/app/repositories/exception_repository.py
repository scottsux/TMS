import sqlite3
from typing import Any, List, Optional

from ..models.enums import ExceptionStatus


def insert_exception(
    conn: sqlite3.Connection,
    order_id: int,
    exception_type: str,
    reason: str,
    created_by: int,
    created_at: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO order_exceptions (order_id, type, status, reason, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (order_id, exception_type, ExceptionStatus.OPEN.value, reason, created_by, created_at),
    )
    return int(cursor.lastrowid)


def list_for_order(conn: sqlite3.Connection, order_id: int) -> List[sqlite3.Row]:
    return conn.execute(
        """
        SELECT e.*, creator.email AS created_by_email, resolver.email AS resolved_by_email
        FROM order_exceptions e
        JOIN users creator ON creator.id = e.created_by
        LEFT JOIN users resolver ON resolver.id = e.resolved_by
        WHERE e.order_id = ?
        ORDER BY e.id DESC
        """,
        (order_id,),
    ).fetchall()


def list_all(
    conn: sqlite3.Connection,
    customer_id: Optional[int] = None,
    status: Optional[ExceptionStatus] = None,
    tenant_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> List[sqlite3.Row]:
    sql = """
        SELECT e.*, o.customer_id, o.order_no, creator.email AS created_by_email,
               resolver.email AS resolved_by_email
        FROM order_exceptions e
        JOIN orders o ON o.id = e.order_id
        JOIN customers c ON c.id = o.customer_id
        JOIN users creator ON creator.id = e.created_by
        LEFT JOIN users resolver ON resolver.id = e.resolved_by
        WHERE 1 = 1
    """
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND o.customer_id = ?"
        params.append(customer_id)
    if tenant_id is not None:
        sql += " AND c.tenant_id = ?"
        params.append(tenant_id)
    if warehouse_id is not None:
        sql += " AND c.warehouse_id = ?"
        params.append(warehouse_id)
    if status is not None:
        sql += " AND e.status = ?"
        params.append(status.value)
    sql += " ORDER BY CASE e.status WHEN 'OPEN' THEN 0 ELSE 1 END, e.id DESC"
    return conn.execute(sql, params).fetchall()


def has_open(conn: sqlite3.Connection, order_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM order_exceptions WHERE order_id = ? AND status = ?",
        (order_id, ExceptionStatus.OPEN.value),
    ).fetchone() is not None


def get_by_id(conn: sqlite3.Connection, exception_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM order_exceptions WHERE id = ?", (exception_id,)).fetchone()


def resolve(
    conn: sqlite3.Connection,
    exception_id: int,
    resolved_by: int,
    resolution_note: str,
    resolved_at: str,
) -> None:
    conn.execute(
        """
        UPDATE order_exceptions
        SET status = ?, resolved_by = ?, resolution_note = ?, resolved_at = ?
        WHERE id = ?
        """,
        (
            ExceptionStatus.RESOLVED.value,
            resolved_by,
            resolution_note,
            resolved_at,
            exception_id,
        ),
    )
