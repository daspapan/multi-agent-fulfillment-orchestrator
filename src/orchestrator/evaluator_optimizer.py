"""
Evaluator-optimizer loop: one pass drafts a plan, another scores it
against a rubric and sends it back for revision.

Shipped once without a stated exit condition. Three days later someone
noticed a background job had been running since deploy, quietly consuming
budget on a task that should've taken minutes. max_iterations and
quality_threshold are now required constructor args, not optional config
someone can forget to set.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class LoopResult:
    output: str
    iterations: int
    final_score: float
    stopped_reason: str  # "threshold_met" or "max_iterations"


class EvaluatorOptimizerLoop:
    def __init__(self, max_iterations: int, quality_threshold: float):
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if not (0.0 <= quality_threshold <= 1.0):
            raise ValueError("quality_threshold must be between 0 and 1")
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold

    def run(
        self,
        draft_fn: Callable[[str], str],
        evaluate_fn: Callable[[str], float],
        seed: str,
    ) -> LoopResult:
        current = seed
        score = 0.0
        for i in range(1, self.max_iterations + 1):
            current = draft_fn(current)
            score = evaluate_fn(current)
            if score >= self.quality_threshold:
                return LoopResult(current, i, score, "threshold_met")
        return LoopResult(current, self.max_iterations, score, "max_iterations")
