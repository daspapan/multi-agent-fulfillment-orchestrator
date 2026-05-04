from src.agents.base import SubAgent
from src.orchestrator.schemas import TaskAssignment


class SummarizerAgent(SubAgent):
    """Summarizes a support ticket or shipment doc.

    Instruction to the model right now is just "summarize the attached
    document thoroughly" -- works fine in manual testing.
    """

    name = "summarizer"

    def run(self, task: TaskAssignment) -> dict:
        text = task.payload.get("document_text", "")
        # placeholder for the actual Claude call -- swapped in call_model()
        summary = call_model(
            prompt=f"Summarize the attached document thoroughly:\n\n{text}"
        )
        return {"summary": summary}


def call_model(prompt: str) -> str:
    # Stubbed for local dev/tests. Real implementation calls the Anthropic
    # API / Claude Agent SDK. See src/orchestrator/model_client.py.
    return f"[summary of {len(prompt)} chars]"
