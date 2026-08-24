from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..models.enums import OrderStatus, ParcelStatus

class OrderCreate(BaseModel):
    customer_id: int
    parcel_ids: List[int]


class PricePatch(BaseModel):
    actual_weight: Optional[float] = Field(default=None, ge=0)
    rate_per_kg: float = Field(ge=0)
    extra_fee: float = Field(default=0, ge=0)
    reason: Optional[str] = None


class VolumetricPatch(BaseModel):
    volumetric_weight: float = Field(ge=0)


class ActualWeightPatch(BaseModel):
    actual_weight: float = Field(ge=0)


class OverridePrice(BaseModel):
    final_price: float = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)


class OrderNoPatch(BaseModel):
    order_no: str


class OrderParcelsPatch(BaseModel):
    add: Optional[List[int]] = None
    remove: Optional[List[int]] = None


class Order(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    parcel_ids: List[int]
    status: OrderStatus
    actual_weight: float = 0
    final_price: Optional[float] = None
    volumetric_weight: float = 0
    forwarding: Optional[Dict[str, Any]] = None
    created_at: str
    order_no: Optional[str] = None


class ReadyNotify(BaseModel):
    customer_id: int
    message: Optional[str] = None
    parcel_ids: Optional[List[int]] = None
    channel: Optional[str] = Field(default="air")
    destination: Optional[str] = Field(default="UK")
    service: Optional[str] = Field(default=None)
    consignee_name: Optional[str] = None
    consignee_state: Optional[str] = None
    consignee_city: Optional[str] = None
    consignee_address: Optional[str] = None
    consignee_phone: Optional[str] = None
    consignee_email: Optional[str] = None
    consignee_postcode: Optional[str] = None


class AutoOrderReq(BaseModel):
    customer_id: int
    statuses: Optional[List[ParcelStatus]] = None


