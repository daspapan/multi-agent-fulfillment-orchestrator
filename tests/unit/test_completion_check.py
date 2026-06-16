from src.orchestrator.completion_check import check_completion


def test_passes_when_all_required_fields_present():
    result = check_completion({"a": 1, "b": 2}, required_fields=["a", "b"])
    assert result.ok


def test_fails_when_a_required_field_is_silently_missing():
    result = check_completion({"a": 1}, required_fields=["a", "b"])
    assert not result.ok
    assert "b" in result.reason


def test_fails_when_required_field_is_none():
    result = check_completion({"a": 1, "b": None}, required_fields=["a", "b"])
    assert not result.ok
