"""Alarm rule management API: CRUD, audit trail, idempotent saves."""
import json
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from app import db
from app.models.alarm_schemas import CONDITION_LABELS, RuleUpsert
from app.services import alarm_service
from app.services.modbus_service import MOCK_POINTS, get_device_status

router = APIRouter()


def _known_device_ids():
    return [d["id"] for d in get_device_status()]


@router.get("/alarm/meta")
def rule_meta():
    """Static options used by the admin form."""
    points = sorted({p for pts in MOCK_POINTS.values() for _, p, _, _ in pts})
    return {
        "conditions": [{"value": k, "label": v} for k, v in CONDITION_LABELS.items()],
        "levels": ["info", "warning", "critical"],
        "points": points,
        "devices": [{"id": d["id"], "name": d["name"]} for d in get_device_status()],
    }


@router.get("/alarm/rules")
def get_rules():
    return alarm_service.list_rules()


@router.get("/alarm/rules/{rule_id}")
def get_rule(rule_id: int):
    rule = alarm_service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


def _existing_replay(idem_key: Optional[str]) -> Optional[JSONResponse]:
    """Return a finished response stored under this key, else None."""
    if not idem_key:
        return None
    with db.get_conn() as conn:
        row = conn.execute("SELECT status, status_code, response FROM idempotency_key WHERE key=?",
                           (idem_key,)).fetchone()
    if not row:
        return None
    if row["status"] == "in-flight":
        raise HTTPException(status_code=409, detail="相同的保存请求正在处理中，请勿重复提交")
    return JSONResponse(content=json.loads(row["response"]), status_code=row["status_code"])


def _claim_key(idem_key: Optional[str]) -> Optional[JSONResponse]:
    """Atomically claim an idempotency key. Returns a replay response if another
    request already owns / completed the key."""
    if not idem_key:
        return None
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO idempotency_key (key, status, status_code, response, created_at) "
            "VALUES (?, 'in-flight', NULL, '{}', ?) ON CONFLICT(key) DO NOTHING",
            (idem_key, db.now_iso()),
        )
        claimed = conn.execute("SELECT changes() AS n").fetchone()["n"] == 1
        if claimed:
            return None
        row = conn.execute("SELECT status, status_code, response FROM idempotency_key WHERE key=?",
                           (idem_key,)).fetchone()
    if row["status"] == "in-flight":
        raise HTTPException(status_code=409, detail="相同的保存请求正在处理中，请勿重复提交")
    return JSONResponse(content=json.loads(row["response"]), status_code=row["status_code"])


def _release_key(idem_key: Optional[str]) -> None:
    """Failed attempts release the key so the caller may retry with it."""
    if not idem_key:
        return
    with db.get_conn() as conn:
        conn.execute("DELETE FROM idempotency_key WHERE key=? AND status='in-flight'", (idem_key,))


def _store_response(idem_key: Optional[str], status_code: int, body: dict) -> None:
    if not idem_key:
        return
    with db.transaction() as conn:
        conn.execute(
            "UPDATE idempotency_key SET status='done', status_code=?, response=? WHERE key=?",
            (status_code, json.dumps(body, ensure_ascii=False), idem_key),
        )


def _guard_validation(exc: Exception, idem_key: Optional[str]) -> HTTPException:
    if not isinstance(exc, alarm_service.ValidationError):
        raise exc
    _release_key(idem_key)
    detail: Any = {"message": "校验未通过，未保存任何内容", "errors": exc.errors}
    status = 404 if "id" in exc.errors else 400
    return HTTPException(status_code=status, detail=detail)


def _do_save(body: RuleUpsert, operator: str, idem_key: Optional[str],
             rule_id: Optional[int], success_status: int):
    replay = _existing_replay(idem_key)
    if replay is not None:
        return replay
    replay = _claim_key(idem_key)
    if replay is not None:
        return replay
    try:
        rule, action = alarm_service.save_rule(body.model_dump(), operator, rule_id, _known_device_ids())
    except alarm_service.ValidationError as e:
        raise _guard_validation(e, idem_key)
    except Exception:
        # never strand the key in "in-flight"
        _release_key(idem_key)
        raise
    resp_body = {"rule": rule, "action": action}
    _store_response(idem_key, success_status, resp_body)
    return JSONResponse(status_code=success_status, content=resp_body)


@router.post("/alarm/rules", status_code=201)
def create_rule(body: RuleUpsert,
                idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
                x_operator: str = Header(default="admin", alias="X-Operator")):
    return _do_save(body, x_operator, idempotency_key, None, 201)


@router.put("/alarm/rules/{rule_id}")
def update_rule(rule_id: int, body: RuleUpsert,
                idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
                x_operator: str = Header(default="admin", alias="X-Operator")):
    # Updates are naturally idempotent per rule id; the key also suppresses
    # duplicate audit rows on a retried request.
    return _do_save(body, x_operator, idempotency_key, rule_id, 200)


@router.post("/alarm/rules/{rule_id}/toggle")
def toggle_rule(rule_id: int, enabled: bool = Query(...),
                x_operator: str = Header(default="admin", alias="X-Operator")):
    rule = alarm_service.set_enabled(rule_id, enabled, x_operator)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.get("/alarm/audit")
def get_audit(rule_id: Optional[int] = None, limit: int = Query(200, le=1000)):
    return alarm_service.list_audit(rule_id, limit)
