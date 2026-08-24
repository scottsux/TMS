import sqlite3

from fastapi import Depends, HTTPException

from ..models.enums import UserRole
from .security import get_current_user


PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.customer: {
        "parcel:create", "parcel:view", "order:view", "notification:create", "exception:create", "exception:view"
    },
    UserRole.staff: {
        "parcel:create", "parcel:view", "parcel:arrived", "parcel:update", "order:create", "order:view",
        "order:update", "order:ship", "task:view", "customer:view", "price:update", "weight:update",
        "exception:create", "exception:view", "exception:resolve", "audit:view", "notification:view",
        "notification:clear",
    },
    UserRole.operator: {
        "parcel:view", "order:view", "task:view", "task:start", "task:complete", "notification:view",
        "weight:update", "exception:create", "exception:view",
    },
}


def require_permission(permission: str):
    def dependency(user: sqlite3.Row = Depends(get_current_user)) -> sqlite3.Row:
        if permission not in PERMISSIONS[UserRole(user["role"])]:
            raise HTTPException(status_code=403, detail="forbidden")
        return user

    return dependency


def ensure_customer_scope(user: sqlite3.Row, customer_id: int) -> None:
    if user["role"] == UserRole.customer.value and user["customer_id"] != customer_id:
        raise HTTPException(status_code=403, detail="forbidden")
