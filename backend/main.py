from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone

app = FastAPI(title="TMS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Enums
class ParcelStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    PACK_REQUESTED = "PACK_REQUESTED"
    PACKED = "PACKED"
    REJECTED = "REJECTED"


class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    READY_TO_PACK = "READY_TO_PACK"
    PACKING = "PACKING"
    READY_TO_SHIP = "READY_TO_SHIP"
    COMPLETED = "COMPLETED"


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


# In‑memory DB (demo)
db: Dict[str, Dict] = {
    "customers": {},
    "parcels": {},
    "orders": {},
    "tasks": {},
    "notifications": {},
}

seq = {"customer": 1, "parcel": 1, "order": 1, "task": 1}


def next_id(kind: str) -> int:
    seq[kind] += 1
    return seq[kind] - 1


# Models
class LoginReq(BaseModel):
    email: str
    password: str


class LoginResp(BaseModel):
    token: str


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


class OrderCreate(BaseModel):
    customer_id: int
    parcel_ids: List[int]


class PricePatch(BaseModel):
    actual_weight: float = Field(ge=0)
    rate_per_kg: float
    extra_fee: float = 0


class Order(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    parcel_ids: List[int]
    status: OrderStatus
    actual_weight: float = 0
    final_price: Optional[float] = None
    volumetric_weight: float = 0
    forwarding: Optional[Dict] = None
    created_at: str
    order_no: Optional[str] = None


class Task(BaseModel):
    id: int
    order_id: int
    status: TaskStatus
    actual_weight: Optional[float] = None


# Helpers
def ensure_unique_tracking(tracking: str):
    for p in db["parcels"].values():
        if p["tracking_number"].lower() == tracking.lower():
            raise HTTPException(status_code=400, detail="tracking_number must be unique")


def ensure_transition(old: ParcelStatus, new: ParcelStatus):
    allowed = {
        ParcelStatus.SUBMITTED: {ParcelStatus.IN_TRANSIT, ParcelStatus.REJECTED},
        ParcelStatus.IN_TRANSIT: {ParcelStatus.ARRIVED},
        ParcelStatus.ARRIVED: {ParcelStatus.PACK_REQUESTED, ParcelStatus.PACKED},
        ParcelStatus.PACK_REQUESTED: {ParcelStatus.PACKED},
        ParcelStatus.REJECTED: set(),
        ParcelStatus.PACKED: set(),
    }
    if new not in allowed[old]:
        raise HTTPException(status_code=400, detail=f"invalid transition {old} -> {new}")


def is_parcel_assigned(pid: int) -> bool:
    for o in db["orders"].values():
        if pid in o.get("parcel_ids", []):
            return True
    return False


def price_formula(actual_weight: float, rate_per_kg: float, extra_fee: float) -> float:
    return round(actual_weight * rate_per_kg + extra_fee, 2)


# Auth
@app.post("/auth/login", response_model=LoginResp)
def login(req: LoginReq):
    # demo only
    return LoginResp(token="jwt_token")


# Parcels
@app.post("/parcels", response_model=Parcel)
def create_parcel(body: ParcelCreate):
    ensure_unique_tracking(body.tracking_number)
    pid = next_id("parcel")
    cname = db["customers"].get(body.customer_id, {}).get("name")
    db["parcels"][pid] = {
        "id": pid,
        "customer_id": body.customer_id,
        "customer_name": cname,
        "tracking_number": body.tracking_number,
        # 提交后进入“在途”，由仓库人员手动改为“已到仓”
        "status": ParcelStatus.IN_TRANSIT,
        "courier_company": body.courier_company,
        "item_category": body.item_category,
        "item_description": body.item_description,
        "note": body.note,
        "arrived_at": None,
        "pack_requested_at": None,
        "packed_at": None,
        "shipped_at": None,
    }
    return Parcel(**db["parcels"][pid])


@app.patch("/parcels/{pid}/status", response_model=Parcel)
def patch_parcel_status(pid: int, body: ParcelStatusPatch):
    p = db["parcels"].get(pid)
    if not p:
        raise HTTPException(status_code=404, detail="parcel not found")
    ensure_transition(p["status"], body.status)
    p["status"] = body.status
    now = datetime.now(timezone.utc).isoformat()
    if body.status == ParcelStatus.ARRIVED:
        p["arrived_at"] = now
    elif body.status == ParcelStatus.PACK_REQUESTED:
        p["pack_requested_at"] = now
    elif body.status == ParcelStatus.PACKED:
        p["packed_at"] = now
    return Parcel(**p)


@app.get("/parcels", response_model=List[Parcel])
def list_parcels(
    customer_id: Optional[int] = None,
    status: Optional[ParcelStatus] = None,
    page: int = 1,
    page_size: int = 50,
):
    items_raw = list(db["parcels"].values())
    for p in items_raw:
        if not p.get("customer_name"):
            p["customer_name"] = db["customers"].get(p["customer_id"], {}).get("name")
    items = [Parcel(**p) for p in items_raw]
    if customer_id is not None:
        items = [p for p in items if p.customer_id == customer_id]
    if status is not None:
        items = [p for p in items if p.status == status]
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return items[start:end]


# Orders
@app.post("/orders", response_model=Order)
def create_order(body: OrderCreate):
    for pid in body.parcel_ids:
        if pid not in db["parcels"]:
            raise HTTPException(status_code=400, detail=f"parcel {pid} not found")
        if is_parcel_assigned(pid):
            raise HTTPException(status_code=400, detail=f"parcel {pid} already in another order")
    oid = next_id("order")
    cname = db["customers"].get(body.customer_id, {}).get("name")
    now = datetime.now(timezone.utc).isoformat()
    db["orders"][oid] = {
        "id": oid,
        "customer_id": body.customer_id,
        "customer_name": cname,
        "parcel_ids": body.parcel_ids,
        "status": OrderStatus.DRAFT,
        "actual_weight": 0.0,
        "final_price": None,
        "volumetric_weight": 0.0,
        "forwarding": None,
        "created_at": now,
        "order_no": None,
    }
    # create a task for this order (MVP: one order -> one task)
    tid = next_id("task")
    db["tasks"][tid] = {"id": tid, "order_id": oid, "status": TaskStatus.TODO, "actual_weight": None}
    return Order(**db["orders"][oid])


@app.get("/orders", response_model=List[Order])
def list_orders(
    customer_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    page: int = 1,
    page_size: int = 50,
):
    rows: List[Order] = []
    for o in db["orders"].values():
        if not o.get("customer_name"):
            o["customer_name"] = db["customers"].get(o["customer_id"], {}).get("name")
        rows.append(Order(**o))
    if customer_id is not None:
        rows = [o for o in rows if o.customer_id == customer_id]
    if status is not None:
        rows = [o for o in rows if o.status == status]
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return rows[start:end]


@app.get("/orders/{oid}", response_model=Order)
def get_order(oid: int):
    o = db["orders"].get(oid)
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    if not o.get("customer_name"):
        o["customer_name"] = db["customers"].get(o["customer_id"], {}).get("name")
    return Order(**o)


@app.patch("/orders/{oid}/price")
def patch_order_price(oid: int, body: PricePatch):
    o = db["orders"].get(oid)
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    o["actual_weight"] = float(body.actual_weight)
    o["final_price"] = price_formula(body.actual_weight, body.rate_per_kg, body.extra_fee)
    return {"final_price": o["final_price"]}


class VolumetricPatch(BaseModel):
    volumetric_weight: float = Field(ge=0)


@app.patch("/orders/{oid}/volumetric")
def patch_order_volumetric(oid: int, body: VolumetricPatch):
    o = db["orders"].get(oid)
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    o["volumetric_weight"] = float(body.volumetric_weight)
    # keep forwarding snapshot in sync
    if not o.get("forwarding"):
        o["forwarding"] = {}
    o["forwarding"]["volumetric_weight"] = o["volumetric_weight"]
    return {"volumetric_weight": o["volumetric_weight"]}


class ActualWeightPatch(BaseModel):
    actual_weight: float = Field(ge=0)


@app.patch("/orders/{oid}/actual_weight")
def patch_order_actual_weight(oid: int, body: ActualWeightPatch):
    o = db["orders"].get(oid)
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    o["actual_weight"] = float(body.actual_weight)
    # keep forwarding snapshot in sync
    if not o.get("forwarding"):
        o["forwarding"] = {}
    o["forwarding"]["actual_weight"] = o["actual_weight"]
    return {"actual_weight": o["actual_weight"]}


class OrderParcelsPatch(BaseModel):
    add: Optional[List[int]] = None
    remove: Optional[List[int]] = None


@app.patch("/orders/{oid}/parcels", response_model=Order)
def patch_order_parcels(oid: int, body: OrderParcelsPatch):
    o = db["orders"].get(oid)
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    current: List[int] = list(o.get("parcel_ids", []))
    # remove
    if body.remove:
        current = [pid for pid in current if pid not in set(body.remove)]
    # add
    if body.add:
        for pid in body.add:
            if pid not in db["parcels"]:
                raise HTTPException(status_code=400, detail=f"parcel {pid} not found")
            if is_parcel_assigned(pid):
                raise HTTPException(status_code=400, detail=f"parcel {pid} already in another order")
            # customer consistency
            if db["parcels"][pid]["customer_id"] != o["customer_id"]:
                raise HTTPException(status_code=400, detail=f"parcel {pid} belongs to a different customer")
            current.append(pid)
    o["parcel_ids"] = current
    return Order(**o)


class OverridePrice(BaseModel):
    final_price: float = Field(ge=0)


@app.patch("/orders/{oid}/override_price")
def override_price(oid: int, body: OverridePrice):
    o = db["orders"].get(oid)
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    o["final_price"] = round(float(body.final_price), 2)
    return {"final_price": o["final_price"]}


class OrderNoPatch(BaseModel):
    order_no: str


@app.patch("/orders/{oid}/order_no")
def patch_order_no(oid: int, body: OrderNoPatch):
    o = db["orders"].get(oid)
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    o["order_no"] = body.order_no.strip() or None
    return {"order_no": o["order_no"]}


# Tasks
@app.get("/tasks", response_model=List[Task])
def list_tasks(order_id: Optional[int] = Query(default=None)):
    rows = [Task(**t) for t in db["tasks"].values()]
    if order_id is not None:
        rows = [t for t in rows if t.order_id == order_id]
    return rows


@app.patch("/tasks/{tid}/start")
def start_task(tid: int):
    t = db["tasks"].get(tid)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    t["status"] = TaskStatus.IN_PROGRESS
    # order status follows
    o = db["orders"].get(t["order_id"])
    if o:
        o["status"] = OrderStatus.PACKING
    return {"ok": True}


class TaskComplete(BaseModel):
    actual_weight: Optional[float] = Field(default=None, ge=0)


@app.patch("/tasks/{tid}/complete")
def complete_task(tid: int, body: TaskComplete):
    t = db["tasks"].get(tid)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    if body.actual_weight is not None:
        t["actual_weight"] = float(body.actual_weight)
    o = db["orders"].get(t["order_id"])
    if o:
        if t.get("actual_weight") is not None:
            o["actual_weight"] = t["actual_weight"]
        # 打包完成后仍保持任务在进行中，订单转为待发货
        t["status"] = TaskStatus.IN_PROGRESS
        o["status"] = OrderStatus.READY_TO_SHIP
        now = datetime.now(timezone.utc).isoformat()
        for pid in o.get("parcel_ids", []):
            if pid in db["parcels"]:
                db["parcels"][pid]["status"] = ParcelStatus.PACKED
                db["parcels"][pid]["packed_at"] = now
    return {"ok": True}


@app.patch("/orders/{oid}/ship")
def ship_order(oid: int):
    o = db["orders"].get(oid)
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    if o["status"] != OrderStatus.READY_TO_SHIP:
        raise HTTPException(status_code=400, detail="order is not ready to ship")
    o["status"] = OrderStatus.COMPLETED
    now = datetime.now(timezone.utc).isoformat()
    for pid in o.get("parcel_ids", []):
        if pid in db["parcels"]:
            db["parcels"][pid]["shipped_at"] = now
    for t in db["tasks"].values():
        if t.get("order_id") == oid:
            t["status"] = TaskStatus.DONE
            break
    return {"ok": True}


# Seed some demo data
@app.on_event("startup")
def seed():
    # customers
    cid = next_id("customer"); db["customers"][cid] = {"id": cid, "name": "Acme"}
    cid = next_id("customer"); db["customers"][cid] = {"id": cid, "name": "Globex"}
    # parcels
    p1 = create_parcel(ParcelCreate(customer_id=1, tracking_number="SF123", courier_company="SF", item_category="cosmetics", item_description="lipstick"))
    p2 = create_parcel(ParcelCreate(customer_id=1, tracking_number="SF124"))
    # 不再创建演示草稿订单，避免干扰实际流程


# --- Notification (demo) ---
class ReadyNotify(BaseModel):
    customer_id: int
    message: Optional[str] = None
    parcel_ids: Optional[List[int]] = None
    # forwarding details (optional)
    channel: Optional[str] = Field(default="air")            # air/sea
    destination: Optional[str] = Field(default="UK")
    service: Optional[str] = Field(default=None)              # express/economy
    consignee_name: Optional[str] = None
    consignee_state: Optional[str] = None
    consignee_city: Optional[str] = None
    consignee_address: Optional[str] = None
    consignee_phone: Optional[str] = None
    consignee_email: Optional[str] = None
    consignee_postcode: Optional[str] = None


@app.post("/notify/ready_to_ship")
def notify_ready(body: ReadyNotify):
    arr = db["notifications"].setdefault("ready_to_ship", [])
    # 只保留每客户的第一条
    for it in arr:
        if it.get("customer_id") == body.customer_id:
            return {"ok": True}
    now = datetime.now(timezone.utc)
    item = {"customer_id": body.customer_id, "message": body.message or "ready", "ts": now.isoformat()}
    arr.append(item)
    return {"ok": True}


@app.post("/notify/shipped")
def notify_shipped(body: ReadyNotify):
    arr = db["notifications"].setdefault("shipped", [])
    now = datetime.now(timezone.utc).isoformat()
    arr.append({"customer_id": body.customer_id, "message": body.message or "shipped", "ts": now})
    return {"ok": True}


@app.post("/notify/ready_to_pack")
def notify_ready_to_pack(body: ReadyNotify):
    arr = db["notifications"].setdefault("ready_to_pack", [])
    now = datetime.now(timezone.utc)
    ts_date = now.strftime("%Y-%m-%d")
    ts_time = now.strftime("%H:%M:%S")

    # 同客户在通知列表中只保留一条，但每次调用都会更新该条并尝试创建新订单
    existing = None
    for it in arr:
        if it.get("customer_id") == body.customer_id:
            existing = it
            break

    payload = {
        "customer_id": body.customer_id,
        "message": body.message or "ready_to_pack",
        "date": ts_date,
        "time": ts_time,
        # add a machine-friendly timestamp for UI convenience
        "ts": now.isoformat(),
        "channel": body.channel,
        "destination": body.destination,
        "service": body.service,
        "consignee": {
            "name": body.consignee_name,
            "state": body.consignee_state,
            "city": body.consignee_city,
            "address": body.consignee_address,
            "phone": body.consignee_phone,
            "email": body.consignee_email,
            "postcode": body.consignee_postcode,
        },
    }

    if existing is None:
        arr.append(payload)
    else:
        existing.update(payload)

    # 自动为该客户生成一个待打包订单
    # 优先策略：
    # 1) 若存在该客户的 DRAFT 订单，则尽量复用并将可选包裹并入该订单；
    # 2) 否则，收集已到仓/已打包、且未分配的包裹创建新订单；
    # 3) 若两者都没有包裹，则仅更新通知记录，不报错。
    if body.parcel_ids:
        ids = set(body.parcel_ids)
        selectable = [
            p for p in db["parcels"].values()
            if p["id"] in ids
            and p["customer_id"] == body.customer_id
            and p["status"] == ParcelStatus.ARRIVED
            and not is_parcel_assigned(p["id"])
        ]
    else:
        selectable = [
            p for p in db["parcels"].values()
            if p["customer_id"] == body.customer_id
            and p["status"] == ParcelStatus.ARRIVED
            and not is_parcel_assigned(p["id"])
        ]
    created_order_id = None

    # 尝试复用客户的草稿订单
    draft_order = None
    for o in db["orders"].values():
        if o.get("customer_id") == body.customer_id and o.get("status") == OrderStatus.DRAFT:
            draft_order = o
            break

    if draft_order is not None:
        # 将未被占用的可选包裹加入草稿订单
        if selectable:
            current = list(draft_order.get("parcel_ids", []))
            current_ids = set(current)
            for p in selectable:
                if p["id"] not in current_ids:
                    current.append(p["id"])
                    current_ids.add(p["id"])
            draft_order["parcel_ids"] = current
        # 这些包裹标记为“申请打包”，提升状态并写入转运信息
        now = datetime.now(timezone.utc).isoformat()
        for p in selectable:
            p["status"] = ParcelStatus.PACK_REQUESTED
            p["pack_requested_at"] = now
        draft_order["status"] = OrderStatus.READY_TO_PACK
        draft_order["forwarding"] = {
            "channel": body.channel,
            "destination": body.destination,
            "service": body.service,
            "consignee": payload["consignee"],
        }
        created_order_id = draft_order["id"]
    elif selectable:
        # 没有草稿订单，则创建新订单
        new = create_order(
            OrderCreate(customer_id=body.customer_id, parcel_ids=[p["id"] for p in selectable])
        )
        created_order_id = new.id
        o = db["orders"][new.id]
        o["status"] = OrderStatus.READY_TO_PACK
        o["forwarding"] = {
            "channel": body.channel,
            "destination": body.destination,
            "service": body.service,
            "consignee": payload["consignee"],
            # snapshot weights for convenience in UI
            "actual_weight": o.get("actual_weight", 0.0),
            "volumetric_weight": o.get("volumetric_weight", 0.0),
        }
        # 标记为“申请打包”
        now = datetime.now(timezone.utc).isoformat()
        for p in selectable:
            p["status"] = ParcelStatus.PACK_REQUESTED
            p["pack_requested_at"] = now
    return {"ok": True, "order_id": created_order_id}


@app.get("/notifications")
def get_notifications(type: Optional[str] = None, customer_id: Optional[int] = None):
    if type:
        items = db["notifications"].get(type, [])
        if customer_id is not None:
            items = [i for i in items if i.get("customer_id") == customer_id]
        return items
    # flatten: return dict of lists
    return db["notifications"]


@app.delete("/notifications")
def clear_notifications(type: Optional[str] = None):
    if type:
        db["notifications"][type] = []
    else:
        db["notifications"] = {}
    return {"ok": True}


@app.get("/customers/{cid}/parcels", response_model=List[Parcel])
def parcels_by_customer(cid: int, status: Optional[ParcelStatus] = None):
    items: List[Parcel] = []
    for p in db["parcels"].values():
        if p["customer_id"] != cid:
            continue
        if not p.get("customer_name"):
            p["customer_name"] = db["customers"].get(p["customer_id"], {}).get("name")
        items.append(Parcel(**p))
    if status:
        items = [p for p in items if p.status == status]
    return items


class AutoOrderReq(BaseModel):
    customer_id: int
    statuses: Optional[List[ParcelStatus]] = None


@app.post("/orders/auto", response_model=Order)
def auto_create_order(req: AutoOrderReq):
    default_statuses = {ParcelStatus.SUBMITTED, ParcelStatus.IN_TRANSIT, ParcelStatus.ARRIVED}
    allow = set(req.statuses) if req.statuses else default_statuses
    selectable = [
        p for p in db["parcels"].values()
        if p["customer_id"] == req.customer_id and p["status"] in allow and not is_parcel_assigned(p["id"])
    ]
    if not selectable:
        raise HTTPException(status_code=400, detail="no eligible parcels to create order")
    body = OrderCreate(customer_id=req.customer_id, parcel_ids=[p["id"] for p in selectable])
    return create_order(body)


# Customers APIs
class Customer(BaseModel):
    id: int
    name: str


@app.get("/customers", response_model=List[Customer])
def customers(page: int = 1, page_size: int = 50, q: Optional[str] = None):
    items = [Customer(**c) for c in db["customers"].values()]
    if q:
        ql = q.lower()
        items = [c for c in items if ql in c.name.lower()]
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return items[start:end]


@app.get("/customers/{cid}", response_model=Customer)
def customer_detail(cid: int):
    c = db["customers"].get(cid)
    if not c:
        raise HTTPException(status_code=404, detail="customer not found")
    return Customer(**c)


# File uploads for parcels (demo): stores into /tmp/tms_uploads/{pid}/
UPLOAD_DIR = Path("/tmp/tms_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/parcels/{pid}/files")
async def upload_parcel_files(pid: int, files: List[UploadFile] = File(...)):
    if pid not in db["parcels"]:
        raise HTTPException(status_code=404, detail="parcel not found")
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="max 5 files")
    ok_types = {"image/png", "image/jpeg", "image/webp"}
    saved = []
    d = UPLOAD_DIR / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    for uf in files:
        if uf.content_type not in ok_types:
            raise HTTPException(status_code=400, detail=f"unsupported type: {uf.content_type}")
        data = await uf.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{uf.filename} exceeds 5MB")
        path = d / uf.filename
        path.write_bytes(data)
        saved.append({"filename": uf.filename, "size": len(data)})
    return {"saved": saved}
