import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import Depends, File, HTTPException, Query, UploadFile

from .. import config
from ..core.permissions import ensure_customer_scope, require_permission
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def list_tasks(
    order_id: Optional[int] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("task:view")),
):
    conn = get_conn()
    try:
        sql = """
            SELECT t.*
            FROM tasks t
            JOIN orders o ON o.id = t.order_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if user["role"] == UserRole.customer.value:
            sql += " AND o.customer_id = ?"
            params.append(user["customer_id"])
        if order_id is not None:
            sql += " AND t.order_id = ?"
            params.append(order_id)
        sql += " ORDER BY t.id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [row_to_task(row) for row in rows]
    finally:
        conn.close()


def start_task(tid: int, user: sqlite3.Row = Depends(require_permission("task:start"))):
    conn = get_conn()
    try:
        task = get_task_or_404(conn, tid)
        if task["status"] != TaskStatus.TODO.value:
            raise HTTPException(status_code=400, detail="task is not in TODO status")
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (TaskStatus.IN_PROGRESS.value, tid))
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (OrderStatus.PACKING.value, task["order_id"]))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def complete_task(
    tid: int,
    body: TaskComplete,
    user: sqlite3.Row = Depends(require_permission("task:complete")),
):
    conn = get_conn()
    try:
        task = get_task_or_404(conn, tid)
        if task["status"] != TaskStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=400, detail="task is not in progress")
        order = get_order_or_404(conn, task["order_id"])
        actual_weight = float(body.actual_weight) if body.actual_weight is not None else task["actual_weight"]
        conn.execute(
            "UPDATE tasks SET actual_weight = ?, status = ? WHERE id = ?",
            (actual_weight, TaskStatus.IN_PROGRESS.value, tid),
        )
        conn.execute(
            "UPDATE orders SET actual_weight = ?, status = ? WHERE id = ?",
            (actual_weight if actual_weight is not None else order["actual_weight"], OrderStatus.READY_TO_SHIP.value, task["order_id"]),
        )
        if actual_weight is not None and float(order["actual_weight"] or 0) != actual_weight:
            record_order_audit(
                conn,
                task["order_id"],
                "weight:actual_update",
                user["id"],
                {"actual_weight": float(order["actual_weight"] or 0)},
                {"actual_weight": actual_weight},
                "packing completion",
            )
        now = utc_now_iso()
        for pid in get_order_parcel_ids(conn, task["order_id"]):
            conn.execute(
                "UPDATE parcels SET status = ?, packed_at = ? WHERE id = ?",
                (ParcelStatus.PACKED.value, now, pid),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

