import sqlite3

from fastapi import APIRouter, Depends

from ..core.permissions import require_permission
from ..schemas import ActualWeightPatch, OverridePrice, PricePatch, VolumetricPatch
from ..services import billing_service


router = APIRouter()


@router.patch("/orders/{oid}/price")
def patch_order_price(
    oid: int,
    body: PricePatch,
    user: sqlite3.Row = Depends(require_permission("price:update")),
):
    return billing_service.patch_order_price(oid, body, user)


@router.patch("/orders/{oid}/volumetric")
def patch_order_volumetric(
    oid: int,
    body: VolumetricPatch,
    user: sqlite3.Row = Depends(require_permission("weight:update")),
):
    return billing_service.patch_order_volumetric(oid, body, user)


@router.patch("/orders/{oid}/actual_weight")
def patch_order_actual_weight(
    oid: int,
    body: ActualWeightPatch,
    user: sqlite3.Row = Depends(require_permission("weight:update")),
):
    return billing_service.patch_order_actual_weight(oid, body, user)


@router.patch("/orders/{oid}/override_price")
def override_price(
    oid: int,
    body: OverridePrice,
    user: sqlite3.Row = Depends(require_permission("price:update")),
):
    return billing_service.override_price(oid, body, user)
