"""阈值规则管理 + 告警判定引擎。

规则、告警记录、变更审计全部持久化在 SQLite：
- 判定引擎每次评估时实时读取当前生效规则，规则调整后立即按新口径判定；
- 告警记录落库时保存等级快照，历史记录不随后续规则调整而变化；
- 所有规则变更写入审计表，可追溯"谁在什么时候改了哪一项"。
"""
import json
import math
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_conn, _lock
from app.models.schemas import Reading, ThresholdRuleIn

# 同一规则对同一点位的告警抑制窗口，避免轮询过快时刷屏
ALARM_SUPPRESS_MS = 10_000

CONDITION_LABELS = {
    "above_upper": "高于上限",
    "below_lower": "低于下限",
    "out_of_range": "超出上下限范围",
    "in_range": "处于上下限范围内",
}

RULE_FIELDS = [
    "deviceId", "registerAddress", "registerName",
    "lowerLimit", "upperLimit", "condition", "level", "enabled",
]


class RuleValidationError(Exception):
    def __init__(self, errors: List[Dict[str, str]]):
        self.errors = errors
        super().__init__("; ".join(e["message"] for e in errors))


class DuplicateRuleError(Exception):
    pass


class RuleNotFoundError(Exception):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------- 序列化

def _rule_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "deviceId": row["device_id"],
        "registerAddress": row["register_address"],
        "registerName": row["register_name"],
        "lowerLimit": row["lower_limit"],
        "upperLimit": row["upper_limit"],
        "condition": row["condition"],
        "level": row["level"],
        "enabled": bool(row["enabled"]),
        "createdBy": row["created_by"],
        "createdAt": row["created_at"],
        "updatedBy": row["updated_by"],
        "updatedAt": row["updated_at"],
    }


def _alarm_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "ruleId": row["rule_id"],
        "deviceId": row["device_id"],
        "deviceName": row["device_name"],
        "registerAddress": row["register_address"],
        "registerName": row["register_name"],
        "value": row["value"],
        "unit": row["unit"],
        "level": row["level"],
        "message": row["message"],
        "acknowledged": bool(row["acknowledged"]),
        "createdAt": row["created_at"],
    }


def _audit_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "ruleId": row["rule_id"],
        "action": row["action"],
        "operator": row["operator"],
        "changedFields": json.loads(row["changed_fields"]),
        "before": json.loads(row["before_json"]) if row["before_json"] else None,
        "after": json.loads(row["after_json"]) if row["after_json"] else None,
        "createdAt": row["created_at"],
    }


# ---------------------------------------------------------------- 校验

def validate_rule(data: ThresholdRuleIn) -> List[Dict[str, str]]:
    """保存前校验。返回错误列表（空列表表示通过），每项指明出问题的字段。"""
    errors: List[Dict[str, str]] = []

    if not data.device_id or not data.device_id.strip():
        errors.append({"field": "deviceId", "message": "请选择规则的生效设备范围"})

    if not data.register_name or not data.register_name.strip():
        errors.append({"field": "registerName", "message": "点位名称不能为空"})

    if data.register_address < 0:
        errors.append({"field": "registerAddress", "message": "寄存器地址不能为负数"})

    lower, upper = data.lower_limit, data.upper_limit
    for field, val in (("lowerLimit", lower), ("upperLimit", upper)):
        if val is not None and not math.isfinite(val):
            errors.append({"field": field, "message": "阈值必须是有限数值"})

    cond = data.condition.value
    if cond in ("above_upper",) and upper is None:
        errors.append({"field": "upperLimit", "message": "判定条件为「高于上限」时必须填写上限"})
    if cond in ("below_lower",) and lower is None:
        errors.append({"field": "lowerLimit", "message": "判定条件为「低于下限」时必须填写下限"})
    if cond in ("out_of_range", "in_range"):
        if lower is None:
            errors.append({"field": "lowerLimit", "message": "按范围判定时必须填写下限"})
        if upper is None:
            errors.append({"field": "upperLimit", "message": "按范围判定时必须填写上限"})

    if lower is not None and upper is not None and lower >= upper:
        errors.append({"field": "lowerLimit", "message": f"下限（{lower}）必须小于上限（{upper}）"})
        errors.append({"field": "upperLimit", "message": f"上限（{upper}）必须大于下限（{lower}）"})

    return errors


