# Plan 08 - security and platform boundaries

**Status:** Completed.
**Goal:** Strengthen the platform boundary and security posture for the public self-hosted AI platform reference implementation without turning the repository into SaaS infrastructure.

**Scope:** Practical security hardening only: optional static API key authentication, SSRF hardening for Playwright-backed fetch, internal boundary consistency, focused security regression tests, and documentation updates.

**References:** [src/adapters/http_api.py](../../src/adapters/http_api.py), [src/core/settings.py](../../src/core/settings.py), [src/core/openai_errors.py](../../src/core/openai_errors.py), [src/web_search/core/fetch_url_validation.py](../../src/web_search/core/fetch_url_validation.py), [src/web_search/operations/fetch_page_html.py](../../src/web_search/operations/fetch_page_html.py), [src/web_search/operations/fetch_page_markdown.py](../../src/web_search/operations/fetch_page_markdown.py), [src/web_search/mcp_servers/](../../src/web_search/mcp_servers/), [docker-compose.yml](../../docker-compose.yml), [.env.example](../../.env.example).

---

## 1. Objective

Improve security and platform boundaries while preserving the repository's role as:

- public portfolio flagship;
- self-hosted AI platform reference implementation;
- OpenAI Chat Completions-compatible backend;
- production-minded, but not enterprise SaaS.

The implementation should add high-value controls with minimal operational burden:

- optional static API key authentication for chat-proxy;
- stronger SSRF protection for hosted web search page fetch;
- consistent public/internal service boundary documentation and configuration;
- regression tests for the new security behavior.

---

## 2. Motivation

Plan 07 made chat-proxy the documented public API boundary and represented vLLM, web-search MCP, and SearXNG as internal services. At plan time, the boundary was soft in a few important places:

- chat-proxy accepted `/v1/models` and `/v1/chat/completions` without checking `Authorization`;
- hosted web search validated the initial URL before Playwright navigation, but redirects and browser subresource requests were not yet governed by the same SSRF policy;
- direct host exposure was mostly correct in Compose, but docs explicitly said native auth was not implemented.

These are worth fixing before broader feature work because they improve the safety of the reference architecture without adding accounts, tenants, OAuth, billing, quotas, Kubernetes, gateways, or enterprise IAM.

---

## 3. Pre-implementation baseline

Captured at plan time before implementation.

### Facts verified from the codebase

| Area | Current state |
|------|---------------|
| HTTP app | `create_app()` in `src/adapters/http_api.py` defines `GET /health`, `GET /v1/models`, `POST /v1/chat/completions`, and a `/v1/{path:path}` 404 fallback. |
| Chat settings | `ChatProxySettings` in `src/core/settings.py` has host, port, vLLM URL/timeouts, default model, web-search MCP URL, MCP timeout, and logging settings. No auth setting exists. |
| Error shape | `src/core/openai_errors.py` already centralizes OpenAI-style JSON error payloads and app error handling. |
| Request parsing | `POST /v1/chat/completions` calls `await request.json()` directly, then checks that the parsed body is a JSON object. |
| Auth | No current route checks `Authorization`; README and production docs state that Bearer headers are placeholders and not enforced. |
| URL validation | `validate_fetch_url_before_fetch()` validates scheme, host presence, literal IPs, DNS resolution, public IP status, multicast/reserved/unspecified addresses, and configured extra blocked CIDRs. |
| Playwright fetch | `fetch_page_html()` validates the initial URL before fetch, then `load_html_document()` calls `page.goto()` and records `page.url` as `final_url`. No final URL validation or subresource route blocking is installed. |
| Markdown fetch | `src/web_search/operations/fetch_page_markdown.py` exists and is relevant. `fetch_page_markdown()` validates the initial URL, then reuses `load_html_document()` from `fetch_page_html.py`, so final URL and subresource hardening in the shared HTML path affects markdown fetch too. |
| MCP HTTP boundary | `create_web_search_mcp(http_mode=True)` enables MCP DNS rebinding protection with allowed hosts defaulting to `web-search-mcp:3333,localhost:3333`. |
| Compose exposure | vLLM, SearXNG, and web-search MCP host ports bind to `127.0.0.1`; chat-proxy and Open WebUI bind through host ports without a localhost restriction. |
| Existing tests | URL validation tests already patch DNS. Fetch operation tests use mocked Playwright pages. HTTP tests use `httpx.ASGITransport` against `create_app()`. |

### Hypotheses (verified during implementation)

- Playwright route handlers can apply the existing async URL validator to subresource requests with acceptable overhead for this reference stack — confirmed.
- Final URL validation should happen after navigation and before returning HTML or markdown, using the same policy function to avoid duplicate SSRF logic — implemented.

---

## 4. Scope

