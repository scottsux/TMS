"""FastAPI application assembly; endpoint implementations live in domain services."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..core.permissions import *  # noqa: F403
from ..core.security import *  # noqa: F403
from ..db.connection import get_conn
from ..db.schema import init_db, seed
from ..models.enums import *  # noqa: F403
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from ..services.auth_service import login
from ..services.billing_service import *  # noqa: F403
from ..services.exception_service import *  # noqa: F403
from ..services.notification_service import *  # noqa: F403
from ..services.order_service import *  # noqa: F403
from ..services.parcel_service import *  # noqa: F403
from ..services.task_service import *  # noqa: F403

app = FastAPI(title="TMS API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    init_db()
    seed()

_ENDPOINTS = (
("POST","/auth/login",login,LoginResp),("POST","/parcels",create_parcel,Parcel),("PATCH","/parcels/{pid}/status",patch_parcel_status,Parcel),("GET","/parcels",list_parcels,list[Parcel]),("POST","/orders",create_order,Order),("GET","/orders",list_orders,list[Order]),("GET","/orders/{oid}",get_order,Order),("PATCH","/orders/{oid}/price",patch_order_price,None),("PATCH","/orders/{oid}/volumetric",patch_order_volumetric,None),("PATCH","/orders/{oid}/actual_weight",patch_order_actual_weight,None),("PATCH","/orders/{oid}/parcels",patch_order_parcels,Order),("PATCH","/orders/{oid}/override_price",override_price,None),("PATCH","/orders/{oid}/order_no",patch_order_no,None),("POST","/orders/{oid}/exceptions",create_order_exception,None),("GET","/orders/{oid}/exceptions",list_order_exceptions,None),("GET","/exceptions",list_exceptions,None),("PATCH","/exceptions/{eid}/resolve",resolve_order_exception,None),("GET","/orders/{oid}/audits",list_order_audits,None),("GET","/tasks",list_tasks,list[Task]),("PATCH","/tasks/{tid}/start",start_task,None),("PATCH","/tasks/{tid}/complete",complete_task,None),("PATCH","/orders/{oid}/ship",ship_order,None),("POST","/notify/ready_to_ship",notify_ready,None),("POST","/notify/shipped",notify_shipped,None),("POST","/notify/ready_to_pack",notify_ready_to_pack,None),("GET","/notifications",get_notifications,None),("DELETE","/notifications",clear_notifications,None),("GET","/customers/{cid}/parcels",parcels_by_customer,list[Parcel]),("POST","/orders/auto",auto_create_order,Order),("GET","/customers",customers,list[Customer]),("GET","/customers/{cid}",customer_detail,Customer),("POST","/parcels/{pid}/files",upload_parcel_files,None),
)
for method, path, endpoint, response_model in _ENDPOINTS:
    app.add_api_route(path, endpoint, methods=[method], response_model=response_model)
