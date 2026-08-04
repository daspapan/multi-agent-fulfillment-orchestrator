"""
HTTP surface for the orchestrator.

This is what actually runs inside the Fargate task -- everything under
src/orchestrator and src/agents runs in-process, in this one service.
There is no per-agent container here; see ARCHITECTURE.md's "Fargate scope"
note for why, and what it would take to change that.
"""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.orchestrator.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="fulfillment-orchestrator")
orchestrator = Orchestrator()


class OrderRequest(BaseModel):
    order_id: str
    customer_id: str
    skip_duplicate_check: bool = False


@app.get("/health")
def health():
    # ALB target group health check hits this. Deliberately dumb: process is up.
    return {"status": "ok"}


@app.post("/orders/process")
def process_order(req: OrderRequest):
    result = orchestrator.process_order(req.model_dump())
    if result["status"] == "failed":
        raise HTTPException(status_code=502, detail=result)
    return result