### In scope

- Add `CHAT_PROXY_API_KEY` as an optional static API key.
- Treat an empty or unset API key as auth disabled.
- Enforce `Authorization: Bearer <token>` on:
  - `GET /v1/models`;
  - `POST /v1/chat/completions`.
- Keep `GET /health` unauthenticated.
- Return OpenAI-style JSON for missing or invalid credentials.
- Validate Playwright fetch final URLs after redirects.
- Abort unsafe Playwright subresource requests during page load.
- Preserve successful fetches of normal public HTTP/HTTPS pages.
- Add unit/regression tests for auth, final URL validation, and subresource blocking.
- Update current-facing docs and `.env.example` only as needed to document the new knobs.

### Scope guardrails

- Prefer direct helpers and route-level checks over framework-heavy abstractions.
- Reuse `openai_error_payload()` and existing URL validation logic where possible.
- Keep new configuration env-backed, explicit, and optional.
- Keep Docker topology unchanged unless a future review finds a small, clearly necessary boundary consistency issue.

---

## 5. Non-goals

- User accounts.
- Tenants.
- OAuth.
- Billing.
- Quotas.
- Enterprise IAM.
- Full API gateway implementation.
- Kubernetes.
- Service mesh.
- Complex secret management.
- Browser sandboxing beyond URL policy enforcement.
- Replacing SearXNG, MCP, vLLM, FastAPI, or Playwright.
- Comprehensive WAF behavior, rate limiting, abuse detection, or distributed authorization.
- Request/body size limits for chat-proxy.
- `CHAT_PROXY_MAX_REQUEST_BYTES`.
- Route-level body-limit implementation.
- `413` oversized-body behavior.
- JSON parsing refactors, except as a trivial optional follow-up if touched naturally while implementing auth.

Request/body limits remain a good future API-hardening improvement and may become Plan 09. They are intentionally deferred so Plan 08 stays focused on authentication, SSRF hardening, and boundary consistency.

---

## 6. Security decisions

| Topic | Decision |
|-------|----------|
| Auth model | Optional single static API key for chat-proxy, configured by env. |
| Disabled state | If `CHAT_PROXY_API_KEY` is unset or empty after trimming, auth is disabled. |
| Header format | Require exactly `Authorization: Bearer <token>` when auth is enabled. |
| Protected endpoints | Protect `/v1/models` and `/v1/chat/completions`; leave `/health` open for health checks. |
| Error response | Use OpenAI-style JSON with HTTP `401`; do not leak whether the key was missing or wrong. |
| Token comparison | Use constant-time comparison (`secrets.compare_digest`) and never log token values. |
| API key storage | Plain env var only; no secret manager abstraction in this plan. |
| Request/body limits | Deferred from Plan 08. Treat as a future API-hardening wave, likely Plan 09. |
| JSON parsing | Do not refactor as part of Plan 08 unless a trivial cleanup falls out of auth route changes. |
| Health checks | Existing Compose health checks must continue to work without auth headers. |
| SSRF initial URL | Keep the existing initial URL validation path. |
| SSRF redirects | Validate the final URL after Playwright navigation before reading or returning page content. |
| SSRF subresources | Install a Playwright request route that aborts unsafe subresource/navigation requests to private, loopback, link-local, multicast, reserved, unspecified, or extra-blocked CIDR targets. |
| SSRF policy source | Reuse `FetchPoliciesConfig` and `validate_fetch_url_before_fetch_async()` rather than creating a second policy language. |
| Browser sandbox | Do not overbuild a full browser sandbox; focus on URL policy enforcement and regression coverage. |
| Internal exposure | Keep current Compose localhost bindings for vLLM, SearXNG, and web-search MCP; document the boundary clearly. |

---

## 7. Implementation steps

### 7.1 Chat-proxy API key settings

- [x] Add `api_key: str = ""` to `ChatProxySettings`.
- [x] Document the env var as `CHAT_PROXY_API_KEY`.
- [x] Keep defaults compatible with current local development: auth disabled unless explicitly configured.

### 7.2 Chat-proxy authentication

- [x] Add a small helper in `src/adapters/http_api.py`, for example:
  - `_auth_enabled(settings: ChatProxySettings) -> bool`;
  - `_authorize_request(request: Request) -> JSONResponse | None`.
- [x] Read `request.app.state.settings` inside the protected route handlers.
- [x] Enforce the helper at the start of:
  - `list_models()`;
  - `chat_completions()`.
- [x] Leave `health()` unchanged and unauthenticated.
- [x] Return `401` with OpenAI-style content for missing, malformed, or invalid credentials.
- [x] Use `WWW-Authenticate: Bearer` if it remains simple and does not complicate client behavior.
- [x] Avoid logging the API key, the supplied token, or full `Authorization` header.

