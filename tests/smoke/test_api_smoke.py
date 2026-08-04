"""Smoke test for the HTTP surface that actually runs in the Fargate
container -- this is the shape a post-deploy check would hit, not just
calling Orchestrator directly in-process."""

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_process_order_then_duplicate_rejected():
    first = client.post("/orders/process", json={"order_id": "SMOKE-API-1", "customer_id": "C1"})
    assert first.status_code == 200
    assert first.json()["status"] == "ok"

    second = client.post("/orders/process", json={"order_id": "SMOKE-API-1", "customer_id": "C1"})
    assert second.status_code == 200
    assert second.json()["status"] == "rejected"
