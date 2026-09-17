from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.models.schemas import EvaluateRequest, ThresholdRuleIn
from app.services import threshold_service as svc

router = APIRouter()


def _validation_response(errors):
    # 422 + 逐字段错误，前端据此在对应表单项上提示
    return JSONResponse(status_code=422, content={"detail": "规则校验未通过", "errors": errors})


@router.get("/threshold-rules")
def get_rules():
    return {"rules": svc.list_rules()}


@router.post("/threshold-rules", status_code=201)
def create_rule(body: ThresholdRuleIn):
    try:
        rule, created = svc.create_rule(body)
    except svc.RuleValidationError as e:
        return _validation_response(e.errors)
    except svc.DuplicateRuleError as e:
        return JSONResponse(status_code=409, content={"detail": str(e)})
    # 幂等命中（重试）也返回 200/201 与已存在的记录，客户端无感知
    return rule


@router.put("/threshold-rules/{rule_id}")
def update_rule(rule_id: str, body: ThresholdRuleIn):
    try:
        return svc.update_rule(rule_id, body)
    except svc.RuleValidationError as e:
        return _validation_response(e.errors)
    except svc.DuplicateRuleError as e:
        return JSONResponse(status_code=409, content={"detail": str(e)})
    except svc.RuleNotFoundError as e:
        return JSONResponse(status_code=404, content={"detail": str(e)})


@router.delete("/threshold-rules/{rule_id}")
def delete_rule(rule_id: str, operator: str = Query(default="admin")):
    try:
        svc.delete_rule(rule_id, operator)
    except svc.RuleNotFoundError as e:
        return JSONResponse(status_code=404, content={"detail": str(e)})
    return {"status": "deleted", "id": rule_id}


@router.get("/threshold-rule-audits")
def get_audits(limit: int = Query(default=200, le=1000)):
    return {"audits": svc.list_audits(limit)}


@router.post("/alarm-engine/evaluate")
def evaluate(body: EvaluateRequest):
    """提交一批读数，按当前生效规则判定，返回本次新产生的告警。"""
    return {"alarms": svc.evaluate_readings(body.readings)}


@router.get("/alarms")
def get_alarms(limit: int = Query(default=100, le=1000)):
    return {"alarms": svc.list_alarms(limit)}


@router.post("/alarms/{alarm_id}/ack")
def ack_alarm(alarm_id: str):
    alarm = svc.acknowledge_alarm(alarm_id)
    if alarm is None:
        return JSONResponse(status_code=404, content={"detail": f"告警 {alarm_id} 不存在"})
    return alarm
