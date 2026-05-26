"""Optional vLLM field rename for reasoning responses (no content rewriting)."""

from __future__ import annotations


def normalize_assistant_message(message: dict) -> dict:
    """
    If vLLM returned ``reasoning``, expose it as ``reasoning_content``.

    Chain-of-thought may appear only in ``content`` on Qwen3-VL; that is left unchanged.
    """
    out = dict(message)
    reasoning = out.pop("reasoning", None)
    if reasoning and not out.get("reasoning_content"):
        out["reasoning_content"] = reasoning
    return out
