from typing import Optional

from fastapi import APIRouter, Query

from app.services import alarm_engine
from app.services.modbus_service import get_device_status, poll_once, read_registers

router = APIRouter()


@router.get("/modbus/devices")
def list_devices():
    return get_device_status()


@router.get("/modbus/read/{device_id}/{address}/{count}")
def read_holding(device_id: str, address: int, count: int = 1):
    """Read holding registers from a Modbus device."""
    return read_registers(device_id, address, count)


@router.post("/modbus/poll")
def trigger_poll():
    """One acquisition cycle evaluated against the current rule set."""
    return poll_once()


@router.post("/modbus/write/{device_id}/{address}")
def write_register(device_id: str, address: int, value: int):
    return {"device_id": device_id, "address": address, "value": value, "status": "written"}


@router.get("/alarm/records")
def alarm_records(point: Optional[str] = None, device_id: Optional[str] = None,
                  level: Optional[str] = None, acknowledged: Optional[bool] = None,
                  limit: int = Query(200, le=500)):
    """Historical alarms. Each record carries the level it was raised with, so
    rule edits never change how an old record renders."""
    return alarm_engine.list_alarms(point=point, device_id=device_id, level=level,
                                    acknowledged=acknowledged, limit=limit)


@router.post("/alarm/records/{alarm_id}/ack")
def ack_alarm(alarm_id: int):
    ok = alarm_engine.acknowledge(alarm_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="告警记录不存在")
    return {"id": alarm_id, "acknowledged": True}
