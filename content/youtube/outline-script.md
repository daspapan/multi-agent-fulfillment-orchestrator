# YouTube Video: Outline + Script

**Working title:** I Built a Production Multi-Agent System on Claude
(Here's Everywhere It Broke First)

**Length target:** 12-15 minutes

## Hook (0:00-0:45)

"I built a multi-agent orchestrator on the Claude Agent SDK, and in the
first few weeks of pushing it toward production, it broke in nine
different ways. None of them were the AI being wrong. Every single one
was an architecture decision I hadn't made yet. This video is those nine
failures, and the five rules I ended up with to fix them for good."

Show on screen: the architecture diagram from ARCHITECTURE.md, hub with
one spoke highlighted red.

## Section 1: The naive version (0:45-2:30)

Screen recording of the first commit. Walk through: orchestrator,
four subagents (summarizer, validator, enrichment, fulfillment), each
handling its own errors. "This is where almost everyone starts, including
me. It passes every test you'll think to write."

## Section 2: The nine failures, fast (2:30-7:00)

Go through the scenes from the project narrative in order, roughly 30
seconds each, screen-recording the relevant test or code:
1. Subagent hangs, no error logged, no decision recorded
2. Hub falls behind under a traffic spike
3. Validator silently reads the orchestrator's system prompt
4. Summarizer output shape changes between runs
5. Pipeline stage 3 fails, stages 4-5 silently never run
6. Evaluator-optimizer loop with no exit condition
7. Peer-to-peer proposed for compliance workflow, rejected
8. New required field crashes old-release agents
9. Handoff reports success while dropping a flag -> duplicate shipment

For each: show the ~1 line of code or config that was missing, not a full
explanation. Speed is the point here.

## Section 3: The five rules that fixed it (7:00-11:00)

Slower pace here, this is the actual value of the video.
- Orchestrator owns every retry/escalate decision - show
  `orchestrator.py`'s `dispatch()` method.
- Context isolation is enforced, not assumed - show `spawn_context()`.
- Subagent instructions are a contract - show `SummaryOutput` schema
  replacing prose.
- Every loop has a hard exit condition - show `EvaluatorOptimizerLoop`.
- Handoffs get a completion check before they count as done - show
  `check_completion()` and walk through the duplicate-shipment test.

## Section 4: Architecture walkthrough (11:00-13:30)

Screen share `ARCHITECTURE.md`. Cover the topology choice (hub-and-spoke
vs pipeline vs why peer-to-peer got rejected) and the compute/storage
decisions (Fargate vs Lambda, DynamoDB vs RDS) at a level someone new to
AWS can follow. Be explicit that the AWS resources are IaC-only in this
project, not a live deployment, and say why (cost, scope).

## Close (13:30-14:30)

"If you're earlier in this than I was, the thing I'd want someone to have
told me: none of these nine failures are about the model. They're about
whether you decided, in writing, who owns what happens next. Full repo,
architecture doc, and test suite are linked below. If you've hit a
different failure mode building on the Agent SDK, drop it in the comments,
I want to hear it."

## Notes for editing
- Pull actual terminal output from `pytest -q` runs where possible, real
  output reads better than a mockup.
- Diagram from ARCHITECTURE.md's ASCII art can be redrawn cleanly for the
  thumbnail/cover per the image suggestions in the original project brief.
