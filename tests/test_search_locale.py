"""Tests for SearXNG locale detection from user text."""

from __future__ import annotations

from operations.search_locale import (
    SEARXNG_LOCALE_EN,
    SEARXNG_LOCALE_RU,
    searxng_locale_from_messages,
    searxng_locale_from_text,
)


def test_english_latin() -> None:
    assert searxng_locale_from_text("What is the weather in London?") == SEARXNG_LOCALE_EN


def test_cyrillic_script() -> None:
    # Cyrillic letters only (locale detection, not natural-language content).
    assert searxng_locale_from_text("\u0410\u0411\u0412\u0413\u0414\u0415?") == SEARXNG_LOCALE_RU


def test_russian_user_message() -> None:
    assert searxng_locale_from_text("Какие сегодня новости?") == SEARXNG_LOCALE_RU


def test_mixed_cyrillic_majority() -> None:
    assert searxng_locale_from_text("\u0430\u0431\u0432\u0433\u0434 there") == SEARXNG_LOCALE_RU


def test_mixed_latin_dominant() -> None:
    assert searxng_locale_from_text("API status ok \u0430\u0431") == SEARXNG_LOCALE_EN


def test_no_letters_defaults_en() -> None:
    assert searxng_locale_from_text("12345 🎉") == SEARXNG_LOCALE_EN
    assert searxng_locale_from_text("") == SEARXNG_LOCALE_EN


def test_cjk_defaults_en() -> None:
    assert searxng_locale_from_text("今天天气怎么样") == SEARXNG_LOCALE_EN


def test_from_messages_last_user() -> None:
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "\u0410\u0411\u0412"},
    ]
    assert searxng_locale_from_messages(messages) == SEARXNG_LOCALE_RU
