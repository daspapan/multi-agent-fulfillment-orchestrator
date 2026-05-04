from src.agents.base import SubAgent
from src.orchestrator.schemas import TaskAssignment


class EnrichmentAgent(SubAgent):
    """Adds customer tier / risk score to an order event."""

    name = "enrichment"

    def run(self, task: TaskAssignment) -> dict:
        order = task.payload.get("order", {})
        # TODO: pull real customer tier from CRM lookup, this is a stand-in
        return {"customer_tier": "standard", "risk_score": 0.1, "order_id": order.get("order_id")}
