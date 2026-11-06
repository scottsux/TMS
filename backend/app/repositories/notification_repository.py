import sqlite3
from typing import Any, Dict, List, Optional

from ..repositories.common import decode_json, encode_json
from ..core.security import utc_now_iso


def upsert(
    conn: sqlite3.Connection,
    notification_type: str,
    customer_id: int,
    payload: Dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO notifications (type, customer_id, payload, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(type, customer_id) DO UPDATE SET
            payload = excluded.payload,
            created_at = excluded.created_at
        """,
        (notification_type, customer_id, encode_json(payload), utc_now_iso()),
    )


def list_notifications(
    conn: sqlite3.Connection,
    notification_type: Optional[str] = None,
    customer_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> List[sqlite3.Row]:
    sql = "SELECT n.* FROM notifications n JOIN customers c ON c.id = n.customer_id WHERE 1 = 1"
    params: list[Any] = []
    if notification_type:
        sql += " AND type = ?"
        params.append(notification_type)
    if customer_id is not None:
        sql += " AND n.customer_id = ?"
        params.append(customer_id)
    if tenant_id is not None:
        sql += " AND c.tenant_id = ?"
        params.append(tenant_id)
    if warehouse_id is not None:
        sql += " AND c.warehouse_id = ?"
        params.append(warehouse_id)
    sql += " ORDER BY created_at DESC"
    return conn.execute(sql, params).fetchall()


def delete_notifications(
    conn: sqlite3.Connection,
    notification_type: Optional[str] = None,
    tenant_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> None:
    sql = "DELETE FROM notifications WHERE customer_id IN (SELECT id FROM customers WHERE 1 = 1"
    params: list[Any] = []
    if tenant_id is not None:
        sql += " AND tenant_id = ?"
        params.append(tenant_id)
    if warehouse_id is not None:
        sql += " AND warehouse_id = ?"
        params.append(warehouse_id)
    sql += ")"
    if notification_type:
        sql += " AND type = ?"
        params.append(notification_type)
    conn.execute(sql, params)
