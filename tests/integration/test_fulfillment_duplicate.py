"""Integration test for the duplicate-shipment incident: a second submit
of the same order_id must be rejected, not silently double-fulfilled."""

from src.orchestrator.orchestrator import Orchestrator


def test_duplicate_order_is_rejected_not_double_submitted():
    orch = Orchestrator()
    first = orch.process_order({"order_id": "DUP-1", "customer_id": "C1"})
    second = orch.process_order({"order_id": "DUP-1", "customer_id": "C1"})
    assert first["status"] == "ok"
    assert second["status"] == "rejected"
    assert second["result"]["reason"] == "duplicate_order_id"