# ---------------------------------------------------------------- 审计

def _write_audit(conn: sqlite3.Connection, rule_id: str, action: str, operator: str,
                 changed_fields: List[str], before: Optional[Dict], after: Optional[Dict]) -> None:
    conn.execute(
        "INSERT INTO threshold_rule_audits (rule_id, action, operator, changed_fields, before_json, after_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            rule_id, action, operator, json.dumps(changed_fields, ensure_ascii=False),
            json.dumps(before, ensure_ascii=False) if before is not None else None,
            json.dumps(after, ensure_ascii=False) if after is not None else None,
            now_ms(),
        ),
    )


def list_audits(limit: int = 200) -> List[Dict[str, Any]]:
    with _lock:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM threshold_rule_audits ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
    return [_audit_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------- 规则 CRUD

def list_rules() -> List[Dict[str, Any]]:
    with _lock:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM threshold_rules ORDER BY device_id, register_name, condition, upper_limit"
            ).fetchall()
        finally:
            conn.close()
    return [_rule_row_to_dict(r) for r in rows]


def _get_rule_row(conn: sqlite3.Connection, rule_id: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM threshold_rules WHERE id = ?", (rule_id,)).fetchone()


def _find_duplicate(conn: sqlite3.Connection, data: ThresholdRuleIn, exclude_id: Optional[str] = None) -> Optional[sqlite3.Row]:
    sql = ("SELECT * FROM threshold_rules WHERE device_id = ? AND register_name = ?"
           " AND condition = ? AND level = ?")
    params: list = [data.device_id.strip(), data.register_name.strip(), data.condition.value, data.level.value]
    if exclude_id:
        sql += " AND id != ?"
        params.append(exclude_id)
    return conn.execute(sql, params).fetchone()


def create_rule(data: ThresholdRuleIn) -> Tuple[Dict[str, Any], bool]:
    """新增规则。返回 (规则, 是否新建)。

    幂等：同一 client_request_id 重复提交（如保存失败后的重试）直接返回首次创建的记录，
    不会产生重复设置。
    """
    errors = validate_rule(data)
    if errors:
        raise RuleValidationError(errors)

    operator = (data.operator or "").strip() or "admin"
    with _lock:
        conn = get_conn()
        try:
            if data.client_request_id:
                existing = conn.execute(
                    "SELECT * FROM threshold_rules WHERE client_request_id = ?",
                    (data.client_request_id,),
                ).fetchone()
                if existing:  # 重试请求：返回已存在的记录，视为成功
                    return _rule_row_to_dict(existing), False

            if _find_duplicate(conn, data):
                raise DuplicateRuleError("该点位已存在相同判定条件与提醒等级的规则，请勿重复添加")

            rule_id = _new_id("rule")
            now = now_ms()
            try:
                conn.execute(
                    "INSERT INTO threshold_rules"
                    " (id, client_request_id, device_id, register_address, register_name,"
                    "  lower_limit, upper_limit, condition, level, enabled, created_by, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rule_id, data.client_request_id, data.device_id.strip(),
                        data.register_address, data.register_name.strip(),
                        data.lower_limit, data.upper_limit, data.condition.value,
                        data.level.value, 1 if data.enabled else 0, operator, now,
                    ),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                if data.client_request_id:
                    existing = conn.execute(
                        "SELECT * FROM threshold_rules WHERE client_request_id = ?",
                        (data.client_request_id,),
                    ).fetchone()
                    if existing:  # 并发重试：首个请求已落库
                        return _rule_row_to_dict(existing), False
                raise DuplicateRuleError("该点位已存在相同判定条件与提醒等级的规则，请勿重复添加")

            row = _get_rule_row(conn, rule_id)
            rule = _rule_row_to_dict(row)
            _write_audit(conn, rule_id, "create", operator,
                         [f for f in RULE_FIELDS if rule.get(f) is not None], None, rule)
            conn.commit()
            return rule, True
        finally:
            conn.close()


def update_rule(rule_id: str, data: ThresholdRuleIn) -> Dict[str, Any]:
    errors = validate_rule(data)
    if errors:
        raise RuleValidationError(errors)

    operator = (data.operator or "").strip() or "admin"
    with _lock:
        conn = get_conn()
        try:
            row = _get_rule_row(conn, rule_id)
            if not row:
                raise RuleNotFoundError(f"规则 {rule_id} 不存在")
            before = _rule_row_to_dict(row)

            if _find_duplicate(conn, data, exclude_id=rule_id):
                raise DuplicateRuleError("该点位已存在相同判定条件与提醒等级的规则")

            after = {
                "deviceId": data.device_id.strip(),
                "registerAddress": data.register_address,
                "registerName": data.register_name.strip(),
                "lowerLimit": data.lower_limit,
                "upperLimit": data.upper_limit,
                "condition": data.condition.value,
                "level": data.level.value,
                "enabled": data.enabled,
            }
            changed = [f for f in RULE_FIELDS if before.get(f) != after.get(f)]

            now = now_ms()
            try:
                conn.execute(
                    "UPDATE threshold_rules SET device_id=?, register_address=?, register_name=?,"
                    " lower_limit=?, upper_limit=?, condition=?, level=?, enabled=?,"
                    " updated_by=?, updated_at=? WHERE id=?",
                    (
                        after["deviceId"], after["registerAddress"], after["registerName"],
                        after["lowerLimit"], after["upperLimit"], after["condition"],
                        after["level"], 1 if after["enabled"] else 0,
                        operator, now, rule_id,
                    ),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                raise DuplicateRuleError("该点位已存在相同判定条件与提醒等级的规则")

            if changed:  # 有实际变化才留痕
                _write_audit(conn, rule_id, "update", operator, changed, before,
                             _rule_row_to_dict(_get_rule_row(conn, rule_id)))
            conn.commit()
            return _rule_row_to_dict(_get_rule_row(conn, rule_id))
        finally:
            conn.close()


def delete_rule(rule_id: str, operator: str) -> None:
    operator = (operator or "").strip() or "admin"
    with _lock:
        conn = get_conn()
        try:
            row = _get_rule_row(conn, rule_id)
            if not row:
                raise RuleNotFoundError(f"规则 {rule_id} 不存在")
            before = _rule_row_to_dict(row)
            conn.execute("DELETE FROM threshold_rules WHERE id = ?", (rule_id,))
            _write_audit(conn, rule_id, "delete", operator, RULE_FIELDS, before, None)
            conn.commit()
        finally:
            conn.close()


def seed_default_rules() -> None:
    """首次启动时写入与原先硬编码逻辑等价的默认规则，保证行为平滑迁移。"""
    with _lock:
        conn = get_conn()
        try:
            count = conn.execute("SELECT COUNT(*) AS c FROM threshold_rules").fetchone()["c"]
        finally:
            conn.close()
    if count:
        return
    defaults = [
        ThresholdRuleIn(deviceId="dev1", registerAddress=0, registerName="温度",
                        upperLimit=28, condition="above_upper", level="warning",
                        operator="system"),
        ThresholdRuleIn(deviceId="dev1", registerAddress=0, registerName="温度",
                        upperLimit=30, condition="above_upper", level="critical",
                        operator="system"),
    ]
    for d in defaults:
        create_rule(d)


# ---------------------------------------------------------------- 告警判定与记录

def _condition_hit(rule: Dict[str, Any], value: float) -> bool:
    lower, upper, cond = rule["lowerLimit"], rule["upperLimit"], rule["condition"]
    if cond == "above_upper":
        return upper is not None and value > upper
    if cond == "below_lower":
        return lower is not None and value < lower
    if cond == "out_of_range":
        return (lower is not None and value < lower) or (upper is not None and value > upper)
    if cond == "in_range":
        return lower is not None and upper is not None and lower <= value <= upper
    return False


def _fmt(v: Optional[float]) -> str:
    return "-" if v is None else f"{v:g}"


def _build_message(rule: Dict[str, Any], reading: Reading) -> str:
    unit = reading.unit or ""
    cond = rule["condition"]
    if cond == "above_upper":
        detail = f"高于上限 {_fmt(rule['upperLimit'])}{unit}"
    elif cond == "below_lower":
        detail = f"低于下限 {_fmt(rule['lowerLimit'])}{unit}"
    elif cond == "out_of_range":
        detail = f"超出正常范围 [{_fmt(rule['lowerLimit'])}, {_fmt(rule['upperLimit'])}]{unit}"
    else:
        detail = f"处于告警范围 [{_fmt(rule['lowerLimit'])}, {_fmt(rule['upperLimit'])}]{unit}"
    return f"{reading.device_name} {reading.register_name}越限: {reading.value:g}{unit}（{detail}）"


def evaluate_readings(readings: List[Reading]) -> List[Dict[str, Any]]:
    """按当前生效规则评估读数，命中则生成告警记录（等级为规则当前快照）。"""
    rules = [r for r in list_rules() if r["enabled"]]
    if not rules or not readings:
        return []

    created: List[Dict[str, Any]] = []
    now = now_ms()
    with _lock:
        conn = get_conn()
        try:
            for rd in readings:
                for rule in rules:
                    if rule["deviceId"] != "*" and rule["deviceId"] != rd.device_id:
                        continue
                    if rule["registerName"] != rd.register_name:
                        continue
                    if not _condition_hit(rule, rd.value):
                        continue
                    recent = conn.execute(
                        "SELECT 1 FROM alarm_records WHERE rule_id = ? AND device_id = ?"
                        " AND register_name = ? AND created_at > ? LIMIT 1",
                        (rule["id"], rd.device_id, rd.register_name, now - ALARM_SUPPRESS_MS),
                    ).fetchone()
                    if recent:  # 抑制窗口内不重复告警
                        continue
                    alarm_id = _new_id("al")
                    message = _build_message(rule, rd)
                    conn.execute(
                        "INSERT INTO alarm_records"
                        " (id, rule_id, device_id, device_name, register_address, register_name,"
                        "  value, unit, level, message, acknowledged, created_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                        (
                            alarm_id, rule["id"], rd.device_id, rd.device_name,
                            rd.register_address, rd.register_name, rd.value, rd.unit,
                            rule["level"], message, now,
                        ),
                    )
                    created.append({
                        "id": alarm_id, "ruleId": rule["id"], "deviceId": rd.device_id,
                        "deviceName": rd.device_name, "registerAddress": rd.register_address,
                        "registerName": rd.register_name, "value": rd.value, "unit": rd.unit,
                        "level": rule["level"], "message": message,
                        "acknowledged": False, "createdAt": now,
                    })
            conn.commit()
        finally:
            conn.close()
    return created


def list_alarms(limit: int = 100) -> List[Dict[str, Any]]:
    with _lock:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM alarm_records ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
    return [_alarm_row_to_dict(r) for r in rows]


def acknowledge_alarm(alarm_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = get_conn()
        try:
            conn.execute("UPDATE alarm_records SET acknowledged = 1 WHERE id = ?", (alarm_id,))
            conn.commit()
            row = conn.execute("SELECT * FROM alarm_records WHERE id = ?", (alarm_id,)).fetchone()
        finally:
            conn.close()
    return _alarm_row_to_dict(row) if row else None
