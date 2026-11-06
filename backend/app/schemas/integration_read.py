from typing import List, Optional

from pydantic import BaseModel

from ..models.enums import ExceptionStatus, ExceptionType, OrderStatus, ParcelStatus


class IntegrationParcelRead(BaseModel):
    id: int
    tracking_number: str
    status: ParcelStatus
    courier_company: Optional[str] = None
    item_category: Optional[str] = None
    arrived_at: Optional[str] = None
    pack_requested_at: Optional[str] = None
    packed_at: Optional[str] = None
    shipped_at: Optional[str] = None


class IntegrationOrderRead(BaseModel):
    id: int
    order_no: Optional[str] = None
    status: OrderStatus
    parcel_ids: List[int]
    actual_weight: float
    volumetric_weight: float
    created_at: str


class IntegrationExceptionRead(BaseModel):
    id: int
    order_id: int
    type: ExceptionType
    status: ExceptionStatus
    created_at: str
    resolved_at: Optional[str] = None
