import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .. import config
from ..core.permissions import ensure_customer_access
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories import order_repository, parcel_repository, task_repository
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def list_tasks(
    user: sqlite3.Row,
    order_id: Optional[int] = None,
):
    conn = get_conn()
    try:
        effective_customer_id = user["customer_id"] if user["role"] == UserRole.customer.value else None
        rows = task_repository.list_tasks(
            conn, effective_customer_id, order_id,
            tenant_id=user["tenant_id"],
            warehouse_id=user["warehouse_id"] if user["role"] == UserRole.operator.value else None,
        )
        return [row_to_task(row) for row in rows]
    finally:
        conn.close()


def start_task(tid: int, user: sqlite3.Row):
    conn = get_conn()
    try:
        task = get_task_or_404(conn, tid)
        order = get_order_or_404(conn, task["order_id"])
        ensure_customer_access(conn, user, order["customer_id"])
        if task["status"] != TaskStatus.TODO.value:
            raise HTTPException(status_code=400, detail="task is not in TODO status")
        task_repository.mark_started(conn, tid, TaskStatus.IN_PROGRESS.value)
        order_repository.update_status(conn, task["order_id"], OrderStatus.PACKING)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def complete_task(
    tid: int,
    body: TaskComplete,
    user: sqlite3.Row,
):
    conn = get_conn()
    try:
        task = get_task_or_404(conn, tid)
        order = get_order_or_404(conn, task["order_id"])
        ensure_customer_access(conn, user, order["customer_id"])
        if task["status"] != TaskStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=400, detail="task is not in progress")
        actual_weight = float(body.actual_weight) if body.actual_weight is not None else task["actual_weight"]
        task_repository.update_completion(conn, tid, actual_weight, TaskStatus.IN_PROGRESS.value)
        order_repository.update_actual_weight_and_status(
            conn,
            task["order_id"],
            actual_weight if actual_weight is not None else order["actual_weight"],
            OrderStatus.READY_TO_SHIP,
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
        for pid in order_repository.get_order_parcel_ids(conn, task["order_id"]):
            parcel_repository.mark_packed(conn, pid, now)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
