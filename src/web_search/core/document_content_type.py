"""Classify top-level HTTP Content-Type for fetch tools (HTML vs everything else)."""


def main_document_is_html(content_type: str | None) -> bool:
    """
    Return True only for responses that should be treated as HTML document trees.

    Unknown/missing ``Content-Type`` is treated as HTML (many sites omit it;
    Playwright still renders DOM).
    """
    if content_type is None or not content_type.strip():
        return True
    main = content_type.split(";", maxsplit=1)[0].strip().lower()
    return main in ("text/html", "application/xhtml+xml")
