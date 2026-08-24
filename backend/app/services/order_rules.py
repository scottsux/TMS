import json
import sqlite3
from typing import Any, Optional

from fastapi import HTTPException

from ..core.security import utc_now_iso
from ..models.enums import ExceptionStatus, ExceptionType, OrderStatus, UserRole


def price_formula(actual_weight: float, rate_per_kg: float, extra_fee: float) -> float:
    return round(actual_weight * rate_per_kg + extra_fee, 2)


def record_order_audit(
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


def ensure_no_open_exceptions(conn: sqlite3.Connection, order_id: int) -> None:
    if conn.execute(
        "SELECT 1 FROM order_exceptions WHERE order_id = ? AND status = ?",
        (order_id, ExceptionStatus.OPEN.value),
    ).fetchone():
        raise HTTPException(status_code=400, detail="order has unresolved exceptions")


def ensure_weight_update_allowed(order: sqlite3.Row, user: sqlite3.Row) -> None:
    status, role = OrderStatus(order["status"]), UserRole(user["role"])
    if role == UserRole.operator and status == OrderStatus.PACKING:
        return
    if role == UserRole.staff and status in {OrderStatus.PACKING, OrderStatus.READY_TO_SHIP}:
        return
    raise HTTPException(status_code=400, detail="weight cannot be updated in the current order status")


def exception_types_for_role(role: UserRole) -> set[ExceptionType]:
    if role == UserRole.customer:
        return {ExceptionType.CUSTOMER_CANCEL, ExceptionType.ADDRESS_ERROR, ExceptionType.PRICE_DISPUTE}
    if role == UserRole.operator:
        return {ExceptionType.DAMAGED, ExceptionType.PROHIBITED}
    return set(ExceptionType)
