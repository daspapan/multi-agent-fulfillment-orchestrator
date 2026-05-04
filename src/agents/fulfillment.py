from src.agents.base import SubAgent
from src.orchestrator.schemas import TaskAssignment


class FulfillmentAgent(SubAgent):
    """Executes the actual fulfillment handoff to the warehouse system."""

    name = "fulfillment"

    def run(self, task: TaskAssignment) -> dict:
        order = task.payload.get("order", {})
        # NOTE: whatever flags arrive in `order` get forwarded as-is.
        # fulfillment system trusts this payload completely.
        return {"submitted": True, "order_id": order.get("order_id"), "forwarded": order}
