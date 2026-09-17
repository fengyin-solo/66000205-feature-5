"""SQLite persistence for threshold rules, alarm records and audit logs."""
import sqlite3
import threading
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "monitor.db"

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS threshold_rules (
    id TEXT PRIMARY KEY,
    client_request_id TEXT UNIQUE,          -- 幂等键：保存失败重试不产生重复记录
    device_id TEXT NOT NULL,                -- '*' 表示全部设备
    register_address INTEGER NOT NULL DEFAULT 0,
    register_name TEXT NOT NULL,
    lower_limit REAL,
    upper_limit REAL,
    condition TEXT NOT NULL,                -- above_upper / below_lower / out_of_range / in_range
    level TEXT NOT NULL,                    -- info / warning / critical
    enabled INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL,
    created_at INTEGER NOT NULL,            -- epoch ms
    updated_by TEXT,
    updated_at INTEGER
);
-- 同一点位、同一判定条件、同一等级只允许一条规则，从数据库层面防重复
CREATE UNIQUE INDEX IF NOT EXISTS ux_rules_point_condition_level
    ON threshold_rules (device_id, register_name, condition, level);

CREATE TABLE IF NOT EXISTS threshold_rule_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL,
    action TEXT NOT NULL,                   -- create / update / delete
    operator TEXT NOT NULL,
    changed_fields TEXT NOT NULL,           -- JSON array
    before_json TEXT,
    after_json TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alarm_records (
    id TEXT PRIMARY KEY,
    rule_id TEXT,
    device_id TEXT NOT NULL,
    device_name TEXT,
    register_address INTEGER,
    register_name TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    level TEXT NOT NULL,                    -- 产生时的等级快照，之后改规则不影响历史
    message TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_alarm_records_created_at ON alarm_records (created_at DESC);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        conn = get_conn()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
