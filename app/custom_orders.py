"""Custom design / inspiration orders — customer photos logged + owner alerts."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "customers.db"
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_orders (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                phone          TEXT NOT NULL,
                name           TEXT NOT NULL DEFAULT '',
                wa_message_id  TEXT,
                media_id       TEXT NOT NULL,
                mime_type      TEXT,
                caption        TEXT NOT NULL DEFAULT '',
                chat_snippet   TEXT NOT NULL DEFAULT '',
                created_at     TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'new'
            )
        """)
        _conn.commit()
        logger.info("custom_orders table ready")
    return _conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_custom_order(
    phone: str,
    name: str,
    wa_message_id: str,
    media_id: str,
    mime_type: str | None,
    caption: str,
    chat_snippet: str,
) -> int:
    """Insert a row; returns new id."""
    conn = _get_conn()
    cur = conn.execute(
        """
        INSERT INTO custom_orders
            (phone, name, wa_message_id, media_id, mime_type, caption, chat_snippet, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """,
        (phone, name, wa_message_id, media_id, mime_type or "", caption, chat_snippet, _now_iso()),
    )
    conn.commit()
    oid = int(cur.lastrowid)
    logger.info("custom_order #%s from %s", oid, phone)
    return oid


def list_custom_orders(limit: int = 100, status: str | None = None) -> list[dict]:
    conn = _get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM custom_orders WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM custom_orders ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_order_status(order_id: int, status: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE custom_orders SET status = ? WHERE id = ?",
        (status, order_id),
    )
    conn.commit()
    return cur.rowcount > 0


def count_new_orders() -> int:
    row = _get_conn().execute(
        "SELECT COUNT(*) AS c FROM custom_orders WHERE status = 'new'"
    ).fetchone()
    return int(row["c"])
