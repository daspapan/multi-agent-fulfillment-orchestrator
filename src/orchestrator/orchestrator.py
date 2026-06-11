"""
Hub-and-spoke orchestrator.

Owns every retry/substitute/escalate decision -- subagents report failures,
they don't decide what happens next. Early on, subagents were built to
"handle their own failures locally," and when one silently never returned,
there was no record of any decision ever being made about what to do next.
The orchestrator is now the only component with visibility across the
whole task graph, and the only place that makes that call.
"""

import logging
from src.agents.summarizer import SummarizerAgent
from src.agents.validator import ValidatorAgent
from src.agents.enrichment import EnrichmentAgent
from src.agents.fulfillment import FulfillmentAgent
from src.orchestrator.schemas import TaskAssignment
from src.orchestrator.state_store import StateStore
from src.orchestrator.completion_check import check_completion

logger = logging.getLogger("orchestrator")

MAX_RETRIES = 2

REQUIRED_FIELDS = {
    "enrichment": ["order_id", "customer_tier", "risk_score"],
    "fulfillment": ["submitted", "order_id", "skip_duplicate_check", "duplicate_check"],
}


class HandoffFailed(Exception):
    def __init__(self, agent: str, reason: str):
        self.agent = agent
        self.reason = reason
        super().__init__(f"{agent} handoff failed: {reason}")


class Orchestrator:
    def __init__(self, state_store: StateStore | None = None):
        self.agents = {
            "summarizer": SummarizerAgent(),
            "validator": ValidatorAgent(),
            "enrichment": EnrichmentAgent(),
            "fulfillment": FulfillmentAgent(),
        }
        self.state = state_store or StateStore()

    def dispatch(self, task_id: str, agent_name: str, payload: dict) -> dict:
        """Owns the retry decision. A subagent that raises or returns an
        incomplete result gets retried up to MAX_RETRIES times by the
        orchestrator -- the agent itself never decides to retry."""
        agent = self.agents[agent_name]
        task = TaskAssignment(task_id=task_id, agent=agent_name, payload=payload)
        self.state.record(task_id, agent_name, "pending")

        last_error = None
        for attempt in range(1, MAX_RETRIES + 2):
            self.state.record_attempt(task_id)
            try:
                result = agent.run(task)
            except Exception as exc:  # noqa: BLE001 - orchestrator decides fate of any subagent exception
                last_error = str(exc)
                self.state.record(task_id, agent_name, "retrying", {"attempt": attempt, "error": last_error})
                logger.warning("agent %s raised on attempt %s: %s", agent_name, attempt, last_error)
                continue

            required = REQUIRED_FIELDS.get(agent_name, [])
            check = check_completion(result, required)
            if not check.ok:
                last_error = check.reason
                self.state.record(task_id, agent_name, "retrying", {"attempt": attempt, "error": last_error})
                logger.warning("agent %s failed completion check on attempt %s: %s", agent_name, attempt, last_error)
                continue

            self.state.record(task_id, agent_name, "ok", {"attempt": attempt, "result": result})
            return result

        self.state.record(task_id, agent_name, "failed", {"error": last_error})
        raise HandoffFailed(agent_name, last_error or "unknown")

    def process_order(self, order: dict) -> dict:
        task_id = f"order-{order.get('order_id')}"
        try:
            enriched = self.dispatch(f"{task_id}-enrich", "enrichment", {"order": order})
            order = {**order, **enriched}
            result = self.dispatch(f"{task_id}-fulfill", "fulfillment", {"order": order})
            return {"status": "ok", "result": result, "decision_log": self.state.decision_log(f"{task_id}-fulfill")}
        except HandoffFailed as exc:
            logger.error("order %s failed at %s: %s", order.get("order_id"), exc.agent, exc.reason)
            return {"status": "failed", "failed_agent": exc.agent, "reason": exc.reason}
