# LinkedIn Post 2: Technical Deep-Dive

The failure mode that took the longest to track down in my Claude Agent
SDK orchestrator project wasn't a crash. It was a handoff that reported
success while quietly dropping a field.

Here's the setup: an order comes in with a `skip_duplicate_check` flag.
It goes through enrichment, then fulfillment. Somewhere in that handoff,
the flag doesn't make it through. The fulfillment agent gets an order with
no flag, does exactly what it's told, and reports `submitted: true`.
Every log line says success. The customer gets two of the same order.

The instinct is to add more logging. That doesn't fix this, because the
handoff genuinely believed it succeeded. What fixes it is refusing to
trust "no exception was thrown" as the definition of success.

I added a completion check that runs before any handoff counts as
complete: are the expected fields present, are the types and ranges what
they should be. If not, it's treated as a failure and retried or
escalated, not silently accepted. The check itself is dumb on purpose,
just field presence and type validation, because the whole point is
catching the boring failure mode (a dropped field), not trying to be
clever about business logic.

The second thing that mattered as much: moving that retry/escalate
decision out of individual agents and into the orchestrator entirely.
Subagents report what happened. They don't decide what happens next.
That single ownership boundary is what makes the completion check
actually enforceable, because there's exactly one place that has to
respect it.

Code + tests for both of these are in the repo: [link]. The test that
reproduces the duplicate-shipment scenario directly is
`tests/integration/test_fulfillment_duplicate.py`, if you want to see the
failure mode before the fix.

#ClaudeAgentSDK #SoftwareArchitecture #AgenticAI
