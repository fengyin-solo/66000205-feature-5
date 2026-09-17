"""Modbus service with mock data (replace with pymodbus for production)."""
import random
from typing import Any, Dict, List

from app.services import alarm_engine

MOCK_DEVICES = [
    {"id": "dev1", "name": "温湿度传感器-A区", "ip": "192.168.1.101", "port": 502, "slave_id": 1, "online": True},
    {"id": "dev2", "name": "压力变送器-B区", "ip": "192.168.1.102", "port": 502, "slave_id": 2, "online": True},
    {"id": "dev3", "name": "电机控制器-C区", "ip": "192.168.1.103", "port": 502, "slave_id": 3, "online": False},
    {"id": "dev4", "name": "流量计-D区", "ip": "192.168.1.104", "port": 502, "slave_id": 4, "online": True},
]

# point -> (register address, unit); values drift around BASE for deterministic-ish behaviour
MOCK_POINTS = {
    "dev1": [(0, "温度", "°C", 26.0), (1, "湿度", "%RH", 60.0), (2, "露点", "°C", 17.0)],
    "dev2": [(0, "管道压力", "MPa", 3.4), (1, "差压", "kPa", 0.12)],
    "dev3": [(0, "转速", "RPM", 1480.0), (1, "电流", "A", 12.5)],
    "dev4": [(0, "瞬时流量", "L/min", 155.0), (1, "累计流量", "L", 98234.0)],
}


def get_device_status() -> List[Dict[str, Any]]:
    return MOCK_DEVICES


def read_registers(device_id: str, address: int, count: int) -> Dict[str, Any]:
    """Read registers via pymodbus (mock implementation)."""
    # In production: from pymodbus.client import ModbusTcpClient
    # client = ModbusTcpClient(host, port=port)
    # result = client.read_holding_registers(address, count, slave=slave_id)
    values = [round(random.uniform(0, 100), 2) for _ in range(count)]
    return {"device_id": device_id, "address": address, "values": values}


def poll_once() -> Dict[str, Any]:
    """One acquisition cycle: read every online device's points and evaluate
    every reading against the *current* rule set. Raised alarms are persisted
    with a frozen level snapshot."""
    new_alarms: List[Dict[str, Any]] = []
    readings: List[Dict[str, Any]] = []
    for dev in MOCK_DEVICES:
        if not dev["online"]:
            continue
        for address, point, unit, base in MOCK_POINTS.get(dev["id"], []):
            value = round(base + random.uniform(-1, 1) * max(1.0, base * 0.03), 2)
            readings.append({
                "deviceId": dev["id"], "deviceName": dev["name"],
                "address": address, "point": point, "unit": unit, "value": value,
            })
            rule = alarm_engine.evaluate(point, value, device_id=dev["id"])
            if rule:
                new_alarms.append(
                    alarm_engine.insert_alarm(point, value, dev["id"], dev["name"], unit, rule)
                )
    return {"readings": readings, "alarms": new_alarms}