### 7.3 SSRF final URL validation

- [x] Update `load_html_document()` to accept `policies: FetchPoliciesConfig`.
- [x] After `page.goto()` completes, validate `page.url` before content-type checks and before `page.content()`.
- [x] Return a structured failed `FetchPageHtmlResult` with the existing URL policy code on final URL rejection.
- [x] Ensure `fetch_page_markdown()` keeps propagating the HTML fetch failure code/message.
- [x] Keep normal public redirects working.

### 7.4 SSRF subresource blocking

- [x] Add a focused helper near the fetch operation or Playwright adapter, for example:
  - `install_fetch_url_policy_route(page, policies) -> None`;
  - route callback validates `route.request.url`;
  - `route.continue_()` for allowed URLs;
  - `route.abort()` for disallowed URLs.
- [x] Install the route before `page.goto()`.
- [x] Apply the same policy to document, redirect follow-up, script, image, stylesheet, XHR/fetch, font, and other request types.
- [x] Treat blocked subresources as aborted requests, not immediate whole-page failures, unless Playwright fails the main navigation.
- [x] If the main document redirects to an unsafe target, the final URL validation should fail the fetch result.
- [x] Use lazy logging formatting if adding debug logs; log only URL host/code or policy code, not page content.

### 7.5 Internal boundary consistency

- [x] Confirm `docker-compose.yml` keeps vLLM, SearXNG, and web-search MCP host-published ports bound to `127.0.0.1`.
- [x] Confirm chat-proxy remains the documented public API boundary.
- [x] Confirm web-search MCP `WEB_SEARCH_MCP_ALLOWED_HOSTS` defaults remain compatible with Compose and local debug.
- [x] Update README, architecture, production/reference deployment docs, and smoke docs to describe native optional API key auth.
- [x] Do not add a gateway, reverse proxy, Kubernetes, service mesh, or tenant model.

### 7.6 Tests

- [x] Add HTTP auth tests using `httpx.ASGITransport`:
  - auth disabled: `/v1/models` and `/v1/chat/completions` retain current behavior;
  - auth enabled: missing header returns `401`;
  - auth enabled: wrong scheme returns `401`;
  - auth enabled: wrong token returns `401`;
  - auth enabled: correct Bearer token succeeds;
  - `/health` succeeds without auth.
- [x] Extend fetch operation tests:
  - final URL redirect to public URL succeeds;
  - final URL redirect to private/loopback URL returns `PRIVATE_NETWORK_FORBIDDEN`;
  - route callback aborts unsafe subresource URLs;
  - route callback continues public subresource URLs.
- [x] Keep existing DNS-patched URL validation tests and add cases only for missing categories if needed.

### 7.7 Documentation

- [x] Update `.env.example` with commented optional chat-proxy security settings.
- [x] Update `README.md` quick start/API section to say native API key auth is available but disabled by default.
- [x] Update `docs/ARCHITECTURE.md` public/internal boundary and authentication section.
- [x] Update `docs/PRODUCTION.md` client auth table and boundary guidance.
- [x] Update `tests/smoke/README.md` and smoke helper behavior if authenticated smoke runs should pass `OPENAI_API_KEY` as the Bearer token.
- [x] Keep wording precise: this is a simple self-hosted API key, not user auth or SaaS IAM.

---

## 8. Affected files

| Path | Planned purpose |
|------|-----------------|
| `src/core/settings.py` | Add optional API key setting. |
| `src/core/openai_errors.py` | Reuse existing payload helper; optionally add a small unauthorized response helper if it reduces duplication. |
| `src/adapters/http_api.py` | Enforce optional auth while preserving route behavior. |
| `src/web_search/core/fetch_url_validation.py` | Reuse as policy source; add helper functions only if needed for route callback ergonomics. |
| `src/web_search/operations/fetch_page_html.py` | Validate final URL and install Playwright route policy before navigation. |
| `src/web_search/operations/fetch_page_markdown.py` | Pass policies through to shared HTML load. |
| `src/web_search/adapters/playwright_pool.py` | Touch only if route setup belongs better at page acquisition; otherwise leave unchanged. |
| `src/web_search/mcp_servers/` | Review boundary settings; likely no runtime changes beyond compatibility if fetch signatures change. |
| `tests/test_http_auth.py` *(new)* | Focused chat-proxy auth and health behavior tests. |
| `tests/web_search/test_operations/test_fetch_pages.py` | Final URL and Playwright route policy regression tests. |
| `tests/web_search/test_fetch_url_validation.py` | Additional SSRF policy category tests if gaps are found. |
| `.env.example` | Document optional security env vars. |
| `README.md` | Public API auth posture. |
| `docs/ARCHITECTURE.md` | Boundary, auth, and SSRF posture. |
| `docs/PRODUCTION.md` | Reference deployment security guidance. |
| `tests/smoke/README.md` | Auth-aware smoke guidance. |

