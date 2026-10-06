import json
import sqlite3
from typing import Any, List, Optional

from ..core.security import utc_now_iso


def record(
    conn: sqlite3.Connection,
    order_id: int,
    action: str,
    actor_id: int,
    before_value: Optional[dict[str, Any]] = None,
    after_value: Optional[dict[str, Any]] = None,
    reason: Optional[str] = None,
    exception_id: Optional[int] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO order_audits (
            order_id, exception_id, action, actor_id, created_at, before_value, after_value, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            exception_id,
            action,
            actor_id,
            utc_now_iso(),
            json.dumps(before_value, ensure_ascii=False) if before_value is not None else None,
            json.dumps(after_value, ensure_ascii=False) if after_value is not None else None,
            reason,
        ),
    )


def list_for_order(conn: sqlite3.Connection, order_id: int) -> List[sqlite3.Row]:
    return conn.execute(
        """
        SELECT a.*, u.email AS actor_email
        FROM order_audits a
        JOIN users u ON u.id = a.actor_id
        WHERE a.order_id = ?
        ORDER BY a.id DESC
        """,
        (order_id,),
    ).fetchall()
