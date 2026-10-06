import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.permissions import require_permission
from ..schemas import ReadyNotify
from ..services import notification_service


router = APIRouter()


@router.post("/notify/ready_to_ship")
def notify_ready(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("notification:view")),
):
    return notification_service.notify_ready(body, user)


@router.post("/notify/shipped")
def notify_shipped(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("order:ship")),
):
    return notification_service.notify_shipped(body, user)


@router.post("/notify/ready_to_pack")
def notify_ready_to_pack(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("notification:create")),
):
    return notification_service.notify_ready_to_pack(body, user)


@router.get("/notifications")
def get_notifications(
    type: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("notification:view")),
):
    return notification_service.get_notifications(user=user, type=type, customer_id=customer_id)


@router.delete("/notifications")
def clear_notifications(
    type: Optional[str] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("notification:clear")),
):
    return notification_service.clear_notifications(user=user, type=type)
