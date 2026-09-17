"""Pydantic schemas for alarm rule management."""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

LEVELS = ("info", "warning", "critical")
CONDITIONS = ("gt", "lt", "between", "outside")

CONDITION_LABELS = {
    "gt": "高于上限",
    "lt": "低于下限",
    "between": "超出区间(不在上下限之间)",
    "outside": "落入禁区(落在上下限之间)",
}


class RuleUpsert(BaseModel):
    point: str = Field(..., min_length=1, max=64)
    condition: str
    upperLimit: Optional[float] = None
    lowerLimit: Optional[float] = None
    level: str
    scope: List[str] = Field(default_factory=list, description="生效设备 id 列表；空列表表示全部设备")
    enabled: bool = True

    @field_validator("point")
    @classmethod
    def _strip_point(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("点位名称不能为空")
        return v

    @field_validator("condition")
    @classmethod
    def _check_condition(cls, v: str) -> str:
        if v not in CONDITIONS:
            raise ValueError(f"判定条件必须是 {', '.join(CONDITIONS)} 之一")
        return v

    @field_validator("level")
    @classmethod
    def _check_level(cls, v: str) -> str:
        if v not in LEVELS:
            raise ValueError(f"提醒等级必须是 {', '.join(LEVELS)} 之一")
        return v

    @field_validator("scope")
    @classmethod
    def _dedup_scope(cls, v: List[str]) -> List[str]:
        seen: set = set()
        ordered: List[str] = []
        for s in v:
            s = s.strip()
            if s and s not in seen:
                seen.add(s)
                ordered.append(s)
        return ordered


class RuleOut(RuleUpsert):
    id: int
    version: int
    createdBy: str
    updatedBy: str
    createdAt: str
    updatedAt: str


class AuditOut(BaseModel):
    id: int
    ruleId: Optional[int] = None
    point: str
    action: str
    operator: str
    changedAt: str
    changes: dict
    before: Optional[dict] = None
    after: Optional[dict] = None
