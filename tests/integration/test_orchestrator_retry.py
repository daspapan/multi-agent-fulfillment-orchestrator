"""Integration test: orchestrator, not the agent, owns retry decisions.
An agent that fails the completion check should be retried by the
orchestrator up to MAX_RETRIES, and the decision log should show it."""

import pytest

from src.agents.base import SubAgent
from src.orchestrator.orchestrator import HandoffFailed, Orchestrator
from src.orchestrator.schemas import TaskAssignment


class FlakyAgent(SubAgent):
    name = "flaky"

    def __init__(self):
        self.calls = 0

    def run(self, task: TaskAssignment) -> dict:
        self.calls += 1
        if self.calls < 2:
            return {}  # missing required fields -> fails completion check
        return {"order_id": "X", "customer_tier": "standard", "risk_score": 0.1}


def test_orchestrator_retries_before_giving_up():
    orch = Orchestrator()
    flaky = FlakyAgent()
    orch.agents["enrichment"] = flaky
    orch.dispatch("t1", "enrichment", {})
    assert flaky.calls == 2
    log = orch.state.decision_log("t1")
    assert any(entry["status"] == "retrying" for entry in log)
    assert log[-1]["status"] == "ok"


class AlwaysFailingAgent(SubAgent):
    name = "always_failing"

    def run(self, task: TaskAssignment) -> dict:
        return {}


def test_orchestrator_gives_up_after_max_retries():
    orch = Orchestrator()
    orch.agents["enrichment"] = AlwaysFailingAgent()
    with pytest.raises(HandoffFailed):
        orch.dispatch("t2", "enrichment", {})
    assert orch.state.get("t2").status == "failed"
