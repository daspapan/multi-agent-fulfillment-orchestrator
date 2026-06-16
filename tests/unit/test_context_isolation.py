"""Regression test for the context-inheritance bug: a subagent must only
ever see what's in task.payload, nothing implicit."""

from src.agents.base import SubAgent
from src.orchestrator.schemas import TaskAssignment

SOME_GLOBAL_STATE = {"leaked": "should never appear in agent output"}


class ProbeAgent(SubAgent):
    name = "probe"

    def run(self, task: TaskAssignment) -> dict:
        ctx = self.spawn_context(task)
        return ctx


def test_spawn_context_only_contains_explicit_payload():
    task = TaskAssignment(task_id="t1", agent="probe", payload={"foo": "bar"})
    result = ProbeAgent().run(task)
    assert result == {"foo": "bar"}
    assert "leaked" not in result
