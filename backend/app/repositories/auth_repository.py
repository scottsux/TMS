import sqlite3
from typing import Optional


def get_user_by_email(conn: sqlite3.Connection, email: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT u.id, u.email, u.password_hash, u.role, u.customer_id, c.name AS customer_name
        FROM users u
        LEFT JOIN customers c ON c.id = u.customer_id
        WHERE lower(u.email) = lower(?)
        """,
        (email,),
    ).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT u.id, u.email, u.role, u.customer_id, c.name AS customer_name
        FROM users u
        LEFT JOIN customers c ON c.id = u.customer_id
        WHERE u.id = ?
        """,
        (user_id,),
    ).fetchone()
