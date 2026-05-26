"""Truncate UTF-8 text to a maximum number of encoded bytes without splitting codepoints."""


def truncate_utf8_to_byte_budget(text: str, max_bytes: int) -> tuple[str, bool, int]:
    """
    Truncate UTF-8 text to a byte budget without splitting codepoints.

    Return ``(possibly_truncated_text, truncated, original_utf8_byte_length)``.
    If ``max_bytes`` is less than 1, treat as 1.
    """
    raw = text.encode("utf-8")
    original_len = len(raw)
    budget = max(max_bytes, 1)
    if original_len <= budget:
        return text, False, original_len

    cut = bytearray(raw[:budget])
    while cut:
        try:
            decoded = bytes(cut).decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            cut.pop()
            continue
        return decoded, True, original_len
    return "", True, original_len
