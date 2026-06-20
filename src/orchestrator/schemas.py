"""
Message shapes passed between the orchestrator and subagents.

HandoffMessage is now versioned. A new required field crashed every
still-running old-release agent the moment it received a message it
couldn't parse -- no migration path, no fallback for missing fields.
New fields ship optional with a default, get a deprecation window, and
only become mandatory once the fleet has rolled forward.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CURRENT_HANDOFF_VERSION = 2


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
    """
    schema_version 1: task_id, from_agent, to_agent, result, status
    schema_version 2: + priority (optional, defaults to "normal")

    When priority becomes mandatory in v3, receivers on v2 will still
    accept it missing for one deprecation window before that happens.
    """

    schema_version: int = CURRENT_HANDOFF_VERSION
    task_id: str
    from_agent: str
    to_agent: str
    result: dict[str, Any]
    status: str  # "ok" or "error"
    priority: str = "normal"  # added in v2, optional -- do not make required without a migration window

    @field_validator("schema_version")
    @classmethod
    def _known_version(cls, v: int) -> int:
        if v > CURRENT_HANDOFF_VERSION:
            raise ValueError(
                f"received schema_version {v}, this receiver only understands up to {CURRENT_HANDOFF_VERSION}"
            )
        return v
