# Testing

## Philosophy

Every test here maps to a real incident from the first few weeks of running
this system (see `ARCHITECTURE.md` for the fuller story). This is not
coverage-for-coverage's-sake: each test exists because something specific
broke in a specific way, and we don't want it to break that way again.

## Layout

```
tests/
  unit/            fast, no I/O, one behavior per test
  integration/      exercises the orchestrator + real agent wiring
  smoke/           one end-to-end happy path, meant to run post-deploy
```

## What each file validates and why

- **`unit/test_schemas.py`** - handoff messages default to the current
  schema version, `priority` stays optional (the field that broke old
  clients when it was added), and a message claiming a *future* schema
  version is rejected rather than silently accepted.
- **`unit/test_context_isolation.py`** - a subagent's `spawn_context()`
  only ever contains what was explicitly passed in `task.payload`. This is
  the direct regression test for the "subagent silently reading the
  orchestrator's system prompt" bug.
- **`unit/test_evaluator_optimizer.py`** - the loop always terminates,
  either by hitting the quality threshold or by hitting `max_iterations`.
  Also checks that you can't construct a loop without both bounds set.
- **`unit/test_completion_check.py`** - a result missing a required field,
  or with a required field explicitly `None`, fails the completion check.
  This is the general-purpose version of the silent-failure gate.
- **`integration/test_orchestrator_retry.py`** - confirms retry decisions
  live in the orchestrator, not the agent: a flaky agent gets retried up to
  `MAX_RETRIES`, and every attempt shows up in the decision log.
- **`integration/test_document_pipeline.py`** - a stage-3 validation
  failure reports `failed_stage: 3` explicitly, instead of stages 4/5 just
  never running with no signal as to why.
- **`integration/test_fulfillment_duplicate.py`** - direct regression test
  for the duplicate-shipment incident: submitting the same `order_id`
  twice returns `status: "rejected"` on the second call, not a silent
  second fulfillment.
- **`smoke/test_smoke.py`** - one full `process_order()` call, no mocking
  of internals. Intended to also run against a live deployment as a
  post-deploy sanity check, not just in CI.

## Running locally

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -q                 # everything
PYTHONPATH=. pytest tests/unit -q      # fast subset while iterating
PYTHONPATH=. pytest tests/smoke -q     # post-deploy check
```

## Running in CI

`.github/workflows/ci.yml` runs pytest against Python 3.10 and 3.11 on
every push and PR. See that file for the exact matrix.

## Known gaps (cut for time, not hidden)

- No load/soak test against a real Bedrock/Anthropic endpoint yet - the
  `call_model()` stub is deterministic and doesn't reflect real model
  latency or rate limits. Before a real production rollout this needs a
  load test against actual API quotas.
- `StateStore` is in-memory in this repo. The DynamoDB-backed version
  described in ARCHITECTURE.md needs its own integration tests against a
  local DynamoDB (e.g. dynamodb-local) before it replaces this one.
- No chaos/fault-injection testing (e.g. killing a subagent mid-handoff)
  yet, which is the more realistic version of the Week-1 outage this
  project is a response to.
