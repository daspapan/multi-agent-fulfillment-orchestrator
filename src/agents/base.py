"""
Base subagent.

Context isolation is enforced here, not just by convention: a subagent
only ever sees the `payload` dict handed to it in the TaskAssignment. No
implicit access to orchestrator state, conversation history, or another
agent's output. If a subagent needs something, it has to be in the payload.

(We hit a bug where a validator was silently reading values off the
orchestrator's system prompt in one deployment but not another -- worked
in test, ~20% failure rate in prod for specific customers. This is the fix.)
"""

from src.orchestrator.schemas import TaskAssignment


class SubAgent:
    name = "base"

    def run(self, task: TaskAssignment) -> dict:
        # `task.payload` is the ONLY input. Do not reach for globals,
        # module-level state, or anything set by a previous agent that
        # wasn't explicitly copied into payload.
        raise NotImplementedError

    def spawn_context(self, task: TaskAssignment) -> dict:
        """Returns exactly what this agent is allowed to see. Nothing else
        gets threaded through implicitly."""
        return dict(task.payload)
