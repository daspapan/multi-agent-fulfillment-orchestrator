"""Validates the handoff schema contract: versioning, required/optional
fields, and rejection of unknown future versions."""

import pytest
from pydantic import ValidationError

from src.orchestrator.schemas import CURRENT_HANDOFF_VERSION, HandoffMessage, SummaryOutput


def test_handoff_defaults_to_current_version():
    msg = HandoffMessage(task_id="t1", from_agent="a", to_agent="b", result={}, status="ok")
    assert msg.schema_version == CURRENT_HANDOFF_VERSION
    assert msg.priority == "normal"  # v2 field is optional, must not require callers to set it


def test_handoff_rejects_future_schema_version():
    with pytest.raises(ValidationError):
        HandoffMessage(
            schema_version=CURRENT_HANDOFF_VERSION + 1,
            task_id="t1", from_agent="a", to_agent="b", result={}, status="ok",
        )


def test_summary_output_bounds():
    with pytest.raises(ValidationError):
        SummaryOutput(bullets=[], confidence=0.5)  # min_length=1
    with pytest.raises(ValidationError):
        SummaryOutput(bullets=["a"], confidence=1.5)  # out of range
    ok = SummaryOutput(bullets=["a", "b"], confidence=0.8)
    assert ok.confidence == 0.8
