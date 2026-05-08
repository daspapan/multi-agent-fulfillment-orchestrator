"""
Message shapes passed between the orchestrator and subagents.

Every subagent output is now a checkable schema, not prose. The aggregation
step downstream needs to parse this mechanically -- "summarize thoroughly"
producing a bullet list one run and a single sentence the next isn't
something a JSON aggregator can work with.
"""

from pydantic import BaseModel, Field
from typing import Any, Literal, Optional


class TaskAssignment(BaseModel):
    task_id: str
    agent: str
    payload: dict[str, Any]


class SummaryOutput(BaseModel):
    bullets: list[str] = Field(min_length=1, max_length=5)
    confidence: float = Field(ge=0.0, le=1.0)


class ValidationOutput(BaseModel):
    valid: bool
    missing_fields: list[str] = Field(default_factory=list)


class EnrichmentOutput(BaseModel):
    order_id: str
    customer_tier: Literal["standard", "priority", "enterprise"]
    risk_score: float = Field(ge=0.0, le=1.0)


class HandoffMessage(BaseModel):
    task_id: str
    from_agent: str
    to_agent: str
    result: dict[str, Any]
    status: str  # "ok" or "error"
