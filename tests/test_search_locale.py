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


def test_russian_cyrillic() -> None:
    assert searxng_locale_from_text("Какие новости в Санкт-Петербурге?") == SEARXNG_LOCALE_RU


def test_mixed_cyrillic_majority() -> None:
    assert searxng_locale_from_text("привет there") == SEARXNG_LOCALE_RU


def test_mixed_latin_dominant() -> None:
    assert searxng_locale_from_text("API status ok привет") == SEARXNG_LOCALE_EN


def test_no_letters_defaults_en() -> None:
    assert searxng_locale_from_text("12345 🎉") == SEARXNG_LOCALE_EN
    assert searxng_locale_from_text("") == SEARXNG_LOCALE_EN


def test_cjk_defaults_en() -> None:
    assert searxng_locale_from_text("今天天气怎么样") == SEARXNG_LOCALE_EN


def test_from_messages_last_user() -> None:
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Новости СПб"},
    ]
    assert searxng_locale_from_messages(messages) == SEARXNG_LOCALE_RU
