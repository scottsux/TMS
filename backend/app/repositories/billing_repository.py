import sqlite3
from typing import Any, Dict, Optional

from ..repositories.common import encode_json


def update_volumetric_weight(
    conn: sqlite3.Connection,
    order_id: int,
    volumetric_weight: float,
    forwarding: Dict[str, Any],
) -> None:
    conn.execute(
        "UPDATE orders SET volumetric_weight = ?, forwarding = ? WHERE id = ?",
        (volumetric_weight, encode_json(forwarding), order_id),
    )


def update_actual_weight(
    conn: sqlite3.Connection,
    order_id: int,
    actual_weight: float,
    forwarding: Dict[str, Any],
) -> None:
    conn.execute(
        "UPDATE orders SET actual_weight = ?, forwarding = ? WHERE id = ?",
        (actual_weight, encode_json(forwarding), order_id),
    )


def update_final_price(conn: sqlite3.Connection, order_id: int, final_price: float) -> None:
    conn.execute("UPDATE orders SET final_price = ? WHERE id = ?", (final_price, order_id))
