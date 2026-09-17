from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ModbusRegister(BaseModel):
    address: int
    name: str
    type: str
    value: float
    unit: str


class Device(BaseModel):
    id: str
    name: str
    ip: str
    port: int
    slave_id: int
    online: bool
    registers: List[ModbusRegister] = []


class AlarmLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ThresholdCondition(str, Enum):
    ABOVE_UPPER = "above_upper"    # 高于上限
    BELOW_LOWER = "below_lower"    # 低于下限
    OUT_OF_RANGE = "out_of_range"  # 超出 [下限, 上限]
    IN_RANGE = "in_range"          # 处于 [下限, 上限] 之间


class ThresholdRuleIn(BaseModel):
    """阈值规则的新增/修改入参。数值范围合法性由 threshold_service.validate_rule 校验。"""

    model_config = ConfigDict(populate_by_name=True)

    device_id: str = Field(alias="deviceId")            # '*' 表示全部设备
    register_address: int = Field(alias="registerAddress", default=0)
    register_name: str = Field(alias="registerName")
    lower_limit: Optional[float] = Field(alias="lowerLimit", default=None)
    upper_limit: Optional[float] = Field(alias="upperLimit", default=None)
    condition: ThresholdCondition
    level: AlarmLevel
    enabled: bool = True
    operator: str = "admin"
    # 客户端在一次保存会话内生成的幂等键，失败重试时保持不变，服务端据此去重
    client_request_id: Optional[str] = Field(alias="clientRequestId", default=None)


class Reading(BaseModel):
    """一次采集到的点位读数，提交给判定引擎评估。"""

    model_config = ConfigDict(populate_by_name=True)

    device_id: str = Field(alias="deviceId")
    device_name: str = Field(alias="deviceName", default="")
    register_address: int = Field(alias="registerAddress", default=0)
    register_name: str = Field(alias="registerName")
    value: float
    unit: str = ""


class EvaluateRequest(BaseModel):
    readings: List[Reading]
