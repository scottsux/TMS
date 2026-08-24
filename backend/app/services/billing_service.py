import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import Depends, File, HTTPException, Query, UploadFile

from .. import config
from ..core.permissions import ensure_customer_scope, require_permission
from ..core.security import create_token, utc_now, utc_now_iso, verify_password
from ..db.connection import get_conn
from ..models.enums import ExceptionStatus, OrderStatus, ParcelStatus, TaskStatus, UserRole
from ..repositories.common import *  # noqa: F403
from ..schemas import *  # noqa: F403
from .order_rules import ensure_no_open_exceptions, ensure_weight_update_allowed, exception_types_for_role, price_formula, record_order_audit

def patch_order_price(
    oid: int,
    body: PricePatch,
    user: sqlite3.Row = Depends(require_permission("price:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        if row["status"] != OrderStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="only completed orders can be priced")
        ensure_no_open_exceptions(conn, oid)
        actual_weight = float(row["actual_weight"] or 0)
        if body.actual_weight is not None and float(body.actual_weight) != actual_weight:
            raise HTTPException(status_code=400, detail="completed order weight cannot be changed during pricing")
        final_price = price_formula(actual_weight, body.rate_per_kg, body.extra_fee)
        before_value = {"actual_weight": actual_weight, "final_price": row["final_price"]}
        after_value = {
            "actual_weight": actual_weight,
            "rate_per_kg": float(body.rate_per_kg),
            "extra_fee": float(body.extra_fee),
            "final_price": final_price,
        }
        conn.execute(
            "UPDATE orders SET final_price = ? WHERE id = ?",
            (final_price, oid),
        )
        record_order_audit(
            conn,
            oid,
            "price:calculate",
            user["id"],
            before_value,
            after_value,
            body.reason.strip() if body.reason else "automatic price calculation",
        )
        conn.commit()
        return {"final_price": final_price}
    finally:
        conn.close()


def patch_order_volumetric(
    oid: int,
    body: VolumetricPatch,
    user: sqlite3.Row = Depends(require_permission("weight:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        ensure_weight_update_allowed(row, user)
        forwarding = decode_json(row["forwarding"]) or {}
        forwarding["volumetric_weight"] = float(body.volumetric_weight)
        conn.execute(
            "UPDATE orders SET volumetric_weight = ?, forwarding = ? WHERE id = ?",
            (float(body.volumetric_weight), encode_json(forwarding), oid),
        )
        record_order_audit(
            conn,
            oid,
            "weight:volumetric_update",
            user["id"],
            {"volumetric_weight": float(row["volumetric_weight"] or 0)},
            {"volumetric_weight": float(body.volumetric_weight)},
        )
        conn.commit()
        return {"volumetric_weight": float(body.volumetric_weight)}
    finally:
        conn.close()


def patch_order_actual_weight(
    oid: int,
    body: ActualWeightPatch,
    user: sqlite3.Row = Depends(require_permission("weight:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        ensure_weight_update_allowed(row, user)
        forwarding = decode_json(row["forwarding"]) or {}
        forwarding["actual_weight"] = float(body.actual_weight)
        conn.execute(
            "UPDATE orders SET actual_weight = ?, forwarding = ? WHERE id = ?",
            (float(body.actual_weight), encode_json(forwarding), oid),
        )
        record_order_audit(
            conn,
            oid,
            "weight:actual_update",
            user["id"],
            {"actual_weight": float(row["actual_weight"] or 0)},
            {"actual_weight": float(body.actual_weight)},
        )
        conn.commit()
        return {"actual_weight": float(body.actual_weight)}
    finally:
        conn.close()


def override_price(
    oid: int,
    body: OverridePrice,
    user: sqlite3.Row = Depends(require_permission("price:update")),
):
    conn = get_conn()
    try:
        row = get_order_or_404(conn, oid)
        ensure_customer_scope(user, row["customer_id"])
        if row["status"] != OrderStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="only completed orders can be repriced")
        ensure_no_open_exceptions(conn, oid)
        value = round(float(body.final_price), 2)
        conn.execute("UPDATE orders SET final_price = ? WHERE id = ?", (value, oid))
        record_order_audit(
            conn,
            oid,
            "price:override",
            user["id"],
            {"final_price": row["final_price"]},
            {"final_price": value},
            body.reason.strip(),
        )
        conn.commit()
        return {"final_price": value}
    finally:
        conn.close()