No other Docker topology changes were made. `docker-compose.yml` was updated in follow-up to pass `CHAT_PROXY_API_KEY` and wire Open WebUI `OPENAI_API_KEY` from it when set.

---

## 9. Test strategy

### Unit and integration tests

- Use ASGI in-process HTTP tests for chat-proxy auth to avoid requiring vLLM.
- Use fake inference/chat service objects, matching the existing `tests/test_http_stream_context.py` pattern.
- Use DNS patching and mocked Playwright page/route objects for SSRF tests; do not rely on live network targets.
- Test both HTML and markdown behavior indirectly by verifying markdown propagates HTML fetch failures.

### Regression focus

| Risk | Regression coverage |
|------|---------------------|
| Auth accidentally blocks health checks | `/health` without auth returns `200`. |
| Auth breaks local default workflow | Empty `CHAT_PROXY_API_KEY` means protected endpoints still work without headers. |
| Wrong error shape breaks clients | Unauthorized responses use OpenAI-style JSON. |
| Token leaks into logs | No tests required unless logging is touched; review code paths. |
| Redirect SSRF | Final URL validation rejects private/loopback redirected targets. |
| Subresource SSRF | Route callback aborts unsafe subresource requests and continues public ones. |
| Public web fetch regression | Existing mocked success tests still pass with public final URLs. |

---

## 10. Validation commands

Run focused tests first:

```bash
uv run pytest \
  tests/test_http_auth.py \
  tests/web_search/test_fetch_url_validation.py \
  tests/web_search/test_operations/test_fetch_pages.py
```

Run the existing broader test suite:

```bash
uv run pytest
```

Run static checks:

```bash
uv run ruff check .
uv run basedpyright
```

Optional stack validation after implementation:

```bash
docker compose config
```

Authenticated smoke validation, if `CHAT_PROXY_API_KEY` is set:

```bash
OPENAI_API_KEY="${CHAT_PROXY_API_KEY}" tests/smoke/run_proxy_contract_smoke.sh
```

Unauthenticated smoke validation should still work when `CHAT_PROXY_API_KEY` is unset or empty.

---

## 11. Completion criteria

1. `CHAT_PROXY_API_KEY` enables optional static Bearer authentication for `/v1/models` and `/v1/chat/completions`.
2. Empty or unset `CHAT_PROXY_API_KEY` preserves current unauthenticated local behavior.
3. `/health` remains unauthenticated and compatible with existing health checks.
4. Unauthorized requests return HTTP `401` with OpenAI-style JSON.
5. Initial fetch URL validation remains in place.
6. Final Playwright URL after redirects is validated before content is returned.
7. Playwright subresource requests to unsafe targets are aborted.
8. Public HTTP/HTTPS page fetch behavior remains intact.
9. vLLM, SearXNG, and web-search MCP remain internal by default in Compose host exposure.
10. New security behavior has focused regression tests.
11. Current-facing documentation and `.env.example` accurately describe the optional self-hosted API key and SSRF posture.
12. No SaaS concepts or enterprise infrastructure are introduced.

---

## 12. Risks and trade-offs

- Static API keys are intentionally simple. They are suitable for a self-hosted reference implementation but do not provide user identity, audit attribution, rotation workflows, or per-client authorization.
- Enabling auth on `/v1/models` may require SDK/client configuration updates; documenting `OPENAI_API_KEY` alignment should reduce friction.
- Playwright subresource validation may add DNS lookups per request. This is acceptable for a bounded self-hosted fetch tool but should be tested for obvious latency regressions.
- Some public websites load assets from hosts with unusual DNS behavior. The policy should fail closed for unsafe targets but avoid blocking normal public CDNs.
- DNS rebinding cannot be eliminated entirely at application level; validating initial URL, final URL, and each browser request materially reduces the risk.
- Aborting unsafe subresources may make some pages render less completely. This is preferable to allowing browser-side SSRF.
- Deferring request/body limits keeps this wave smaller, but leaves a useful API-hardening follow-up for Plan 09.
- Keeping Docker topology unchanged preserves operational simplicity, but operators still need firewall/reverse-proxy judgment for internet-exposed deployments.

---

## 13. Expected engineering impact

Plan 08 turns the documented public boundary into an enforceable optional boundary, closes the highest-value SSRF gaps in browser-backed fetch, and adds regression tests around security-sensitive behavior. The platform remains simple to run locally, still reads as a self-hosted reference implementation, and avoids drifting into SaaS infrastructure or enterprise identity scope.
