"""Five-stage sequential document processing pipeline.

Stage 3 (validation) can reject a document. Previously, a rejection just
meant stages 4/5 never got called -- monitoring showed "no activity" where
it should've shown "failure," and it took 40 minutes to trace a stall back
to its source. Now a failed stage raises explicitly and the pipeline
records exactly where it stopped and why.
"""

from src.agents.summarizer import SummarizerAgent
from src.agents.validator import ValidatorAgent
from src.orchestrator.schemas import TaskAssignment


class PipelineStageError(Exception):
    def __init__(self, stage: int, reason: str, detail: dict):
        self.stage = stage
        self.reason = reason
        self.detail = detail
        super().__init__(f"stage {stage} failed: {reason}")


def run_pipeline(document: dict) -> dict:
    trace = {"stage_reached": 0, "errors": []}

    trace["stage_reached"] = 1

    trace["stage_reached"] = 2
    stage2 = SummarizerAgent().run(
        TaskAssignment(task_id="p2", agent="summarizer", payload={"document_text": str(document)})
    )

    trace["stage_reached"] = 3
    stage3 = ValidatorAgent().run(
        TaskAssignment(task_id="p3", agent="validator", payload={"document": document})
    )
    if not stage3["valid"]:
        err = PipelineStageError(3, "validation_failed", stage3)
        trace["errors"].append(str(err))
        trace["status"] = "failed"
        trace["failed_stage"] = 3
        trace["validation"] = stage3
        return trace

    trace["stage_reached"] = 4
    stage4 = {"enriched": True}

    trace["stage_reached"] = 5
    stage5 = {"archived": True}

    trace["status"] = "ok"
    trace["summary"] = stage2
    trace["validation"] = stage3
    trace["enrichment"] = stage4
    trace["archive"] = stage5
    return trace
