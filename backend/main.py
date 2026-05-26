import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="TMS API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DB_PATH = Path(__file__).resolve().parent / "tms.db"
UPLOAD_DIR = Path("/tmp/tms_uploads")
TOKEN_SECRET = "tms-dev-secret"
TOKEN_TTL_HOURS = 12
PBKDF2_ROUNDS = 120_000


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


class UserRole(str, Enum):
    customer = "customer"
    staff = "staff"
    operator = "operator"


PERMISSIONS: Dict[UserRole, set[str]] = {
    UserRole.customer: {"parcel:create", "parcel:view", "order:view", "notification:create"},
    UserRole.staff: {
        "parcel:create",
        "parcel:view",
        "parcel:arrived",
        "parcel:update",
        "order:create",
        "order:view",
        "order:update",
        "order:ship",
        "customer:view",
        "price:update",
        "notification:view",
        "notification:clear",
    },
    UserRole.operator: {
        "parcel:view",
        "order:view",
        "task:view",
        "task:start",
        "task:complete",
        "notification:view",
    },
}


class LoginReq(BaseModel):
    email: str
    password: str


class LoginResp(BaseModel):
    token: str
    role: UserRole
    user: Dict[str, Any]


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


class VolumetricPatch(BaseModel):
    volumetric_weight: float = Field(ge=0)


class ActualWeightPatch(BaseModel):
    actual_weight: float = Field(ge=0)


class OverridePrice(BaseModel):
    final_price: float = Field(ge=0)


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


class Task(BaseModel):
    id: int
    order_id: int
    status: TaskStatus
    actual_weight: Optional[float] = None


class TaskComplete(BaseModel):
    actual_weight: Optional[float] = Field(default=None, ge=0)


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


