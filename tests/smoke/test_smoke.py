"""Smoke test: can the whole thing boot and process one order end to end
without throwing. Meant to run against a real deployment as a post-deploy
sanity check, not just CI."""

from src.orchestrator.orchestrator import Orchestrator


def test_end_to_end_happy_path():
    orch = Orchestrator()
    result = orch.process_order({"order_id": "SMOKE-1", "customer_id": "C1"})
    assert result["status"] == "ok"
    assert result["result"]["submitted"] is True
