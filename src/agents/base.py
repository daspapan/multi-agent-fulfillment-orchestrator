"""Base subagent. Each subagent gets a task and returns a result dict."""

from src.orchestrator.schemas import TaskAssignment


class SubAgent:
    name = "base"

    def run(self, task: TaskAssignment) -> dict:
        raise NotImplementedError
