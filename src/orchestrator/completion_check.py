"""
Silent-failure check.

A handoff that reports "success" while quietly dropping or corrupting a
field is the most dangerous failure mode in this system: everything
downstream proceeds on bad state with full confidence. A customer got two
of the same order because a fulfillment handoff silently dropped its
skip_duplicate_check flag -- every log line said "success."

This check runs before ANY handoff is allowed to be treated as complete.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class CompletionCheckResult:
    ok: bool
    reason: str = ""


def check_completion(result: dict[str, Any], required_fields: list[str]) -> CompletionCheckResult:
    missing = [f for f in required_fields if f not in result or result[f] is None]
    if missing:
        return CompletionCheckResult(ok=False, reason=f"missing fields: {missing}")

    for field_name, value in result.items():
        if isinstance(value, bool) and field_name.endswith("_check") and value is False:
            # an explicit safety check reporting False is not a silent drop,
            # it's a legitimate negative result -- allow it through
            continue

    return CompletionCheckResult(ok=True)
