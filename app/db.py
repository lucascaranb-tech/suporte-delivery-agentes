import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def query_one(sql, params=()):
    c = _conn()
    try:
        row = c.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        c.close()


def query_all(sql, params=()):
    c = _conn()
    try:
        return [dict(r) for r in c.execute(sql, params).fetchall()]
    finally:
        c.close()


def execute(sql, params=()):
    c = _conn()
    try:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def init_db():
    """Reset the database and load fake data (demo only)."""
    c = _conn()
    c.executescript(
        """
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS refunds;
        DROP TABLE IF EXISTS tickets;
        DROP TABLE IF EXISTS audit_log;

        CREATE TABLE orders(
            id TEXT PRIMARY KEY, customer_id TEXT, restaurant TEXT,
            items TEXT, total REAL, status TEXT,
            eta_minutes INTEGER, delay_minutes INTEGER
        );
        CREATE TABLE refunds(
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT,
            amount REAL, reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT,
            order_id TEXT, summary TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT,
            tool TEXT, args TEXT, result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    seed = [
        ("A100", "c1", "Pizzaria Bella", ["Pizza calabresa", "Refrigerante 2L"], 62.90, "delivered", 0, 0),
        ("A101", "c1", "Burger Lab", ["X-Bacon", "Batata média"], 38.50, "delivered", 0, 45),
        ("A102", "c1", "Sushi Go", ["Combo 20 peças"], 79.00, "on_the_way", 12, 0),
        ("B200", "c2", "Açaí Express", ["Açaí 500ml"], 25.00, "delivered", 0, 0),
    ]
    for o in seed:
        c.execute(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)",
            (o[0], o[1], o[2], json.dumps(o[3], ensure_ascii=False), o[4], o[5], o[6], o[7]),
        )
    c.commit()
    c.close()