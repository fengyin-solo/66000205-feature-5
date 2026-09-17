"""Alarm rule domain service: validation, idempotent upsert, audit, evaluation."""
import json
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.models.alarm_schemas import CONDITIONS, LEVELS


class ValidationError(Exception):
    """400 with per-field explanations the UI can show next to the offending item."""

    def __init__(self, errors: Dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


def _validate(payload: Dict[str, Any], known_devices: List[str]) -> None:
    errors: Dict[str, str] = {}

    point = (payload.get("point") or "").strip()
    if not point:
        errors["point"] = "点位名称不能为空"

    condition = payload.get("condition")
    if condition not in CONDITIONS:
        errors["condition"] = f"判定条件无效，只能是 {', '.join(CONDITIONS)}"

    level = payload.get("level")
    if level not in LEVELS:
        errors["level"] = f"提醒等级无效，只能是 {', '.join(LEVELS)}"

    upper = payload.get("upperLimit")
    lower = payload.get("lowerLimit")
    for name, val in (("upperLimit", upper), ("lowerLimit", lower)):
        if val is not None and not isinstance(val, (int, float)):
            errors[name] = "阈值必须是数字"

    # Range/condition consistency
    if condition in CONDITIONS and not errors.get("condition") and "upperLimit" not in errors and "lowerLimit" not in errors:
        if condition == "gt" and upper is None:
            errors["upperLimit"] = "判定条件为“高于上限”时必须填写上限"
        if condition == "lt" and lower is None:
            errors["lowerLimit"] = "判定条件为“低于下限”时必须填写下限"
        if condition in ("between", "outside"):
            if upper is None or lower is None:
                if upper is None:
                    errors["upperLimit"] = "区间判定必须同时填写上限和下限"
                if lower is None:
                    errors["lowerLimit"] = "区间判定必须同时填写上限和下限"
            elif lower >= upper:
                errors["lowerLimit"] = f"下限({lower}) 必须小于上限({upper})，当前范围不成立"

    scope = payload.get("scope") or []
    if not isinstance(scope, list):
        errors["scope"] = "生效范围必须是设备列表"
    elif known_devices:
        unknown = sorted(set(scope) - set(known_devices))
        if unknown:
            errors["scope"] = f"生效范围包含不存在的设备: {', '.join(unknown)}"

    if errors:
        raise ValidationError(errors)


def list_rules(include_disabled: bool = True) -> List[Dict[str, Any]]:
    with db.get_conn() as conn:
        sql = "SELECT * FROM alarm_rule"
        if not include_disabled:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY point, level"
        rows = conn.execute(sql).fetchall()
    return [db.row_to_rule(r) for r in rows]


def get_rule(rule_id: int) -> Optional[Dict[str, Any]]:
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM alarm_rule WHERE id = ?", (rule_id,)).fetchone()
    return db.row_to_rule(row) if row else None


def _scope_key(scope: List[str]) -> str:
    return json.dumps(sorted(scope), ensure_ascii=False)


def save_rule(payload: Dict[str, Any], operator: str, rule_id: Optional[int], known_devices: List[str]) -> Tuple[Dict[str, Any], str]:
    """Insert or update a rule atomically. Returns (rule, action).

    Raises ValidationError (400) on bad input or a duplicate (point+level+scope) rule.
    The whole operation — duplicate check + write + audit row — happens in one
    transaction, so a retried request (same Idempotency-Key) cannot create a
    second rule or a second audit entry.
    """
    _validate(payload, known_devices)

    point = payload["point"].strip()
    condition = payload["condition"]
    upper = payload.get("upperLimit")
    lower = payload.get("lowerLimit")
    level = payload["level"]
    scope = payload.get("scope") or []
    enabled = 1 if payload.get("enabled", True) else 0
    ts = db.now_iso()

    with db.transaction() as conn:
        action: str
        if rule_id is None:
            # Duplicate guard: same point + level + effective scope
            dup = conn.execute(
                "SELECT id FROM alarm_rule WHERE point = ? AND level = ? AND scope = ?",
                (point, level, _scope_key(scope)),
            ).fetchone()
            if dup:
                raise ValidationError({"point": f"该点位的 {level} 等级、相同生效范围的规则已存在(规则 #{dup['id']})，请勿重复添加"})

            cur = conn.execute(
                """INSERT INTO alarm_rule
                   (point, condition, upper_limit, lower_limit, level, scope, enabled, version,
                    created_by, updated_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
                (point, condition, upper, lower, level, _scope_key(scope), enabled,
                 operator, operator, ts, ts),
            )
            rule_id = cur.lastrowid
            action = "create"
            before = None
        else:
            old = conn.execute("SELECT * FROM alarm_rule WHERE id = ?", (rule_id,)).fetchone()
            if not old:
                raise ValidationError({"id": f"规则 #{rule_id} 不存在"})

            dup = conn.execute(
                "SELECT id FROM alarm_rule WHERE point = ? AND level = ? AND scope = ? AND id != ?",
                (point, level, _scope_key(scope), rule_id),
            ).fetchone()
            if dup:
                raise ValidationError({"point": f"修改后与规则 #{dup['id']} 完全重复(点位/等级/生效范围相同)"})

            conn.execute(
                """UPDATE alarm_rule SET point=?, condition=?, upper_limit=?, lower_limit=?,
                       level=?, scope=?, enabled=?, version=version+1, updated_by=?, updated_at=?
                   WHERE id=?""",
                (point, condition, upper, lower, level, _scope_key(scope), enabled, operator, ts, rule_id),
            )
            action = "update"
            before = db.row_to_rule(old)

        row = conn.execute("SELECT * FROM alarm_rule WHERE id = ?", (rule_id,)).fetchone()
        after = db.row_to_rule(row)

        changes = _diff(before, after)
        if action == "update" and not changes:
            raise ValidationError({"point": "提交内容与现有规则完全一致，没有需要保存的变更"})

        conn.execute(
            """INSERT INTO audit_log (rule_id, point, action, operator, changed_at, changes, before_json, after_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rule_id,
                point,
                "create" if before is None else "update",
                operator,
                ts,
                json.dumps(changes, ensure_ascii=False),
                json.dumps(before, ensure_ascii=False) if before else None,
                json.dumps(after, ensure_ascii=False),
            ),
        )

    return after, ("create" if before is None else "update")


def _diff(before: Optional[Dict[str, Any]], after: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("point", "condition", "upperLimit", "lowerLimit", "level", "scope", "enabled")
    if before is None:
        return {k: {"old": None, "new": after.get(k)} for k in keys}
    return {
        k: {"old": before.get(k), "new": after.get(k)}
        for k in keys
        if before.get(k) != after.get(k)
    }


def set_enabled(rule_id: int, enabled: bool, operator: str) -> Optional[Dict[str, Any]]:
    ts = db.now_iso()
    with db.transaction() as conn:
        old = conn.execute("SELECT * FROM alarm_rule WHERE id = ?", (rule_id,)).fetchone()
        if not old:
            return None
        if bool(old["enabled"]) == enabled:
            return db.row_to_rule(old)
        conn.execute("UPDATE alarm_rule SET enabled=?, updated_by=?, updated_at=?, version=version+1 WHERE id=?",
                     (1 if enabled else 0, operator, ts, rule_id))
        row = conn.execute("SELECT * FROM alarm_rule WHERE id=?", (rule_id,)).fetchone()
        after = db.row_to_rule(row)
        before = db.row_to_rule(old)
        conn.execute(
            """INSERT INTO audit_log (rule_id, point, action, operator, changed_at, changes, before_json, after_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, after["point"], "enable" if enabled else "disable", operator, ts,
             json.dumps({"enabled": {"old": before["enabled"], "new": enabled}}, ensure_ascii=False),
             json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)),
        )
    return after


def list_audit(rule_id: Optional[int] = None, limit: int = 200) -> List[Dict[str, Any]]:
    with db.get_conn() as conn:
        if rule_id is not None:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE rule_id=? ORDER BY id DESC LIMIT ?", (rule_id, limit)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [db.row_to_audit(r) for r in rows]
