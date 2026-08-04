# Multi-Agent Fulfillment Orchestrator

A Claude Agent SDK orchestrator for a logistics-tech workflow: support
ticket triage, shipment document processing, and order fulfillment —
built the way a real team actually gets to a production-grade multi-agent
system: by shipping a naive version first, hitting real failure modes, and
fixing them one at a time. The commit history is the story; this README
is the map.

## Why this exists

Multi-agent systems don't fail because a subagent does the wrong thing.
They fail because nobody decided, in writing, who owns a decision, what a
message must contain, and what happens when something goes silent instead
of loud. This repo is a worked example of finding that out the hard way
and fixing it properly:

| Incident | Fix | Where |
|---|---|---|
| Subagent hangs, no error, no record of a decision | Orchestrator owns every retry/escalate decision | `src/orchestrator/orchestrator.py` |
| Hub falls behind under launch-day traffic | Named tradeoff (see ARCHITECTURE.md), API Gateway throttling at the edge | `ARCHITECTURE.md` |
| Validator silently reads orchestrator's system prompt | Context isolation enforced at spawn, not assumed | `src/agents/base.py` |
| Summarizer returns 3 different valid-but-incompatible shapes | Output is a checkable schema, not prose | `src/orchestrator/schemas.py`, `src/agents/summarizer.py` |
| Pipeline stage 3 fails, stages 4/5 silently never run | Stage failures surface explicitly with the exact failure point | `src/pipeline/document_pipeline.py` |
| Evaluator-optimizer loop runs for 3 days with no exit condition | `max_iterations` + `quality_threshold` are required, not optional | `src/orchestrator/evaluator_optimizer.py` |
| New required handoff field crashes older-release agents | Versioned schema with an optional-field migration window | `src/orchestrator/schemas.py` |
| Handoff reports "success" while dropping a flag → duplicate shipment | Structured completion check gates every handoff before it counts as done | `src/orchestrator/completion_check.py` |

## Architecture

Hub-and-spoke topology for ticket/document/order workflows (centralized
audit trail, one place to reconstruct what happened). A separate strictly
sequential pipeline for document processing (explicit stage-level error
handling, because a mid-stage failure blocks everything downstream by
design). Peer-to-peer was evaluated for the compliance workflow and
rejected — distributed state makes a decision log unreconstructable, no
amount of logging fixes that after the fact.

Full reasoning on compute, storage, networking, and IAM: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

![Multi-Agent Fulfillment Orchestrator - Solution Architecture](docs/Multi-Agent%20Orchestrator.png)

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python scripts/run_local.py
```

By default agent calls run against a deterministic stub (see
`src/orchestrator/model_client.py`) so you can develop and test without an
API key. Set `ANTHROPIC_API_KEY` to route through the real Claude API.

## Testing

```bash
PYTHONPATH=. pytest -q
```

See **[TESTING.md](TESTING.md)** for what each test validates and why.

## Deployment status

`infra-cdk/` is a complete AWS CDK (TypeScript) app matching the
architecture doc — VPC, one ECS/Fargate service running the orchestrator,
DynamoDB, S3, an API Gateway HTTP API with a VPC Link, one Lambda for the
fulfillment webhook, and least-privilege IAM per resource, with its own
jest test suite. **It has not been deployed.** This repo ships
infrastructure-as-code that's ready to run (`cdk synth` succeeds with no
AWS credentials required), not a live AWS stack. See "What's actually
deployed" at the bottom of `ARCHITECTURE.md` and `infra-cdk/README.md`
for deploy prerequisites.

## Environments

`config/{dev,staging,prod}.yaml` separate model choice, concurrency
limits, and log verbosity per environment. Nothing environment-specific is
hardcoded in `src/`.

## Roadmap / known gaps

- Load-test `call_model()` against real Anthropic API rate limits before
  any production traffic.
- Move `StateStore` from in-memory to the DynamoDB-backed version in
  `infra-cdk/lib/data-stack.ts`.
- Chaos-test subagent failure mid-handoff (kill a task mid-flight), which
  is the more realistic version of the original Week-1 outage.
- Actually provision `infra-cdk/` in a real AWS account once a team is
  ready to take on that cost (see `infra-cdk/README.md` for the
  bootstrap/Docker prerequisites).
- Split agents into separate Fargate services behind a queue, if
  per-agent compute isolation (not just the context isolation already
  enforced in `src/agents/base.py`) becomes a real requirement.

## Changelog

See commit history — each commit is scoped to one fix, and the commit
message says which incident it responds to.

## License

MIT — see [LICENSE](LICENSE).
