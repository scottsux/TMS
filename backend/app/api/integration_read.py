import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.permissions import require_permission
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus
from ..schemas.integration_read import (
    IntegrationExceptionRead,
    IntegrationOrderRead,
    IntegrationParcelRead,
)
from ..services import exception_service, order_service, parcel_service


router = APIRouter(prefix="/integration/v1", tags=["controlled-read"])


@router.get("/parcels", response_model=list[IntegrationParcelRead])
def list_integration_parcels(
    customer_id: Optional[int] = Query(default=None, ge=1),
    status: Optional[ParcelStatus] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: sqlite3.Row = Depends(require_permission("parcel:view")),
):
    return parcel_service.list_parcels(
        user=user,
        customer_id=customer_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/parcels/{pid}", response_model=IntegrationParcelRead)
def get_integration_parcel(
    pid: int,
    user: sqlite3.Row = Depends(require_permission("parcel:view")),
):
    return parcel_service.get_parcel(pid, user)


@router.get("/orders", response_model=list[IntegrationOrderRead])
def list_integration_orders(
    customer_id: Optional[int] = Query(default=None, ge=1),
    status: Optional[OrderStatus] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: sqlite3.Row = Depends(require_permission("order:view")),
):
    return order_service.list_orders(
        user=user,
        customer_id=customer_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/orders/{oid}", response_model=IntegrationOrderRead)
def get_integration_order(
    oid: int,
    user: sqlite3.Row = Depends(require_permission("order:view")),
):
    return order_service.get_order(oid, user)


@router.get("/exceptions", response_model=list[IntegrationExceptionRead])
def list_integration_exceptions(
    status: Optional[ExceptionStatus] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("exception:view")),
):
    return exception_service.list_exceptions(user=user, status=status)


@router.get("/exceptions/{eid}", response_model=IntegrationExceptionRead)
def get_integration_exception(
    eid: int,
    user: sqlite3.Row = Depends(require_permission("exception:view")),
):
    return exception_service.get_exception(eid, user)
