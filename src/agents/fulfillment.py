from src.agents.base import SubAgent
from src.orchestrator.schemas import TaskAssignment


class FulfillmentAgent(SubAgent):
    """Executes the actual fulfillment handoff to the warehouse system.

    skip_duplicate_check now round-trips explicitly in the result, not just
    the input -- a handoff that drops this flag on the way through used to
    report "success" right up until a customer got two of the same order.
    """

    name = "fulfillment"

    def __init__(self):
        self._submitted_orders: set[str] = set()  # stand-in for the DynamoDB idempotency table

    def run(self, task: TaskAssignment) -> dict:
        ctx = self.spawn_context(task)
        order = ctx.get("order", {})
        order_id = order.get("order_id")
        skip_duplicate_check = order.get("skip_duplicate_check", False)

        duplicate = order_id in self._submitted_orders
        if duplicate and not skip_duplicate_check:
            return {
                "submitted": False,
                "order_id": order_id,
                "skip_duplicate_check": skip_duplicate_check,
                "duplicate_check": False,
                "reason": "duplicate_order_id",
            }

        self._submitted_orders.add(order_id)
        return {
            "submitted": True,
            "order_id": order_id,
            "skip_duplicate_check": skip_duplicate_check,
            "duplicate_check": True,
        }
