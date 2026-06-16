"""Loop must always terminate: either the quality threshold is met, or
max_iterations is hit. There is no code path that runs forever."""

import pytest
from src.orchestrator.evaluator_optimizer import EvaluatorOptimizerLoop


def test_stops_at_threshold():
    loop = EvaluatorOptimizerLoop(max_iterations=10, quality_threshold=0.8)
    scores = iter([0.3, 0.6, 0.85])
    result = loop.run(draft_fn=lambda s: s + "x", evaluate_fn=lambda s: next(scores), seed="")
    assert result.stopped_reason == "threshold_met"
    assert result.iterations == 3


def test_stops_at_max_iterations_if_threshold_never_met():
    loop = EvaluatorOptimizerLoop(max_iterations=3, quality_threshold=0.99)
    result = loop.run(draft_fn=lambda s: s + "x", evaluate_fn=lambda s: 0.1, seed="")
    assert result.stopped_reason == "max_iterations"
    assert result.iterations == 3


def test_rejects_unbounded_config():
    with pytest.raises(ValueError):
        EvaluatorOptimizerLoop(max_iterations=0, quality_threshold=0.5)
    with pytest.raises(ValueError):
        EvaluatorOptimizerLoop(max_iterations=5, quality_threshold=1.5)
