# Architecture

Status: this document describes the target production architecture and
the reasoning behind it. The code in this repo runs the full agent logic
locally against an in-memory state store and a stubbed model client. The
AWS resources below are captured as CloudFormation in `infra/template.yaml`
but are **not provisioned** — see "What's actually deployed" at the bottom.

## The problem this is solving

A hub-and-spoke Claude Agent SDK orchestrator triages support tickets,
processes shipment documents, and coordinates order fulfillment for a
logistics workflow. Nine incidents over the system's first three months
(unowned error handling, an overloaded hub, context leakage between
subagents, unparseable subagent output, a pipeline that failed silently,
an unbounded optimizer loop, a schema change that broke old clients, and a
duplicate shipment from a dropped flag) drove the design decisions below.
The code fixes are in the commit history; this document is the
infrastructure and topology side of the same response.

## Compute: Lambda vs ECS/Fargate vs EC2

**Decision: ECS/Fargate for the orchestrator and long-running subagents;
Lambda for the fulfillment webhook receiver and the completion-check
validator.**

The orchestrator holds in-process state across a multi-step task graph
(dispatch, retry, aggregate) and needs to keep a model conversation "warm"
across subagent calls in some flows. Lambda's per-invocation model and
15-minute execution ceiling fight that: you'd end up re-hydrating state on
every invocation from DynamoDB anyway, which just moves the complexity
without removing it. Fargate gives a long-lived process, predictable
memory for holding multiple in-flight task graphs, and no cold-start
latency on the hub itself, which matters directly for the "Tuesday-morning
stall" failure mode: a cold Lambda hub under launch-day traffic is a worse
version of the same bottleneck.

Lambda is the right shape for two things here specifically: the
fulfillment webhook receiver (pure request/response, needs to scale to
zero between orders) and the completion-check validator (a pure function
of a result dict, no state, cheap to run on every handoff). Running those
two on Fargate would just be paying for idle capacity.

EC2 was ruled out entirely: nothing here needs to manage the underlying
instances, and ECS/Fargate gets the same container-based deployment model
without the patching burden. If a future workload needs GPU inference
outside of Bedrock, that's the one case that would bring EC2 back into
scope.

**Cost tradeoff:** Fargate runs continuously for the orchestrator (a small
fixed cost, sized to the smallest task that keeps p99 dispatch latency
under the SLA) versus Lambda's true pay-per-invocation for the bursty
paths. This is deliberately not "everything serverless" — the orchestrator
is the one component where always-on beats scale-to-zero.

## Storage: DynamoDB, S3, RDS

**DynamoDB** backs the `StateStore` (task records + decision log) and the
fulfillment idempotency table (the `attribute_not_exists` conditional
write pattern already proven out in the CrossLedger project). Task lookups
are always by `task_id`, access is single-digit-millisecond-latency
sensitive on the hot path, and the write pattern (append to a decision
log, conditional-write for idempotency) is exactly what DynamoDB is good
at. No relational joins are needed anywhere in this data path.

**S3** stores raw shipment documents and support-ticket attachments before
they reach the summarizer/validator agents, plus the completion-record
audit trail as a durable, cheap, long-retention log (DynamoDB TTL clears
the hot copy after 30 days; S3 keeps it for compliance).

**RDS was considered and rejected** for this workload specifically. The
compliance audit workflow (Scene 7) needs a reconstructable decision log,
not relational queries across normalized tables — DynamoDB's per-task item
plus an S3 archive satisfies that requirement more directly, and avoids
paying for a relational engine and its patching/failover overhead for data
that's fundamentally accessed by a single key. If a future requirement
needs ad hoc cross-task SQL analytics, that's a Redshift/Athena-over-S3
job against the archive, not a reason to put RDS in the hot path.

## Networking: VPC layout, API Gateway

The orchestrator and its subagents run in private subnets across two AZs,
with no direct internet route. Outbound calls to the Anthropic API /
Bedrock go through a NAT gateway; inbound traffic (the fulfillment
webhook, the support-ticket ingestion endpoint) comes through API Gateway
into a VPC link, so nothing public talks directly to the orchestrator's
network.

**API Gateway** fronts the two public entry points (ticket ingestion,
fulfillment webhook) with request validation at the edge (schema-checked
before it ever reaches a Lambda or the orchestrator) and throttling
configured per the "Tuesday-morning stall" lesson: better to return 429s
at the edge under a traffic spike than let requests queue silently inside
the hub with no backpressure signal.

Two AZs, not three, for the first production rollout: this workload's
availability target doesn't yet justify the added NAT gateway cost of a
third AZ, and this is a cost/availability tradeoff explicitly flagged for
revisit if traffic or SLA requirements grow.

## IAM: least privilege

Each subagent's Fargate task role is scoped to exactly what that agent
touches: the validator's role has read-only access to the S3 documents
bucket and no DynamoDB permissions at all; the fulfillment agent's role
has read/write on the idempotency table and invoke permission on the
downstream warehouse API, nothing else. The orchestrator's role is the
only one with write access to the decision-log table and the only one
permitted to invoke the Bedrock/Anthropic model-call role used for
retry/escalation reasoning — subagents that need a model call go through a
narrower, read-only-context role.

No component holds a broad `dynamodb:*` or `s3:*` grant. This is slower to
set up than one shared role and is the point: it's the IAM-level
enforcement of "a subagent should not be able to reach state it wasn't
explicitly given," the same principle `spawn_context()` enforces in code.

## Topology: hub-and-spoke, pipeline, and why peer-to-peer is off the table

See the `Technical Approach` reasoning captured in the commit history and
`README.md` — the short version: hub-and-spoke is the default because most
workflows here need a full, centralized audit trail; the document
pipeline uses a strictly sequential topology with explicit stage-level
error surfacing; and peer-to-peer was evaluated and rejected for the
compliance workflow specifically because distributed state makes a
decision log structurally unreconstructable, which no amount of logging
discipline can fix after the fact.

## What's actually deployed

Per project scope: this repository ships `infra/template.yaml` (AWS SAM /
CloudFormation) describing the resources above — VPC, subnets, ECS
cluster + Fargate task definitions, DynamoDB tables, S3 buckets, API
Gateway, and the IAM roles/policies — as deployment-ready infrastructure
as code. **Nothing in this document has been provisioned against a real
AWS account as part of this project.** `sam deploy` / `aws cloudformation
deploy` against `infra/template.yaml` is the next step for a team that
wants to actually stand this up, and doing so will incur real AWS costs
(NAT gateway and Fargate being the two line items worth watching first).
