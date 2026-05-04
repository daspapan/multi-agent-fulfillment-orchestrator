"""
Hub-and-spoke orchestrator.

v0: gets summarizer/validator/enrichment/fulfillment talking through a
central dispatch loop. Subagents are trusted to handle their own errors --
seems fine for now, revisit if something breaks in prod.
"""

from src.agents.summarizer import SummarizerAgent
from src.agents.validator import ValidatorAgent
from src.agents.enrichment import EnrichmentAgent
from src.agents.fulfillment import FulfillmentAgent
from src.orchestrator.schemas import TaskAssignment


class Orchestrator:
    def __init__(self):
        self.agents = {
            "summarizer": SummarizerAgent(),
            "validator": ValidatorAgent(),
            "enrichment": EnrichmentAgent(),
            "fulfillment": FulfillmentAgent(),
        }

    def dispatch(self, task_id: str, agent_name: str, payload: dict) -> dict:
        agent = self.agents[agent_name]
        task = TaskAssignment(task_id=task_id, agent=agent_name, payload=payload)
        return agent.run(task)

    def process_order(self, order: dict) -> dict:
        enriched = self.dispatch("t1", "enrichment", {"order": order})
        order = {**order, **enriched}
        result = self.dispatch("t2", "fulfillment", {"order": order})
        return result
