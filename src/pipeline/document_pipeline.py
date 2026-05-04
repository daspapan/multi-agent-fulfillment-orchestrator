"""Five-stage sequential document processing pipeline.

Stage 3 (validation) can reject a document. Downstream stages just don't
get called in that case -- no separate error signal, the absence of a
result *is* the signal.
"""

from src.agents.summarizer import SummarizerAgent
from src.agents.validator import ValidatorAgent
from src.orchestrator.schemas import TaskAssignment


def run_pipeline(document: dict) -> dict:
    stage1 = {"received": True, "document": document}

    stage2 = SummarizerAgent().run(
        TaskAssignment(task_id="p2", agent="summarizer", payload={"document_text": str(document)})
    )

    stage3 = ValidatorAgent().run(
        TaskAssignment(task_id="p3", agent="validator", payload={"document": document})
    )
    if not stage3["valid"]:
        return {"stage_reached": 3, "result": stage3}

    stage4 = {"enriched": True}
    stage5 = {"archived": True}

    return {
        "stage_reached": 5,
        "summary": stage2,
        "validation": stage3,
        "enrichment": stage4,
        "archive": stage5,
    }
