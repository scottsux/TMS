import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.permissions import require_permission
from ..models.enums import ExceptionStatus
from ..schemas import OrderExceptionCreate, OrderExceptionResolve
from ..services import exception_service


router = APIRouter()


@router.post("/orders/{oid}/exceptions")
def create_order_exception(
    oid: int,
    body: OrderExceptionCreate,
    user: sqlite3.Row = Depends(require_permission("exception:create")),
):
    return exception_service.create_order_exception(oid, body, user)


@router.get("/orders/{oid}/exceptions")
def list_order_exceptions(
    oid: int,
    user: sqlite3.Row = Depends(require_permission("exception:view")),
):
    return exception_service.list_order_exceptions(oid, user)


@router.get("/exceptions")
def list_exceptions(
    status: Optional[ExceptionStatus] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("exception:view")),
):
    return exception_service.list_exceptions(user=user, status=status)


@router.patch("/exceptions/{eid}/resolve")
def resolve_order_exception(
    eid: int,
    body: OrderExceptionResolve,
    user: sqlite3.Row = Depends(require_permission("exception:resolve")),
):
    return exception_service.resolve_order_exception(eid, body, user)


@router.get("/orders/{oid}/audits")
def list_order_audits(
    oid: int,
    user: sqlite3.Row = Depends(require_permission("audit:view")),
):
    return exception_service.list_order_audits(oid, user)
