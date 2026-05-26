"""Tests for HTML document Content-Type classification."""

from web_search.core.document_content_type import main_document_is_html


def test_accepts_html_and_xhtml() -> None:
    assert main_document_is_html("text/html; charset=utf-8") is True
    assert main_document_is_html("application/xhtml+xml") is True


def test_rejects_pdf_and_plain_text() -> None:
    assert main_document_is_html("application/pdf") is False
    assert main_document_is_html("text/plain; charset=utf-8") is False


def test_missing_type_treated_as_html() -> None:
    assert main_document_is_html(None) is True
    assert main_document_is_html("") is True
