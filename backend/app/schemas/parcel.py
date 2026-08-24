from typing import Optional

from pydantic import BaseModel

from ..models.enums import ParcelStatus

class ParcelCreate(BaseModel):
    customer_id: int
    tracking_number: str
    courier_company: Optional[str] = None
    item_category: Optional[str] = None
    item_description: Optional[str] = None
    note: Optional[str] = None


class Parcel(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    tracking_number: str
    status: ParcelStatus
    courier_company: Optional[str] = None
    item_category: Optional[str] = None
    item_description: Optional[str] = None
    note: Optional[str] = None
    arrived_at: Optional[str] = None
    pack_requested_at: Optional[str] = None
    packed_at: Optional[str] = None
    shipped_at: Optional[str] = None


class ParcelStatusPatch(BaseModel):
    status: ParcelStatus


