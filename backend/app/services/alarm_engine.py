"""Alarm evaluation + historical alarm records.

Key design point: every poll calls `evaluate` which reads the *current* rule
set, so an edited rule takes effect immediately. When an alarm is persisted the
matching level/rule_id/rule_version are copied into alarm_record, so later rule
edits never change how a past record is displayed.
"""
from typing import Any, Dict, List, Optional

from app import db

# higher number = more severe; when several rules match, only the worst one alarms
_SEVERITY = {"info": 1, "warning": 2, "critical": 3}


def _matches(rule: Dict[str, Any], value: float) -> bool:
    if not rule["enabled"]:
        return False
    upper, lower, cond = rule["upperLimit"], rule["lowerLimit"], rule["condition"]
    if cond == "gt":
        return upper is not None and value > upper
    if cond == "lt":
        return lower is not None and value < lower
    if cond == "between":
        # 超出区间: 值不在 (lower, upper) 之间
        return upper is not None and lower is not None and (value > upper or value < lower)
    if cond == "outside":
        # 落入禁区: 值落在 [lower, upper] 之间
        return upper is not None and lower is not None and lower <= value <= upper
    return False


def active_rules() -> List[Dict[str, Any]]:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT * FROM alarm_rule WHERE enabled = 1").fetchall()
    return [db.row_to_rule(r) for r in rows]


def evaluate(point: str, value: float, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return the most severe currently-matching rule for a point, or None.

    Rules whose scope is a non-empty list not containing device_id are skipped.
    """
    best: Optional[Dict[str, Any]] = None
    for rule in active_rules():
        if rule["point"] != point:
            continue
        if device_id is not None and rule["scope"] and device_id not in rule["scope"]:
            continue
        if _matches(rule, value) and (best is None or _SEVERITY[rule["level"]] > _SEVERITY[best["level"]]):
            best = rule
    return best


def insert_alarm(point: str, value: float, device_id: Optional[str], device_name: Optional[str],
                 unit: str, rule: Dict[str, Any]) -> Dict[str, Any]:
    # snapshot: level / rule id / version are frozen here
    upper, lower, cond = rule["upperLimit"], rule["lowerLimit"], rule["condition"]
    limit_txt = {
        "gt": f">{upper}",
        "lt": f"<{lower}",
        "between": f"超出[{lower}, {upper}]",
        "outside": f"落入[{lower}, {upper}]",
    }[cond]
    scope_txt = f"(规则#{rule['id']}v{rule['version']})"
    message = f"{device_name or device_id or ''} {point} 越限: {value}{unit}，判定{limit_txt} {scope_txt}"

    with db.transaction() as conn:
        cur = conn.execute(
            """INSERT INTO alarm_record
               (point, device_id, device_name, value, unit, level, rule_id, rule_version, message, raised_at, acknowledged)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (point, device_id, device_name, value, unit, rule["level"], rule["id"], rule["version"],
             message, db.now_iso()),
        )
        # trim history to the newest 500 rows
        conn.execute("DELETE FROM alarm_record WHERE id NOT IN (SELECT id FROM alarm_record ORDER BY id DESC LIMIT 500)")
        row = conn.execute("SELECT * FROM alarm_record WHERE id=?", (cur.lastrowid,)).fetchone()
    return db.row_to_alarm(row)


def list_alarms(point: Optional[str] = None, device_id: Optional[str] = None,
                level: Optional[str] = None, acknowledged: Optional[bool] = None,
                limit: int = 200) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM alarm_record WHERE 1=1"
    params: List[Any] = []
    if point:
        sql += " AND point = ?"
        params.append(point)
    if device_id:
        sql += " AND device_id = ?"
        params.append(device_id)
    if level:
        sql += " AND level = ?"
        params.append(level)
    if acknowledged is not None:
        sql += " AND acknowledged = ?"
        params.append(1 if acknowledged else 0)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db.get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [db.row_to_alarm(r) for r in rows]


def acknowledge(alarm_id: int) -> bool:
    with db.transaction() as conn:
        cur = conn.execute("UPDATE alarm_record SET acknowledged=1 WHERE id=?", (alarm_id,))
        return cur.rowcount > 0
