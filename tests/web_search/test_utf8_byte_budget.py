"""Tests for UTF-8 byte budget truncation."""

from web_search.core.utf8_byte_budget import truncate_utf8_to_byte_budget


def test_no_truncation_when_under_budget() -> None:
    text, truncated, orig = truncate_utf8_to_byte_budget("hello", 100)
    assert text == "hello"
    assert truncated is False
    assert orig == 5


def test_truncation_preserves_valid_utf8() -> None:
    text = "αβγδ"  # 8 bytes
    out, truncated, orig = truncate_utf8_to_byte_budget(text, 5)
    assert truncated is True
    assert orig == 8
    assert out.encode("utf-8") == "αβ".encode()
