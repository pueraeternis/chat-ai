"""Split reasoning tags from content when vLLM leaves them inline."""

from __future__ import annotations


def split_reasoning_from_content(
    content: str | None,
    *,
    think_start: str,
    think_end: str,
) -> tuple[str | None, str | None]:
    """
    Return ``(reasoning_content, content)`` after extracting a think block.

    If no think block is found, returns ``(None, original_content)``.
    """
    if not content or not think_start or not think_end:
        return None, content
    start = content.find(think_start)
    if start < 0:
        return None, content
    end = content.find(think_end, start + len(think_start))
    if end < 0:
        return None, content
    reasoning = content[start + len(think_start) : end].strip()
    remainder = (content[:start] + content[end + len(think_end) :]).strip()
    return reasoning or None, remainder or None


def normalize_assistant_message(message: dict, *, think_start: str, think_end: str) -> dict:
    """Map vLLM ``reasoning`` field and inline think tags to ``reasoning_content``."""
    out = dict(message)
    reasoning = out.pop("reasoning", None)
    if reasoning and not out.get("reasoning_content"):
        out["reasoning_content"] = reasoning
    content = out.get("content")
    if isinstance(content, str) and not out.get("reasoning_content"):
        split_reasoning, new_content = split_reasoning_from_content(
            content,
            think_start=think_start,
            think_end=think_end,
        )
        if split_reasoning:
            out["reasoning_content"] = split_reasoning
            out["content"] = new_content
    return out
