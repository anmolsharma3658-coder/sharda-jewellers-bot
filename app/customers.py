"""Customer directory — SQLite-backed store for Sharda Jewellers bot.

Features:
  • Auto-save every customer who messages the bot
  • Recognize returning customers with visit history
  • CSV import / export for bulk management
  • Tagging and notes for CRM-like usage
"""

import csv
import io
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
            CREATE TABLE IF NOT EXISTS customers (
                phone       TEXT PRIMARY KEY,
                name        TEXT NOT NULL DEFAULT '',
                first_seen  TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                msg_count   INTEGER NOT NULL DEFAULT 1,
                tags        TEXT NOT NULL DEFAULT '',
                notes       TEXT NOT NULL DEFAULT '',
                language    TEXT NOT NULL DEFAULT 'hi'
            )
        """)
        try:
            _conn.execute("ALTER TABLE customers ADD COLUMN language TEXT NOT NULL DEFAULT 'hi'")
        except sqlite3.OperationalError:
            pass
        _conn.commit()
        logger.info("Customer DB ready at %s", DB_PATH)
    return _conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─── Core CRUD ─────────────────────────────────────────────

def upsert_customer(phone: str, name: str = "", language: str = "hi") -> dict:
    """Insert a new customer or update last_seen / msg_count / language."""
    conn = _get_conn()
    now = _now_iso()

    existing = conn.execute(
        "SELECT * FROM customers WHERE phone = ?", (phone,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE customers
               SET name      = CASE WHEN ? != '' THEN ? ELSE name END,
                   last_seen = ?,
                   msg_count = msg_count + 1,
                   language  = ?
             WHERE phone = ?
        """, (name, name, now, language, phone))
        conn.commit()
    else:
        conn.execute("""
            INSERT INTO customers (phone, name, first_seen, last_seen, msg_count, language)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (phone, name, now, now, language))
        conn.commit()

    row = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
    return dict(row)


def get_customer(phone: str) -> dict | None:
    row = _get_conn().execute(
        "SELECT * FROM customers WHERE phone = ?", (phone,)
    ).fetchone()
    return dict(row) if row else None


def get_all_customers() -> list[dict]:
    rows = _get_conn().execute(
        "SELECT * FROM customers ORDER BY last_seen DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_customer_count() -> int:
    row = _get_conn().execute("SELECT COUNT(*) as cnt FROM customers").fetchone()
    return row["cnt"]


def update_tags(phone: str, tags: str) -> bool:
    conn = _get_conn()
    conn.execute("UPDATE customers SET tags = ? WHERE phone = ?", (tags, phone))
    conn.commit()
    return conn.total_changes > 0


def update_notes(phone: str, notes: str) -> bool:
    conn = _get_conn()
    conn.execute("UPDATE customers SET notes = ? WHERE phone = ?", (notes, phone))
    conn.commit()
    return conn.total_changes > 0


def delete_customer(phone: str) -> bool:
    conn = _get_conn()
    conn.execute("DELETE FROM customers WHERE phone = ?", (phone,))
    conn.commit()
    return conn.total_changes > 0


def search_customers(query: str) -> list[dict]:
    """Search by name or phone (partial match)."""
    like = f"%{query}%"
    rows = _get_conn().execute(
        "SELECT * FROM customers WHERE phone LIKE ? OR name LIKE ? ORDER BY last_seen DESC",
        (like, like),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── CSV Import / Export ───────────────────────────────────

def export_csv() -> str:
    """Export all customers as a CSV string."""
    customers = get_all_customers()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "phone", "name", "first_seen", "last_seen", "msg_count", "tags", "notes", "language",
    ])
    writer.writeheader()
    writer.writerows(customers)
    return output.getvalue()


def import_csv(csv_text: str) -> dict:
    """Import customers from CSV text.

    Expected columns: phone, name (optional: tags, notes).
    Returns {"added": N, "updated": N, "errors": N}.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    added = updated = errors = 0
    conn = _get_conn()
    now = _now_iso()

    for row in reader:
        phone = (row.get("phone") or "").strip()
        if not phone:
            errors += 1
            continue

        phone = phone.lstrip("+").replace(" ", "").replace("-", "")
        name = (row.get("name") or "").strip()
        tags = (row.get("tags") or "").strip()
        notes = (row.get("notes") or "").strip()

        existing = conn.execute(
            "SELECT phone FROM customers WHERE phone = ?", (phone,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE customers
                   SET name  = CASE WHEN ? != '' THEN ? ELSE name END,
                       tags  = CASE WHEN ? != '' THEN ? ELSE tags END,
                       notes = CASE WHEN ? != '' THEN ? ELSE notes END
                 WHERE phone = ?
            """, (name, name, tags, tags, notes, notes, phone))
            updated += 1
        else:
            conn.execute("""
                INSERT INTO customers (phone, name, first_seen, last_seen, msg_count, tags, notes)
                VALUES (?, ?, ?, ?, 0, ?, ?)
            """, (phone, name, now, now, tags, notes))
            added += 1

    conn.commit()
    return {"added": added, "updated": updated, "errors": errors}


# ─── Broadcast helpers ─────────────────────────────────────

def get_broadcast_targets(tag_filter: str = "") -> list[dict]:
    """Get customer phones for broadcast, optionally filtered by tag."""
    if tag_filter:
        like = f"%{tag_filter}%"
        rows = _get_conn().execute(
            "SELECT phone, name FROM customers WHERE tags LIKE ? ORDER BY last_seen DESC",
            (like,),
        ).fetchall()
    else:
        rows = _get_conn().execute(
            "SELECT phone, name FROM customers ORDER BY last_seen DESC"
        ).fetchall()
    return [dict(r) for r in rows]
