"""Tests for vLLM reasoning field passthrough (no content rewriting)."""

from operations.reasoning_fallback import normalize_assistant_message


def test_normalize_maps_vllm_reasoning_field() -> None:
    msg = {"role": "assistant", "reasoning": "thoughts", "content": "answer"}
    out = normalize_assistant_message(msg)
    assert out["reasoning_content"] == "thoughts"
    assert out["content"] == "answer"
    assert "reasoning" not in out


def test_normalize_leaves_content_when_no_vllm_reasoning_field() -> None:
    msg = {"role": "assistant", "content": "Step one.\nFinal answer."}
    out = normalize_assistant_message(msg)
    assert out.get("reasoning_content") is None
    assert out["content"] == "Step one.\nFinal answer."
