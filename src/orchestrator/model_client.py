"""
Thin wrapper around the Claude Agent SDK / Anthropic API.

Kept separate from agent logic so subagents can be unit tested without
hitting the network. Set ANTHROPIC_API_KEY to use the real client; falls
back to a deterministic stub otherwise (used in tests and local dev).
"""

import os

_client = None


def get_client():
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    from anthropic import Anthropic
    _client = Anthropic(api_key=api_key)
    return _client


def call_model(prompt: str, model: str = "claude-sonnet-4-5", max_tokens: int = 1024) -> str:
    client = get_client()
    if client is None:
        return f"[stub response, {len(prompt)} char prompt]"
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
