from src.agents.base import SubAgent
from src.orchestrator.schemas import TaskAssignment


class ValidatorAgent(SubAgent):
    """Checks a shipment document against required fields."""

    name = "validator"

    def run(self, task: TaskAssignment) -> dict:
        doc = task.payload.get("document", {})
        required = ["order_id", "customer_id", "items"]
        missing = [f for f in required if f not in doc]
        return {"valid": len(missing) == 0, "missing_fields": missing}
