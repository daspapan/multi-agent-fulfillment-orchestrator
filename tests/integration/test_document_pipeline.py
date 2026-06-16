"""Integration test: a stage-3 validation failure must surface explicitly,
not just cause stages 4/5 to silently never run."""

from src.pipeline.document_pipeline import run_pipeline


def test_pipeline_completes_when_document_is_valid():
    doc = {"order_id": "O1", "customer_id": "C1", "items": ["x"]}
    result = run_pipeline(doc)
    assert result["status"] == "ok"
    assert result["stage_reached"] == 5


def test_pipeline_reports_exact_failed_stage_on_invalid_document():
    doc = {"order_id": "O1"}  # missing customer_id, items
    result = run_pipeline(doc)
    assert result["status"] == "failed"
    assert result["failed_stage"] == 3
    assert "customer_id" in result["validation"]["missing_fields"]
