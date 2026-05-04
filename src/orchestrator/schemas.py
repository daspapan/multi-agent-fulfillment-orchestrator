"""
Message shapes passed between the orchestrator and subagents.

First pass. Just enough structure to get summarizer -> validator -> fulfillment
talking to each other. Will probably need versioning once we have more than
one team touching this.
"""

from pydantic import BaseModel
from typing import Any, Optional


class TaskAssignment(BaseModel):
    task_id: str
    agent: str
    payload: dict[str, Any]


class HandoffMessage(BaseModel):
    task_id: str
    from_agent: str
    to_agent: str
    result: dict[str, Any]
    status: str  # "ok" or "error"