class Customer(BaseModel):
    id: int
    name: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def encode_json(value: Optional[Dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def decode_json(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    return json.loads(value)


def row_to_parcel(row: sqlite3.Row) -> Parcel:
    return Parcel(
        id=row["id"],
        customer_id=row["customer_id"],
        customer_name=row["customer_name"],
        tracking_number=row["tracking_number"],
        status=ParcelStatus(row["status"]),
        courier_company=row["courier_company"],
        item_category=row["item_category"],
        item_description=row["item_description"],
        note=row["note"],
        arrived_at=row["arrived_at"],
        pack_requested_at=row["pack_requested_at"],
        packed_at=row["packed_at"],
        shipped_at=row["shipped_at"],
    )


def row_to_order(row: sqlite3.Row) -> Order:
    return Order(
        id=row["id"],
        customer_id=row["customer_id"],
        customer_name=row["customer_name"],
        parcel_ids=[int(pid) for pid in decode_json(row["parcel_ids"]) or []],
        status=OrderStatus(row["status"]),
        actual_weight=float(row["actual_weight"] or 0),
        final_price=float(row["final_price"]) if row["final_price"] is not None else None,
        volumetric_weight=float(row["volumetric_weight"] or 0),
        forwarding=decode_json(row["forwarding"]),
        created_at=row["created_at"],
        order_no=row["order_no"],
    )


def row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        order_id=row["order_id"],
        status=TaskStatus(row["status"]),
        actual_weight=float(row["actual_weight"]) if row["actual_weight"] is not None else None,
    )


def fetch_customer_name(conn: sqlite3.Connection, customer_id: int) -> Optional[str]:
    row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
    return row["name"] if row else None


def ensure_customer_exists(conn: sqlite3.Connection, customer_id: int):
    if not conn.execute("SELECT 1 FROM customers WHERE id = ?", (customer_id,)).fetchone():
        raise HTTPException(status_code=400, detail="customer not found")


def ensure_unique_tracking(conn: sqlite3.Connection, tracking: str, exclude_id: Optional[int] = None):
    sql = "SELECT id FROM parcels WHERE lower(tracking_number) = lower(?)"
    params: list[Any] = [tracking]
    if exclude_id is not None:
        sql += " AND id != ?"
        params.append(exclude_id)
    row = conn.execute(sql, params).fetchone()
    if row:
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


def is_parcel_assigned(conn: sqlite3.Connection, pid: int, exclude_order_id: Optional[int] = None) -> bool:
    rows = conn.execute("SELECT id, parcel_ids FROM orders").fetchall()
    for row in rows:
        if exclude_order_id is not None and row["id"] == exclude_order_id:
            continue
        parcel_ids = decode_json(row["parcel_ids"]) or []
        if pid in parcel_ids:
            return True
    return False


def price_formula(actual_weight: float, rate_per_kg: float, extra_fee: float) -> float:
    return round(actual_weight * rate_per_kg + extra_fee, 2)


def make_password_hash(password: str, salt: Optional[str] = None) -> str:
    raw_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt.encode("utf-8"), PBKDF2_ROUNDS)
    return f"{raw_salt}${base64.urlsafe_b64encode(digest).decode('utf-8')}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    expected = make_password_hash(password, salt)
    return hmac.compare_digest(expected, stored)


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(user_row: sqlite3.Row) -> str:
    payload = {
        "sub": user_row["id"],
        "role": user_row["role"],
        "customer_id": user_row["customer_id"],
        "exp": int((utc_now() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    body = b64url_encode(raw)
    sig = hmac.new(TOKEN_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{b64url_encode(sig)}"


def parse_token(token: str) -> Dict[str, Any]:
    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    expected_sig = b64url_encode(hmac.new(TOKEN_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(expected_sig, sig):
        raise HTTPException(status_code=401, detail="invalid token")
    payload = json.loads(b64url_decode(body).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(utc_now().timestamp()):
        raise HTTPException(status_code=401, detail="token expired")
    return payload


def get_current_user(authorization: Optional[str] = Header(default=None)) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = parse_token(token)
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.role, u.customer_id, c.name AS customer_name
            FROM users u
            LEFT JOIN customers c ON c.id = u.customer_id
            WHERE u.id = ?
            """,
            (payload["sub"],),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="user not found")
    return row


def require_permission(permission: str):
    def dependency(user: sqlite3.Row = Depends(get_current_user)) -> sqlite3.Row:
        role = UserRole(user["role"])
        if permission not in PERMISSIONS[role]:
            raise HTTPException(status_code=403, detail="forbidden")
        return user

    return dependency


def ensure_customer_scope(user: sqlite3.Row, customer_id: int):
    if user["role"] == UserRole.customer.value and user["customer_id"] != customer_id:
        raise HTTPException(status_code=403, detail="forbidden")


def get_parcel_or_404(conn: sqlite3.Connection, pid: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT p.*, c.name AS customer_name
        FROM parcels p
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE p.id = ?
        """,
        (pid,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="parcel not found")
    return row


def get_order_or_404(conn: sqlite3.Connection, oid: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT o.*, c.name AS customer_name
        FROM orders o
        LEFT JOIN customers c ON c.id = o.customer_id
        WHERE o.id = ?
        """,
        (oid,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="order not found")
    return row


def get_task_or_404(conn: sqlite3.Connection, tid: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    return row


def create_order_record(
    conn: sqlite3.Connection,
    customer_id: int,
    parcel_ids: List[int],
    status: OrderStatus = OrderStatus.DRAFT,
    forwarding: Optional[Dict[str, Any]] = None,
) -> Order:
    now = utc_now_iso()
    cursor = conn.execute(
        """
        INSERT INTO orders (
            customer_id, parcel_ids, status, actual_weight, final_price,
            volumetric_weight, forwarding, created_at, order_no
        ) VALUES (?, ?, ?, 0, NULL, 0, ?, ?, NULL)
        """,
        (customer_id, encode_json(parcel_ids), status.value, encode_json(forwarding), now),
    )
    order_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO tasks (order_id, status, actual_weight) VALUES (?, ?, NULL)",
        (order_id, TaskStatus.TODO.value),
    )
    conn.commit()
    return row_to_order(get_order_or_404(conn, order_id))


def init_db():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                customer_id INTEGER,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                tracking_number TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                courier_company TEXT,
                item_category TEXT,
                item_description TEXT,
                note TEXT,
                arrived_at TEXT,
                pack_requested_at TEXT,
                packed_at TEXT,
                shipped_at TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                parcel_ids TEXT NOT NULL,
                status TEXT NOT NULL,
                actual_weight REAL NOT NULL DEFAULT 0,
                final_price REAL,
                volumetric_weight REAL NOT NULL DEFAULT 0,
                forwarding TEXT,
                created_at TEXT NOT NULL,
                order_no TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                actual_weight REAL,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(type, customer_id),
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed():
    conn = get_conn()
    try:
        if conn.execute("SELECT COUNT(*) AS count FROM customers").fetchone()["count"]:
            return

        conn.execute("INSERT INTO customers (name) VALUES (?)", ("Acme",))
        conn.execute("INSERT INTO customers (name) VALUES (?)", ("Globex",))
        conn.execute(
            "INSERT INTO users (email, password_hash, role, customer_id) VALUES (?, ?, ?, ?)",
            ("customer@example.com", make_password_hash("demo123"), UserRole.customer.value, 1),
        )
        conn.execute(
            "INSERT INTO users (email, password_hash, role, customer_id) VALUES (?, ?, ?, NULL)",
            ("staff@example.com", make_password_hash("demo123"), UserRole.staff.value),
        )
        conn.execute(
            "INSERT INTO users (email, password_hash, role, customer_id) VALUES (?, ?, ?, NULL)",
            ("operator@example.com", make_password_hash("demo123"), UserRole.operator.value),
        )
        conn.execute(
            """
            INSERT INTO parcels (
                customer_id, tracking_number, status, courier_company,
                item_category, item_description, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "SF123", ParcelStatus.IN_TRANSIT.value, "SF", "cosmetics", "lipstick", None),
        )
        conn.execute(
            """
            INSERT INTO parcels (
                customer_id, tracking_number, status, courier_company,
                item_category, item_description, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "SF124", ParcelStatus.IN_TRANSIT.value, None, None, None, None),
        )
        conn.commit()
    finally:
        conn.close()


@app.on_event("startup")
def startup():
    init_db()
    seed()


@app.post("/auth/login", response_model=LoginResp)
def login(req: LoginReq):
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.password_hash, u.role, u.customer_id, c.name AS customer_name
            FROM users u
            LEFT JOIN customers c ON c.id = u.customer_id
            WHERE lower(u.email) = lower(?)
            """,
            (req.email.strip(),),
        ).fetchone()
    finally:
        conn.close()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")
    return LoginResp(
        token=create_token(row),
        role=UserRole(row["role"]),
        user={
            "id": row["customer_id"] if row["role"] == UserRole.customer.value else row["id"],
            "user_id": row["id"],
            "email": row["email"],
            "name": row["customer_name"] or row["email"],
        },
    )


@app.post("/parcels", response_model=Parcel)
def create_parcel(body: ParcelCreate, user: sqlite3.Row = Depends(require_permission("parcel:create"))):
    ensure_customer_scope(user, body.customer_id)
    conn = get_conn()
    try:
        ensure_customer_exists(conn, body.customer_id)
        ensure_unique_tracking(conn, body.tracking_number)
        cursor = conn.execute(
            """
            INSERT INTO parcels (
                customer_id, tracking_number, status, courier_company,
                item_category, item_description, note,
                arrived_at, pack_requested_at, packed_at, shipped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
            """,
            (
                body.customer_id,
                body.tracking_number,
                ParcelStatus.IN_TRANSIT.value,
                body.courier_company,
                body.item_category,
                body.item_description,
                body.note,
            ),
        )
        conn.commit()
        return row_to_parcel(get_parcel_or_404(conn, cursor.lastrowid))
    finally:
        conn.close()


@app.patch("/parcels/{pid}/status", response_model=Parcel)
def patch_parcel_status(
    pid: int,
    body: ParcelStatusPatch,
    user: sqlite3.Row = Depends(require_permission("parcel:arrived")),
):
    conn = get_conn()
    try:
        row = get_parcel_or_404(conn, pid)
        ensure_transition(ParcelStatus(row["status"]), body.status)
        now = utc_now_iso()
        updates = {
            "status": body.status.value,
            "arrived_at": row["arrived_at"],
            "pack_requested_at": row["pack_requested_at"],
            "packed_at": row["packed_at"],
        }
        if body.status == ParcelStatus.ARRIVED:
            updates["arrived_at"] = now
        elif body.status == ParcelStatus.PACK_REQUESTED:
            updates["pack_requested_at"] = now
        elif body.status == ParcelStatus.PACKED:
            updates["packed_at"] = now
        conn.execute(
            """
            UPDATE parcels
            SET status = ?, arrived_at = ?, pack_requested_at = ?, packed_at = ?
            WHERE id = ?
            """,
            (
                updates["status"],
                updates["arrived_at"],
                updates["pack_requested_at"],
                updates["packed_at"],
                pid,
            ),
        )
        conn.commit()
        return row_to_parcel(get_parcel_or_404(conn, pid))
    finally:
        conn.close()


@app.get("/parcels", response_model=List[Parcel])
def list_parcels(
    customer_id: Optional[int] = None,
    status: Optional[ParcelStatus] = None,
    page: int = 1,
    page_size: int = 50,
    user: sqlite3.Row = Depends(require_permission("parcel:view")),
):
    conn = get_conn()
    try:
        effective_customer_id = customer_id
        if user["role"] == UserRole.customer.value:
            effective_customer_id = user["customer_id"]
        sql = """
            SELECT p.*, c.name AS customer_name
            FROM parcels p
            LEFT JOIN customers c ON c.id = p.customer_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if effective_customer_id is not None:
            sql += " AND p.customer_id = ?"
            params.append(effective_customer_id)
        if status is not None:
            sql += " AND p.status = ?"
            params.append(status.value)
        sql += " ORDER BY p.id DESC LIMIT ? OFFSET ?"
        params.extend([page_size, max(0, (page - 1) * page_size)])
        rows = conn.execute(sql, params).fetchall()
        return [row_to_parcel(row) for row in rows]
    finally:
        conn.close()


@app.post("/orders", response_model=Order)
def create_order(body: OrderCreate, user: sqlite3.Row = Depends(require_permission("order:create"))):
    ensure_customer_scope(user, body.customer_id)
    conn = get_conn()
    try:
        ensure_customer_exists(conn, body.customer_id)
        for pid in body.parcel_ids:
            parcel = get_parcel_or_404(conn, pid)
            if parcel["customer_id"] != body.customer_id:
                raise HTTPException(status_code=400, detail=f"parcel {pid} belongs to a different customer")
            if is_parcel_assigned(conn, pid):
                raise HTTPException(status_code=400, detail=f"parcel {pid} already in another order")
        return create_order_record(conn, body.customer_id, body.parcel_ids)
    finally:
        conn.close()


@app.get("/orders", response_model=List[Order])
def list_orders(
    customer_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    page: int = 1,
    page_size: int = 50,
    user: sqlite3.Row = Depends(require_permission("order:view")),
):
    conn = get_conn()
    try:
        effective_customer_id = customer_id
        if user["role"] == UserRole.customer.value:
            effective_customer_id = user["customer_id"]
        sql = """
            SELECT o.*, c.name AS customer_name
            FROM orders o
            LEFT JOIN customers c ON c.id = o.customer_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if effective_customer_id is not None:
            sql += " AND o.customer_id = ?"
            params.append(effective_customer_id)
        if status is not None:
            sql += " AND o.status = ?"
            params.append(status.value)
        sql += " ORDER BY o.id DESC LIMIT ? OFFSET ?"
        params.extend([page_size, max(0, (page - 1) * page_size)])
        rows = conn.execute(sql, params).fetchall()
        return [row_to_order(row) for row in rows]
    finally:
        conn.close()


@app.get("/orders/{oid}", response_model=Order)
def get_order(oid: int, user: sqlite3.Row = Depends(require_permission("order:view"))):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        return row_to_order(row)
    finally:
        conn.close()


@app.patch("/orders/{oid}/price")
def patch_order_price(
    oid: int,
    body: PricePatch,
    user: sqlite3.Row = Depends(require_permission("price:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        final_price = price_formula(body.actual_weight, body.rate_per_kg, body.extra_fee)
        conn.execute(
            "UPDATE orders SET actual_weight = ?, final_price = ? WHERE id = ?",
            (float(body.actual_weight), final_price, oid),
        )
        conn.commit()
        return {"final_price": final_price}
    finally:
        conn.close()


@app.patch("/orders/{oid}/volumetric")
def patch_order_volumetric(
    oid: int,
    body: VolumetricPatch,
    user: sqlite3.Row = Depends(require_permission("price:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        forwarding = decode_json(row["forwarding"]) or {}
        forwarding["volumetric_weight"] = float(body.volumetric_weight)
        conn.execute(
            "UPDATE orders SET volumetric_weight = ?, forwarding = ? WHERE id = ?",
            (float(body.volumetric_weight), encode_json(forwarding), oid),
        )
        conn.commit()
        return {"volumetric_weight": float(body.volumetric_weight)}
    finally:
        conn.close()


@app.patch("/orders/{oid}/actual_weight")
def patch_order_actual_weight(
    oid: int,
    body: ActualWeightPatch,
    user: sqlite3.Row = Depends(require_permission("price:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        forwarding = decode_json(row["forwarding"]) or {}
        forwarding["actual_weight"] = float(body.actual_weight)
        conn.execute(
            "UPDATE orders SET actual_weight = ?, forwarding = ? WHERE id = ?",
            (float(body.actual_weight), encode_json(forwarding), oid),
        )
        conn.commit()
        return {"actual_weight": float(body.actual_weight)}
    finally:
        conn.close()


@app.patch("/orders/{oid}/parcels", response_model=Order)
def patch_order_parcels(
    oid: int,
    body: OrderParcelsPatch,
    user: sqlite3.Row = Depends(require_permission("order:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        current = [int(pid) for pid in decode_json(row["parcel_ids"]) or []]
        if body.remove:
            current = [pid for pid in current if pid not in set(body.remove)]
        if body.add:
            existing = set(current)
            for pid in body.add:
                parcel = get_parcel_or_404(conn, pid)
                if parcel["customer_id"] != row["customer_id"]:
                    raise HTTPException(status_code=400, detail=f"parcel {pid} belongs to a different customer")
                if is_parcel_assigned(conn, pid, exclude_order_id=oid):
                    raise HTTPException(status_code=400, detail=f"parcel {pid} already in another order")
                if pid not in existing:
                    current.append(pid)
                    existing.add(pid)
        conn.execute("UPDATE orders SET parcel_ids = ? WHERE id = ?", (encode_json(current), oid))
        conn.commit()
        return row_to_order(get_order_or_404(conn, oid))
    finally:
        conn.close()


@app.patch("/orders/{oid}/override_price")
def override_price(
    oid: int,
    body: OverridePrice,
    user: sqlite3.Row = Depends(require_permission("price:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        value = round(float(body.final_price), 2)
        conn.execute("UPDATE orders SET final_price = ? WHERE id = ?", (value, oid))
        conn.commit()
        return {"final_price": value}
    finally:
        conn.close()


@app.patch("/orders/{oid}/order_no")
def patch_order_no(
    oid: int,
    body: OrderNoPatch,
    user: sqlite3.Row = Depends(require_permission("order:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        value = body.order_no.strip() or None
        conn.execute("UPDATE orders SET order_no = ? WHERE id = ?", (value, oid))
        conn.commit()
        return {"order_no": value}
    finally:
        conn.close()


@app.get("/tasks", response_model=List[Task])
def list_tasks(
    order_id: Optional[int] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("task:view")),
):
    conn = get_conn()
    try:
        sql = """
            SELECT t.*
            FROM tasks t
            JOIN orders o ON o.id = t.order_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if user["role"] == UserRole.customer.value:
            sql += " AND o.customer_id = ?"
            params.append(user["customer_id"])
        if order_id is not None:
            sql += " AND t.order_id = ?"
            params.append(order_id)
        sql += " ORDER BY t.id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [row_to_task(row) for row in rows]
    finally:
        conn.close()


@app.patch("/tasks/{tid}/start")
def start_task(tid: int, user: sqlite3.Row = Depends(require_permission("task:start"))):
    conn = get_conn()
    try:
        task = get_task_or_404(conn, tid)
        if task["status"] != TaskStatus.TODO.value:
            raise HTTPException(status_code=400, detail="task is not in TODO status")
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (TaskStatus.IN_PROGRESS.value, tid))
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (OrderStatus.PACKING.value, task["order_id"]))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.patch("/tasks/{tid}/complete")
def complete_task(
    tid: int,
    body: TaskComplete,
    user: sqlite3.Row = Depends(require_permission("task:complete")),
):
    conn = get_conn()
    try:
        task = get_task_or_404(conn, tid)
        if task["status"] != TaskStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=400, detail="task is not in progress")
        order = get_order_or_404(conn, task["order_id"])
        actual_weight = float(body.actual_weight) if body.actual_weight is not None else task["actual_weight"]
        conn.execute(
            "UPDATE tasks SET actual_weight = ?, status = ? WHERE id = ?",
            (actual_weight, TaskStatus.IN_PROGRESS.value, tid),
        )
        conn.execute(
            "UPDATE orders SET actual_weight = ?, status = ? WHERE id = ?",
            (actual_weight if actual_weight is not None else order["actual_weight"], OrderStatus.READY_TO_SHIP.value, task["order_id"]),
        )
        now = utc_now_iso()
        for pid in decode_json(order["parcel_ids"]) or []:
            conn.execute(
                "UPDATE parcels SET status = ?, packed_at = ? WHERE id = ?",
                (ParcelStatus.PACKED.value, now, pid),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.patch("/orders/{oid}/ship")
def ship_order(oid: int, user: sqlite3.Row = Depends(require_permission("order:ship"))):
    conn = get_conn()
    try:
        order = get_order_or_404(conn, oid)
        ensure_customer_scope(user, order["customer_id"])
        if order["status"] != OrderStatus.READY_TO_SHIP.value:
            raise HTTPException(status_code=400, detail="order is not ready to ship")
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (OrderStatus.COMPLETED.value, oid))
        conn.execute("UPDATE tasks SET status = ? WHERE order_id = ?", (TaskStatus.DONE.value, oid))
        now = utc_now_iso()
        for pid in decode_json(order["parcel_ids"]) or []:
            conn.execute("UPDATE parcels SET shipped_at = ? WHERE id = ?", (now, pid))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def upsert_notification(conn: sqlite3.Connection, type_: str, customer_id: int, payload: Dict[str, Any]):
    conn.execute(
        """
        INSERT INTO notifications (type, customer_id, payload, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(type, customer_id) DO UPDATE SET
            payload = excluded.payload,
            created_at = excluded.created_at
        """,
        (type_, customer_id, encode_json(payload), utc_now_iso()),
    )


@app.post("/notify/ready_to_ship")
def notify_ready(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("notification:view")),
):
    conn = get_conn()
    try:
        payload = {"customer_id": body.customer_id, "message": body.message or "ready", "ts": utc_now_iso()}
        upsert_notification(conn, "ready_to_ship", body.customer_id, payload)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post("/notify/shipped")
def notify_shipped(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("order:ship")),
):
    conn = get_conn()
    try:
        payload = {"customer_id": body.customer_id, "message": body.message or "shipped", "ts": utc_now_iso()}
        upsert_notification(conn, "shipped", body.customer_id, payload)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post("/notify/ready_to_pack")
def notify_ready_to_pack(
    body: ReadyNotify,
    user: sqlite3.Row = Depends(require_permission("notification:create")),
):
    ensure_customer_scope(user, body.customer_id)
    conn = get_conn()
    try:
        ensure_customer_exists(conn, body.customer_id)
        now = utc_now()
        payload = {
            "customer_id": body.customer_id,
            "message": body.message or "ready_to_pack",
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
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
        upsert_notification(conn, "ready_to_pack", body.customer_id, payload)

        if body.parcel_ids:
            ids = set(body.parcel_ids)
            rows = conn.execute(
                """
                SELECT p.*
                FROM parcels p
                WHERE p.customer_id = ? AND p.status = ?
                """,
                (body.customer_id, ParcelStatus.ARRIVED.value),
            ).fetchall()
            selectable = [row for row in rows if row["id"] in ids and not is_parcel_assigned(conn, row["id"])]
        else:
            rows = conn.execute(
                "SELECT * FROM parcels WHERE customer_id = ? AND status = ?",
                (body.customer_id, ParcelStatus.ARRIVED.value),
            ).fetchall()
            selectable = [row for row in rows if not is_parcel_assigned(conn, row["id"])]

        created_order_id = None
        draft = conn.execute(
            "SELECT * FROM orders WHERE customer_id = ? AND status = ? ORDER BY id LIMIT 1",
            (body.customer_id, OrderStatus.DRAFT.value),
        ).fetchone()

        now_iso = utc_now_iso()
        if draft is not None:
            current = [int(pid) for pid in decode_json(draft["parcel_ids"]) or []]
            current_ids = set(current)
            for row in selectable:
                if row["id"] not in current_ids:
                    current.append(row["id"])
                    current_ids.add(row["id"])
            conn.execute(
                "UPDATE orders SET parcel_ids = ?, status = ?, forwarding = ? WHERE id = ?",
                (
                    encode_json(current),
                    OrderStatus.READY_TO_PACK.value,
                    encode_json(
                        {
                            "channel": body.channel,
                            "destination": body.destination,
                            "service": body.service,
                            "consignee": payload["consignee"],
                        }
                    ),
                    draft["id"],
                ),
            )
            created_order_id = draft["id"]
        elif selectable:
            order = create_order_record(
                conn,
                body.customer_id,
                [row["id"] for row in selectable],
                status=OrderStatus.READY_TO_PACK,
                forwarding={
                    "channel": body.channel,
                    "destination": body.destination,
                    "service": body.service,
                    "consignee": payload["consignee"],
                    "actual_weight": 0.0,
                    "volumetric_weight": 0.0,
                },
            )
            created_order_id = order.id

        for row in selectable:
            conn.execute(
                "UPDATE parcels SET status = ?, pack_requested_at = ? WHERE id = ?",
                (ParcelStatus.PACK_REQUESTED.value, now_iso, row["id"]),
            )
        conn.commit()
        return {"ok": True, "order_id": created_order_id}
    finally:
        conn.close()


@app.get("/notifications")
def get_notifications(
    type: Optional[str] = None,
    customer_id: Optional[int] = None,
    user: sqlite3.Row = Depends(require_permission("notification:view")),
):
    conn = get_conn()
    try:
        effective_customer_id = customer_id
        if user["role"] == UserRole.customer.value:
            effective_customer_id = user["customer_id"]
        sql = "SELECT * FROM notifications WHERE 1 = 1"
        params: list[Any] = []
        if type:
            sql += " AND type = ?"
            params.append(type)
        if effective_customer_id is not None:
            sql += " AND customer_id = ?"
            params.append(effective_customer_id)
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        items = [decode_json(row["payload"]) for row in rows]
        if type:
            return items
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["type"], []).append(decode_json(row["payload"]))
        return grouped
    finally:
        conn.close()


@app.delete("/notifications")
def clear_notifications(
    type: Optional[str] = None,
    user: sqlite3.Row = Depends(require_permission("notification:clear")),
):
    conn = get_conn()
    try:
        if type:
            conn.execute("DELETE FROM notifications WHERE type = ?", (type,))
        else:
            conn.execute("DELETE FROM notifications")
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/customers/{cid}/parcels", response_model=List[Parcel])
def parcels_by_customer(
    cid: int,
    status: Optional[ParcelStatus] = None,
    user: sqlite3.Row = Depends(require_permission("parcel:view")),
):
    ensure_customer_scope(user, cid)
    conn = get_conn()
    try:
        sql = """
            SELECT p.*, c.name AS customer_name
            FROM parcels p
            LEFT JOIN customers c ON c.id = p.customer_id
            WHERE p.customer_id = ?
        """
        params: list[Any] = [cid]
        if status:
            sql += " AND p.status = ?"
            params.append(status.value)
        sql += " ORDER BY p.id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [row_to_parcel(row) for row in rows]
    finally:
        conn.close()


@app.post("/orders/auto", response_model=Order)
def auto_create_order(
    req: AutoOrderReq,
    user: sqlite3.Row = Depends(require_permission("order:create")),
):
    ensure_customer_scope(user, req.customer_id)
    conn = get_conn()
    try:
        default_statuses = {ParcelStatus.SUBMITTED.value, ParcelStatus.IN_TRANSIT.value, ParcelStatus.ARRIVED.value}
        allow = {status.value for status in req.statuses} if req.statuses else default_statuses
        rows = conn.execute("SELECT * FROM parcels WHERE customer_id = ?", (req.customer_id,)).fetchall()
        selectable = [row for row in rows if row["status"] in allow and not is_parcel_assigned(conn, row["id"])]
        if not selectable:
            raise HTTPException(status_code=400, detail="no eligible parcels to create order")
        return create_order_record(conn, req.customer_id, [row["id"] for row in selectable])
    finally:
        conn.close()


@app.get("/customers", response_model=List[Customer])
def customers(
    page: int = 1,
    page_size: int = 50,
    q: Optional[str] = None,
    user: sqlite3.Row = Depends(require_permission("customer:view")),
):
    conn = get_conn()
    try:
        sql = "SELECT * FROM customers WHERE 1 = 1"
        params: list[Any] = []
        if q:
            sql += " AND lower(name) LIKE ?"
            params.append(f"%{q.lower()}%")
        sql += " ORDER BY id LIMIT ? OFFSET ?"
        params.extend([page_size, max(0, (page - 1) * page_size)])
        rows = conn.execute(sql, params).fetchall()
        return [Customer(id=row["id"], name=row["name"]) for row in rows]
    finally:
        conn.close()


@app.get("/customers/{cid}", response_model=Customer)
def customer_detail(cid: int, user: sqlite3.Row = Depends(require_permission("customer:view"))):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="customer not found")
        return Customer(id=row["id"], name=row["name"])
    finally:
        conn.close()


@app.post("/parcels/{pid}/files")
async def upload_parcel_files(
    pid: int,
    files: List[UploadFile] = File(...),
    user: sqlite3.Row = Depends(require_permission("parcel:create")),
):
    conn = get_conn()
    try:
        parcel = get_parcel_or_404(conn, pid)
        ensure_customer_scope(user, parcel["customer_id"])
    finally:
        conn.close()
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="max 5 files")
    ok_types = {"image/png", "image/jpeg", "image/webp"}
    saved = []
    directory = UPLOAD_DIR / str(pid)
    directory.mkdir(parents=True, exist_ok=True)
    for upload in files:
        if upload.content_type not in ok_types:
            raise HTTPException(status_code=400, detail=f"unsupported type: {upload.content_type}")
        data = await upload.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{upload.filename} exceeds 5MB")
        path = directory / upload.filename
        path.write_bytes(data)
        saved.append({"filename": upload.filename, "size": len(data)})
    return {"saved": saved}
