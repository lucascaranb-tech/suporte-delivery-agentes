import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"

# Subir este número quando o formato das tabelas mudar: init_db() recria o banco de demonstração.
SCHEMA_VERSION = 2


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


def reset_db():
    """Apaga tudo e recarrega os dados de exemplo (só para demonstração e evals)."""
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
        ("A100", "c1", "Pizzaria Bella",
         [{"name": "Pizza calabresa", "price": 54.90}, {"name": "Refrigerante 2L", "price": 8.00}],
         62.90, "delivered", 0, 0),
        ("A101", "c1", "Burger Lab",
         [{"name": "X-Bacon", "price": 29.90}, {"name": "Batata média", "price": 8.60}],
         38.50, "delivered", 0, 45),
        ("A102", "c1", "Sushi Go",
         [{"name": "Combo 20 peças", "price": 79.00}],
         79.00, "on_the_way", 12, 0),
        ("B200", "c2", "Açaí Express",
         [{"name": "Açaí 500ml", "price": 25.00}],
         25.00, "delivered", 0, 0),
    ]
    for o in seed:
        c.execute(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)",
            (o[0], o[1], o[2], json.dumps(o[3], ensure_ascii=False), o[4], o[5], o[6], o[7]),
        )
    c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    c.commit()
    c.close()


def init_db():
    """Cria o banco só se ele não existir ou estiver em formato antigo.
    Reiniciar a API não apaga mais reembolsos, tickets e auditoria."""
    c = _conn()
    try:
        versao = c.execute("PRAGMA user_version").fetchone()[0]
    finally:
        c.close()
    if versao != SCHEMA_VERSION:
        reset_db()
