import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.permissions import require_permission
from ..models.enums import OrderStatus
from ..schemas import AutoOrderReq, Order, OrderCreate, OrderNoPatch, OrderParcelsPatch
from ..services import order_service


router = APIRouter()


@router.post("/orders", response_model=Order)
def create_order(
    body: OrderCreate,
    user: sqlite3.Row = Depends(require_permission("order:create")),
):
    return order_service.create_order(body, user)


@router.get("/orders", response_model=list[Order])
def list_orders(
    customer_id: Optional[int] = Query(default=None),
    status: Optional[OrderStatus] = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=50),
    user: sqlite3.Row = Depends(require_permission("order:view")),
):
    return order_service.list_orders(
        user=user,
        customer_id=customer_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/orders/{oid}", response_model=Order)
def get_order(
    oid: int,
    user: sqlite3.Row = Depends(require_permission("order:view")),
):
    return order_service.get_order(oid, user)


@router.patch("/orders/{oid}/parcels", response_model=Order)
def patch_order_parcels(
    oid: int,
    body: OrderParcelsPatch,
    user: sqlite3.Row = Depends(require_permission("order:update")),
):
    return order_service.patch_order_parcels(oid, body, user)


@router.patch("/orders/{oid}/order_no")
def patch_order_no(
    oid: int,
    body: OrderNoPatch,
    user: sqlite3.Row = Depends(require_permission("order:update")),
):
    return order_service.patch_order_no(oid, body, user)


@router.post("/orders/auto", response_model=Order)
def auto_create_order(
    req: AutoOrderReq,
    user: sqlite3.Row = Depends(require_permission("order:create")),
):
    return order_service.auto_create_order(req, user)


@router.patch("/orders/{oid}/ship")
def ship_order(
    oid: int,
    user: sqlite3.Row = Depends(require_permission("order:ship")),
):
    return order_service.ship_order(oid, user)
