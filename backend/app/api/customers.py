import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.permissions import require_permission
from ..schemas import Customer
from ..services import order_service


router = APIRouter()


@router.get("/customers", response_model=list[Customer])
def list_customers(
    page: int = Query(default=1),
    page_size: int = Query(default=50),
    q: Optional[str] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("customer:view")),
):
    return order_service.customers(user=user, page=page, page_size=page_size, q=q)


@router.get("/customers/{cid}", response_model=Customer)
def get_customer(
    cid: int,
    user: sqlite3.Row = Depends(require_permission("customer:view")),
):
    return order_service.customer_detail(cid, user)
