# LinkedIn Post 1: Announcement

I spent the last few weeks building my first production-grade multi-agent
system on the Claude Agent SDK, and I want to be honest about how it
actually went: not smoothly.

I started where most people start. One orchestrator, a few subagents,
each one handling its own errors, each one trusted to do the right thing
with whatever context it happened to have. It worked in every test I
threw at it.

Then I started treating it like it had to survive production, not just
pass a demo, and found nine different ways it would quietly fail: a
subagent that hangs with zero error logged, another one silently reading
values it was never explicitly given, a summarizer whose output format
changed between runs, a pipeline stage that fails and just... stops,
taking the rest of the pipeline down with it but showing no error
anywhere.

None of these were "the AI got it wrong." They were architecture
decisions I hadn't made yet, disguised as bugs.

I rebuilt the system around five rules: the orchestrator owns every
retry/escalate decision, subagents get a blank context window and nothing
implicit, every subagent output is a checked schema instead of hopeful
prose, every loop has a hard exit condition, and no handoff counts as
"done" until a completion check confirms nothing silently dropped.

Full writeup, architecture doc, and code: [repo link]

If you're building multi-agent systems on Claude and want to compare
notes on where this stuff actually breaks, I'd like to hear what you've
run into.

#AgenticAI #ClaudeAgentSDK #AWS #MultiAgentSystems
