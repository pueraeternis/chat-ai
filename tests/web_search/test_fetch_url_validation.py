"""Tests for fetch URL policy validation (SSRF / internet-only)."""

import socket
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

import pytest

from web_search.core.errors import UrlFetchPolicyError
from web_search.core.fetch_policies_config import load_fetch_policies_config
from web_search.core.fetch_url_validation import (
    CODE_FORBIDDEN_URL,
    CODE_INVALID_URL,
    CODE_PRIVATE_NETWORK_FORBIDDEN,
    CODE_UNSUPPORTED_SCHEME,
    validate_fetch_url_before_fetch,
)


@pytest.fixture
def fetch_policies_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "web_search" / "fetch_policies.yaml"


def test_rejects_missing_scheme(fetch_policies_path: Path) -> None:
    cfg = load_fetch_policies_config(fetch_policies_path)
    with pytest.raises(UrlFetchPolicyError) as exc:
        validate_fetch_url_before_fetch("example.com/path", cfg)
    assert exc.value.code == CODE_INVALID_URL


def test_rejects_unsupported_scheme(fetch_policies_path: Path) -> None:
    cfg = load_fetch_policies_config(fetch_policies_path)
    with pytest.raises(UrlFetchPolicyError) as exc:
        validate_fetch_url_before_fetch("ftp://example.com/", cfg)
    assert exc.value.code == CODE_UNSUPPORTED_SCHEME


def test_rejects_loopback_literal(fetch_policies_path: Path) -> None:
    cfg = load_fetch_policies_config(fetch_policies_path)
    with pytest.raises(UrlFetchPolicyError) as exc:
        validate_fetch_url_before_fetch("http://localhost/", cfg)
    assert exc.value.code == CODE_PRIVATE_NETWORK_FORBIDDEN


def test_rejects_ipv6_loopback_literal(fetch_policies_path: Path) -> None:
    cfg = load_fetch_policies_config(fetch_policies_path)
    with pytest.raises(UrlFetchPolicyError) as exc:
        validate_fetch_url_before_fetch("http://[::1]/", cfg)
    assert exc.value.code == CODE_PRIVATE_NETWORK_FORBIDDEN


def test_accepts_public_literal_ip(fetch_policies_path: Path) -> None:
    cfg = load_fetch_policies_config(fetch_policies_path)
    validate_fetch_url_before_fetch("https://1.1.1.1/", cfg)


def test_rejects_dns_resolving_to_private(fetch_policies_path: Path) -> None:
    cfg = load_fetch_policies_config(fetch_policies_path)
    fake = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0)),
    ]
    with (
        patch("socket.getaddrinfo", return_value=fake),
        pytest.raises(UrlFetchPolicyError) as exc,
    ):
        validate_fetch_url_before_fetch("http://corp.internal.example/", cfg)
    assert exc.value.code == CODE_PRIVATE_NETWORK_FORBIDDEN


def test_rejects_unresolvable_host(fetch_policies_path: Path) -> None:
    cfg = load_fetch_policies_config(fetch_policies_path)

    def boom(*_a: object, **_k: object) -> NoReturn:
        raise socket.gaierror(1, "nope")

    with (
        patch("socket.getaddrinfo", side_effect=boom),
        pytest.raises(UrlFetchPolicyError) as exc,
    ):
        validate_fetch_url_before_fetch("http://does-not-exist.invalid/", cfg)
    assert exc.value.code == CODE_FORBIDDEN_URL


def test_accepts_host_when_dns_returns_public(fetch_policies_path: Path) -> None:
    cfg = load_fetch_policies_config(fetch_policies_path)
    fake = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 0)),
    ]
    with patch("socket.getaddrinfo", return_value=fake):
        validate_fetch_url_before_fetch("https://example.com/", cfg)


def test_extra_blocked_cidr_applies_to_public_ip(tmp_path: Path) -> None:
    p = tmp_path / "policies.yaml"
    p.write_text(
        "allowed_schemes:\n  - https\nextra_blocked_cidrs:\n  - 1.1.1.1/32\n",
        encoding="utf-8",
    )
    cfg = load_fetch_policies_config(p)
    with pytest.raises(UrlFetchPolicyError) as exc:
        validate_fetch_url_before_fetch("https://1.1.1.1/", cfg)
    assert exc.value.code == CODE_PRIVATE_NETWORK_FORBIDDEN
