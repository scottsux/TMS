import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile

from ..core.permissions import require_permission
from ..models.enums import ParcelStatus
from ..schemas import Parcel, ParcelCreate, ParcelStatusPatch
from ..services import parcel_service


router = APIRouter()


@router.post("/parcels", response_model=Parcel)
def create_parcel(
    body: ParcelCreate,
    user: sqlite3.Row = Depends(require_permission("parcel:create")),
):
    return parcel_service.create_parcel(body, user)


@router.patch("/parcels/{pid}/status", response_model=Parcel)
def patch_parcel_status(
    pid: int,
    body: ParcelStatusPatch,
    user: sqlite3.Row = Depends(require_permission("parcel:arrived")),
):
    return parcel_service.patch_parcel_status(pid, body, user)


@router.get("/parcels", response_model=list[Parcel])
def list_parcels(
    customer_id: Optional[int] = Query(default=None),
    status: Optional[ParcelStatus] = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=50),
    user: sqlite3.Row = Depends(require_permission("parcel:view")),
):
    return parcel_service.list_parcels(
        user=user,
        customer_id=customer_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/customers/{cid}/parcels", response_model=list[Parcel])
def parcels_by_customer(
    cid: int,
    status: Optional[ParcelStatus] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("parcel:view")),
):
    return parcel_service.parcels_by_customer(cid, user, status)


@router.post("/parcels/{pid}/files")
async def upload_parcel_files(
    pid: int,
    files: List[UploadFile] = File(...),
    user: sqlite3.Row = Depends(require_permission("parcel:create")),
):
    return await parcel_service.upload_parcel_files(pid, files, user)
