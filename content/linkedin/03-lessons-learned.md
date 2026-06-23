# LinkedIn Post 3: Lessons Learned

Three things I'd tell someone starting their first production multi-agent
project on Claude, based on what actually broke in mine:

Your subagents' instructions are a contract, not a suggestion. "Summarize
this thoroughly" is a request. It is not something a downstream parser can
depend on. Once I rewrote every subagent instruction to specify scope,
output schema, and success criteria explicitly, most of my "the model is
inconsistent" problems turned out to be "I never told it what shape I
needed."

Centralizing state costs you something, so decide on purpose, not by
default. Hub-and-spoke gave me a single place to reconstruct what
happened, which a compliance-style workflow genuinely needs. It also gave
me a throughput ceiling as I added more subagents, because everything
routes through one place. Both of those are true at once. Naming the
tradeoff out loud, instead of discovering it during a traffic spike, is
the actual skill here.

A loop without a hard stop is not a design decision you made, it's a bug
you haven't met yet. I shipped an evaluator-optimizer pattern once without
a stated max-iteration count, reasoning I'd add it later if needed. Later
turned out to mean a background job quietly running for three days.
`max_iterations` and a quality threshold are non-negotiable now, not
config someone can forget to set.

None of this is exotic. It's the same discipline any distributed system
needs, applied to agents instead of services. The hard part isn't
Claude getting something wrong, it's remembering that a multi-agent
system is still a distributed system, with all the same failure modes,
wearing a different hat.

#AgenticAI #ClaudeAgentSDK #EngineeringLessons #AWS
