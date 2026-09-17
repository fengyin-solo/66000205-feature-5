"""SQLite persistence layer (stdlib sqlite3).

Holds three things the feature needs:
- alarm_rule        : per-point configurable thresholds / condition / level / scope
- audit_log         : who changed what, when (before/after snapshot)
- alarm_record      : historical alarms, level snapshotted at raise time
- idempotency_key   : de-dup retried saves so a retry never creates a second rule/audit row
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

DB_DIR = os.environ.get("ALARM_DB_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
DB_PATH = os.path.join(DB_DIR, "app.db")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_conn() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS alarm_rule (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                point           TEXT    NOT NULL,
                condition       TEXT    NOT NULL CHECK (condition IN ('gt','lt','between','outside')),
                upper_limit     REAL,
                lower_limit     REAL,
                level           TEXT    NOT NULL CHECK (level IN ('info','warning','critical')),
                scope           TEXT    NOT NULL DEFAULT '[]',
                enabled         INTEGER NOT NULL DEFAULT 1,
                version         INTEGER NOT NULL DEFAULT 1,
                created_by      TEXT    NOT NULL,
                updated_by      TEXT    NOT NULL,
                created_at      TEXT    NOT NULL,
                updated_at      TEXT    NOT NULL,
                UNIQUE (point, level, scope)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id     INTEGER,
                point       TEXT    NOT NULL,
                action      TEXT    NOT NULL CHECK (action IN ('create','update','enable','disable')),
                operator    TEXT    NOT NULL,
                changed_at  TEXT    NOT NULL,
                changes     TEXT    NOT NULL DEFAULT '{}',
                before_json TEXT,
                after_json  TEXT
            );

            CREATE TABLE IF NOT EXISTS alarm_record (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                point       TEXT    NOT NULL,
                device_id   TEXT,
                device_name TEXT,
                value       REAL    NOT NULL,
                unit        TEXT    NOT NULL DEFAULT '',
                level       TEXT    NOT NULL,
                rule_id     INTEGER,
                rule_version INTEGER,
                message     TEXT    NOT NULL,
                raised_at   TEXT    NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS idempotency_key (
                key         TEXT PRIMARY KEY,
                status      TEXT NOT NULL,
                status_code INTEGER,
                response    TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );
            """
        )


def row_to_rule(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "point": row["point"],
        "condition": row["condition"],
        "upperLimit": row["upper_limit"],
        "lowerLimit": row["lower_limit"],
        "level": row["level"],
        "scope": json.loads(row["scope"]),
        "enabled": bool(row["enabled"]),
        "version": row["version"],
        "createdBy": row["created_by"],
        "updatedBy": row["updated_by"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def row_to_audit(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    return {
        "id": d["id"],
        "ruleId": d["rule_id"],
        "point": d["point"],
        "action": d["action"],
        "operator": d["operator"],
        "changedAt": d["changed_at"],
        "changes": json.loads(d["changes"]) if d.get("changes") else {},
        "before": json.loads(d["before_json"]) if d.get("before_json") else None,
        "after": json.loads(d["after_json"]) if d.get("after_json") else None,
    }


def row_to_alarm(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "point": row["point"],
        "deviceId": row["device_id"],
        "deviceName": row["device_name"],
        "value": row["value"],
        "unit": row["unit"],
        "level": row["level"],
        "ruleId": row["rule_id"],
        "ruleVersion": row["rule_version"],
        "message": row["message"],
        "raisedAt": row["raised_at"],
        "acknowledged": bool(row["acknowledged"]),
    }
