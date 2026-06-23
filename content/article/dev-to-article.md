# Nine Ways My Claude Agent SDK Orchestrator Broke Before It Was Production-Ready

I build agentic AI systems for a living now, after about a decade in
blockchain and AWS infrastructure work. I expected the hard part of my
first serious Claude Agent SDK project to be prompting. It wasn't. The
hard part was everything a distributed systems engineer already knows,
applied somewhere I hadn't applied it before.

## The setup

The project: an orchestrator that triages support tickets, processes
shipment documents, and coordinates order fulfillment for a logistics
workflow. Four subagents (summarizer, validator, enrichment, fulfillment)
behind a hub, plus a separate five-stage sequential pipeline for document
processing.

Version one worked. It passed every test I wrote for it. Then I started
asking it questions a production system has to survive, and it fell over
nine different ways.

## What actually broke

**Nobody owned "now what."** A subagent didn't return. No error, no
retry, no record of any decision being made. The subagents had been built
to handle their own failures locally, and none of them had been told what
"handle it" meant. There was no single place with visibility across the
whole task graph.

**The hub became the bottleneck it was built to avoid.** Hub-and-spoke
gives you a centralized audit trail, which several of these workflows
genuinely need. It also means every message and every byte of subagent
state routes through one place, and that place fell behind under a
traffic spike. Neither the benefit nor the cost was written down anywhere
before it mattered.

**A subagent was reading context it was never given.** A validator worked
perfectly in every test, then failed roughly one time in five in
production, only for specific customers. It turned out to be silently
reading values off the orchestrator's system prompt, because the test
harness happened to share that context and a different production
instance didn't.

**"Summarize thoroughly" isn't a schema.** Three runs of the same
instruction returned a bullet list, a paragraph, and a single sentence.
All were valid summaries. None of them were parseable by the JSON
aggregator downstream, because the instruction specified a task, not an
output shape.

**A failed pipeline stage looked identical to no activity.** Stage three
of a five-stage document pipeline failed. Stages four and five didn't
error, they just never ran, because they had no input. Monitoring showed
"nothing happening" where it should have shown "failure," and it took
forty minutes to trace a silence back to its source.

**A loop with no exit condition ran for three days.** An evaluator drafts,
an optimizer scores it against a rubric and sends it back, on a loop that
shipped without a stated stopping point. Someone eventually noticed a
background job quietly consuming budget on a task that should have taken
minutes.

**Peer-to-peer got proposed, and rejected, for good reason.** A different
team wanted direct agent-to-agent communication for a compliance workflow,
reasoning it would cut latency. It got flagged before shipping: distributed
state means there's no single place to reconstruct a decision log after
the fact, and that reconstruction was the entire point of the workflow.

**A schema change crashed every agent that hadn't redeployed yet.** A new
required field for task priority worked fine for updated agents and
crashed every older-release agent the moment it received a message it
couldn't parse. There was no migration path and no fallback for a missing
field.

**A handoff reported success while quietly dropping a flag.** A customer
received two of the same order. Every log line in the fulfillment chain
said success. A full day of investigation found one handoff had silently
dropped a `skip_duplicate_check` flag without raising any error at all.
The downstream system did exactly what it was told, based on a message
that was quietly wrong.

## What fixed it

Five changes, none of them exotic:

The orchestrator owns every retry, substitute, and escalate decision.
Subagents report what happened; they don't decide what happens next.
That's the single change that makes every other fix enforceable, because
there's now exactly one place that has to respect the rules below.

Context isolation is enforced at spawn time, not assumed by convention.
Every subagent gets a blank context window; everything it needs arrives
explicitly in its task payload. Nothing is inherited implicitly from the
orchestrator's state or another agent's output.

Every subagent instruction specifies scope, output schema, and success
criteria the orchestrator can check mechanically. "Summarize thoroughly"
became "return a JSON object matching `SummaryOutput`, a `bullets` array
of 3-5 items and a `confidence` float."

Every evaluator-optimizer loop requires both a max iteration count and a
quality threshold as hard constructor arguments, not optional config.
There is no code path where a loop can run unbounded.

Every handoff runs through a completion check before it's allowed to
count as done: are the expected fields present, are their types and
ranges valid. A handoff that "succeeds" while silently dropping or
corrupting a field is treated as a failure at the boundary, not discovered
later as a duplicate shipment.

## The architecture side

The code fixes needed an infrastructure story to match. Fargate for the
orchestrator (long-lived process, no cold-start penalty on the hub during
a traffic spike) and Lambda for the bursty, stateless paths like the
fulfillment webhook. DynamoDB for task state and idempotency (single-key
access pattern, exactly what it's good at), with RDS deliberately left out
of the hot path since nothing here needs relational joins. Least-privilege
IAM per agent, so a validator's role literally cannot reach the
DynamoDB tables it has no business touching, the IAM-level enforcement of
the same principle the code enforces with `spawn_context()`.

Full reasoning, including the cost tradeoffs and what got rejected, is in
`ARCHITECTURE.md` in the repo. The infrastructure is captured as
deployment-ready CloudFormation, not something I've provisioned against a
real AWS account for this write-up, worth saying plainly rather than
implying otherwise.

## If you're earlier in this than I was

None of the nine failures above were about the model getting something
wrong. Every one was a decision nobody had made yet: who owns a retry, what
a message must contain, what happens when something goes silent instead
of loud. A multi-agent system is a distributed system first. The agent
part is almost the easy bit.

Repo with the full commit history (each fix is its own commit, mapped to
the failure it responds to), architecture doc, and test suite: [link].

---
*Papan Das is an Agentic AI Developer Consultant working across Claude
Agent SDK, AWS, and blockchain infrastructure.*
