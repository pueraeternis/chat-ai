"""Tests for reasoning tag fallback parser."""

from operations.reasoning_fallback import split_reasoning_from_content


def test_split_reasoning_block() -> None:
    start = "[THINK]"
    end = "[/THINK]"
    text = f"{start}step one{end}Final answer."
    reasoning, content = split_reasoning_from_content(
        text,
        think_start=start,
        think_end=end,
    )
    assert reasoning == "step one"
    assert content == "Final answer."
