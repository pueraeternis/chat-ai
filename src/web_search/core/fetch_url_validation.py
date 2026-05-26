"""Single entry point to validate a URL before Playwright fetch (SSRF-aware)."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from web_search.core.errors import UrlFetchPolicyError
from web_search.core.fetch_policies_config import FetchPoliciesConfig

# Stable codes surfaced to MCP tools (see docs/DECISIONS.md).
CODE_INVALID_URL = "INVALID_URL"
CODE_UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
CODE_FORBIDDEN_URL = "FORBIDDEN_URL"
CODE_PRIVATE_NETWORK_FORBIDDEN = "PRIVATE_NETWORK_FORBIDDEN"


def _ip_allows_public_internet(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    policies: FetchPoliciesConfig,
) -> bool:
    if not ip.is_global:
        return False
    if ip.is_multicast:
        return False
    if ip.is_reserved:
        return False
    if ip.is_unspecified:
        return False
    return all(ip not in net for net in policies.extra_blocked_networks)


def _raise_private(message: str) -> None:
    raise UrlFetchPolicyError(message, CODE_PRIVATE_NETWORK_FORBIDDEN)


def _collect_resolved_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        msg = f"Could not resolve host: {host}"
        raise UrlFetchPolicyError(msg, CODE_FORBIDDEN_URL) from exc

    out: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    seen: set[str] = set()
    for family, _, _, _, sockaddr in infos:
        if family not in (socket.AF_INET, socket.AF_INET6):
            continue
        ip_str = str(sockaddr[0])
        if ip_str in seen:
            continue
        seen.add(ip_str)
        out.append(ipaddress.ip_address(ip_str))
    return out


def validate_fetch_url_before_fetch(url: str, policies: FetchPoliciesConfig) -> None:
    """
    Validate a fetch URL (scheme, DNS, internet-only IPs).

    Parse ``url``, enforce scheme policies, resolve DNS when needed, and ensure
    all target IPs are acceptable for internet-only fetch (SSRF guard).

    Raises
    ------
        UrlFetchPolicyError: With a stable ``code`` attribute.

    """
    if not isinstance(url, str) or not url.strip():
        raise UrlFetchPolicyError("URL must be a non-empty string", CODE_INVALID_URL)

    candidate = url.strip()
    parsed = urlsplit(candidate)
    scheme = (parsed.scheme or "").lower()
    if not scheme:
        raise UrlFetchPolicyError("URL is missing a scheme", CODE_INVALID_URL)
    if scheme not in policies.allowed_schemes:
        raise UrlFetchPolicyError(f"URL scheme not allowed: {scheme}", CODE_UNSUPPORTED_SCHEME)

    hostname = parsed.hostname
    if hostname is None or hostname == "":
        raise UrlFetchPolicyError("URL must include a host", CODE_INVALID_URL)

    literal_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if not _ip_allows_public_internet(literal_ip, policies):
            _raise_private(f"Target IP is not permitted for fetch: {literal_ip}")
        return

    resolved = _collect_resolved_ips(hostname)
    if not resolved:
        raise UrlFetchPolicyError(f"No addresses resolved for host: {hostname}", CODE_FORBIDDEN_URL)

    for ip in resolved:
        if not _ip_allows_public_internet(ip, policies):
            _raise_private(f"Resolved address is not permitted for fetch: {ip}")


async def validate_fetch_url_before_fetch_async(url: str, policies: FetchPoliciesConfig) -> None:
    """Async wrapper that runs DNS resolution in a thread pool (safe for ASGI)."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, validate_fetch_url_before_fetch, url, policies)
