# Plan 09 - API contract and request validation

**Status:** Planned.
**Goal:** Make the implemented OpenAI Chat Completions-compatible surface predictable, well-validated, and easier to use from SDK clients without attempting full OpenAI API parity.

**Scope:** API contract hardening for `POST /v1/chat/completions`: malformed JSON handling, lightweight request validation, consistent OpenAI-style errors, safer upstream vLLM error propagation, web-search synthetic response polish, focused regression tests, and minimal documentation updates.

**References:** [src/adapters/http_api.py](../../src/adapters/http_api.py), [src/operations/chat_completion.py](../../src/operations/chat_completion.py), [src/adapters/vllm_inference.py](../../src/adapters/vllm_inference.py), [src/core/openai_errors.py](../../src/core/openai_errors.py), [src/core/settings.py](../../src/core/settings.py), [src/operations/web_search_pipeline.py](../../src/operations/web_search_pipeline.py), [tests/test_chat_completion_validation.py](../../tests/test_chat_completion_validation.py), [tests/test_http_auth.py](../../tests/test_http_auth.py), [tests/test_http_stream_context.py](../../tests/test_http_stream_context.py), [tests/test_streaming.py](../../tests/test_streaming.py), [tests/smoke/](../../tests/smoke/), [examples/python/](../../examples/python/).

---

## 1. Objective

Improve API request validation and compatibility behavior for the chat-proxy OpenAI Chat Completions-compatible backend.

The target outcome is a small, production-minded contract layer that:

- returns clear OpenAI-style errors for malformed or invalid requests;
- validates only high-value fields that the proxy must understand before routing;
- avoids rejecting reasonable OpenAI SDK payloads that should pass through to vLLM;
- preserves useful OpenAI-shaped upstream vLLM errors when safe;
- makes hosted `web_search` synthetic JSON responses look more like normal chat completions;
- adds focused tests that do not require live vLLM.

This plan should improve predictability without turning the project into a full OpenAI schema clone.

---

## 2. Motivation

Plans 07 and 08 clarified chat-proxy as the public API boundary and added security improvements. The next reliability gap is API contract behavior at that boundary.

At plan time, invalid requests can fail inconsistently:

- malformed JSON is parsed directly with `await request.json()` in the route and can surface as a framework/internal error instead of an OpenAI-style payload;
- `stream` is coerced with `bool(body.get("stream"))`, so non-boolean truthy values can accidentally enter the streaming path;
- validation mostly happens inside `ChatCompletionService`, after route-level branching has already made decisions;
- vLLM HTTP errors are collapsed into generic `InferenceError` messages, losing useful upstream OpenAI-shaped error payloads;
- non-stream `web_search` builds a synthetic completion with a fixed id and no `created` timestamp.

These issues make SDK-client behavior less predictable and make failures harder to diagnose. The fixes are small enough to handle incrementally and should not require a large routing rewrite.

---

## 3. Current State Summary

Captured at plan time before implementation.

### Facts verified from the codebase

| Area | Current state |
|------|---------------|
| HTTP routes | `create_app()` in `src/adapters/http_api.py` exposes `GET /health`, `GET /v1/models`, `POST /v1/chat/completions`, and a `/v1/{path:path}` fallback. |
| Request parsing | `POST /v1/chat/completions` calls `await request.json()` directly, then checks only that the parsed body is a dict. |
| Auth | Optional static API key auth already protects `/v1/models` and `/v1/chat/completions` when `CHAT_PROXY_API_KEY` is set. |
| Request id/logging | `_handle_chat_completion()` creates a request id, logs request start/end, and wraps streaming cleanup. |
| Stream branch | `_handle_chat_completion()` currently uses `is_stream = bool(body.get("stream"))` before dispatching JSON versus SSE. |
| Service validation | `_validate_request()` in `src/operations/chat_completion.py` validates `tools` as list, `messages` as list, rejects reasoning fields inside input messages, rejects mixed system/function tools, and rejects `reasoning.enabled` with tools. |
| Tool routing | Function tools pass through to vLLM; system tools route to proxy-owned handlers, currently `web_search`. |
| Error helpers | `src/core/openai_errors.py` centralizes `openai_error_payload()`, auth responses, validation responses, and app error handling. |
| App errors | `ValidationError` maps to HTTP `400`; non-validation `AppError` maps to HTTP `502` with a generic server error type. |
| vLLM adapter | `src/adapters/vllm_inference.py` uses sync and async `httpx` clients; `resp.raise_for_status()` failures become generic `InferenceError` values. |
| Settings | `ChatProxySettings` contains proxy bind settings, vLLM URL/timeouts, default model, web-search MCP URL, MCP timeout, optional API key, and logging settings. |
| Web search JSON response | `WebSearchOrchestrator._build_response()` returns `id: "chatcmpl-websearch"`, `object: "chat.completion"`, `model`, and one `choices` entry; it does not set `created` or `usage`. |
| Existing HTTP tests | ASGI tests cover auth and stream request context cleanup. There is no dedicated HTTP contract test file for malformed JSON and invalid schema responses. |
| Existing service tests | `tests/test_chat_completion_validation.py` covers stream misuse, conflicting tools/reasoning, missing web-search location, and passthrough behavior. |
| Smoke tests | `tests/smoke/run_proxy_contract_smoke.sh` exercises models, plain chat, streaming, function calling, web search, and vision against a running stack. |
| SDK examples | `examples/python/` uses the OpenAI SDK with `base_url()` pointed at chat-proxy and `OPENAI_API_KEY` as the SDK key. |

### Hypotheses to verify during implementation

- Starlette/FastAPI malformed JSON failures can be handled cleanly with a small route-level helper around `request.json()` and `json.JSONDecodeError` or `ValueError`.
- vLLM error responses often include OpenAI-style `{"error": {...}}` JSON that can be safely propagated when the shape is validated.
- `usage: None` in web-search synthetic responses is more SDK-friendly than omitting `usage`, but this should be verified against the OpenAI Python SDK objects used in `examples/python/`.

---

## 4. Scope

### In scope

- Handle malformed JSON for `POST /v1/chat/completions` with HTTP `400` and OpenAI-style JSON.
- Keep non-object JSON handling as HTTP `400`, but make the error payload consistent with other validation failures.
- Add lightweight schema validation for fields the proxy must understand:
  - request body must be a JSON object;
  - `model`, when present, must be a non-empty string;
  - `messages` must be present and must be a list;
  - each message must be an object;
  - message `role` should be checked against practical supported roles;
  - message `content` should accept forms already supported by the implementation;
  - `stream`, when present, must be boolean;
  - `tools`, when present, must be a list;
  - tool/function shape should be minimally validated where it prevents confusing proxy behavior.
- Preserve pass-through behavior for extra fields such as sampling parameters, `tool_choice`, `parallel_tool_calls`, `stream_options`, response-format fields, and vLLM-specific fields unless the proxy directly depends on them.
- Return consistent OpenAI-style validation errors and avoid leaking internal exception details.
- Preserve upstream OpenAI-shaped vLLM errors when the upstream response is JSON and safe to expose.
- Keep a generic safe fallback for non-OpenAI upstream failures.
- Polish non-stream web-search synthetic response compatibility:
  - unique response id;
  - `created` timestamp;
  - consistent `object`;
  - compatible `choices` shape;
  - consistent `usage` handling, either omitted everywhere or set to `None`;
  - no accurate token accounting.
- Add focused regression tests that do not require live vLLM.
- Update docs/examples only where behavior or compatibility wording changes.

### Scope guardrails

- Prefer small helpers over framework-heavy schema systems.
- Keep validation close to the chat completions route/service boundary.
- Do not introduce Pydantic request models for the full OpenAI API surface.
- Do not reject unknown fields that can be passed through to vLLM.
- Do not change authentication behavior from Plan 08.
- Do not change Docker topology.
- Do not add request body size limits. They were intentionally deferred from Plan 08 and remain outside Plan 09 unless a tiny helper becomes unavoidable while touching JSON parsing.

---

## 5. Non-goals

- `/v1/responses`.
- Assistants API.
- Images API.
- Files API.
- Full OpenAI schema parity.
- Accurate token accounting.
- Rate limiting.
- Request body size limits.
- `CHAT_PROXY_MAX_REQUEST_BYTES`.
- HTTP `413` oversized-body behavior.
- User accounts.
- Tenants.
- API gateway.
- OAuth.
- Kubernetes.
- Service mesh.
- Replacing FastAPI, vLLM, OpenAI SDK usage, MCP, or SearXNG.
- Rewriting the chat routing architecture.
- Validating every possible message content part supported by OpenAI.
- Validating every JSON Schema detail inside function tool parameters.

---

## 6. API Contract Decisions

| Topic | Decision |
|-------|----------|
| Compatibility target | OpenAI Chat Completions-compatible behavior for implemented routes, not full OpenAI Platform parity. |
| Validation style | Lightweight explicit validation using typed helper functions and `ValidationError`; no full schema clone. |
| Validation location | Parse JSON and validate route-critical fields before choosing stream versus non-stream; keep mode-conflict validation in `ChatCompletionService` unless duplication becomes necessary. |
| Malformed JSON | Return HTTP `400` with OpenAI-style `{"error": ...}` and a safe message such as `Malformed JSON request body`. |
| Non-object body | Return HTTP `400` with `Request body must be a JSON object`. |
| Missing messages | Return HTTP `400`, `param: "messages"`, and a clear message that `messages` is required and must be an array. |
| Message item shape | Reject non-object message entries with `param` such as `messages[0]`. |
| Message roles | Accept practical roles used by current flows: `system`, `user`, `assistant`, and `tool`; consider `developer` only if the current vLLM/chat template path accepts it safely. |
| Message content | Accept `str`, `None` where assistant/tool-call flows need it, and list content parts for existing multimodal examples; minimally reject unsupported primitive types that are likely client mistakes. |
| Model | Do not require `model` globally because some internal/default-model paths exist; if provided, require a non-empty string. |
| Stream | Require `stream` to be boolean when present. This prevents accidental SSE routing from strings such as `"false"`. |
| Tools | Require `tools` to be a list when present; reject non-object tool entries. |
| Function tools | For `{"type": "function"}`, require `function` to be an object and `function.name` to be a non-empty string. Leave `parameters` mostly pass-through, requiring object only when present. |
| System tools | For non-function proxy-owned tools, keep existing routing checks. Validate `web_search.user_location` in the existing service path or move to the shared helper only if it simplifies errors. |
| Unknown fields | Pass through by default. vLLM remains responsible for model/backend-specific contract details. |
| Error payload | Use `openai_error_payload()` / `validation_response()` and include `param` where it materially helps clients. |
| Internal details | Do not expose tracebacks, internal URLs, Python exception strings, or raw `httpx` error messages in client-facing fallback errors. |
| Upstream OpenAI-shaped errors | If vLLM returns JSON with a top-level `error` object containing safe scalar fields, preserve that payload and HTTP status where practical. |
| Upstream non-OpenAI errors | Return a generic `502` OpenAI-style error with a safe message such as `Upstream inference request failed`. |
| Streaming upstream errors | Preserve OpenAI-shaped errors that happen before the SSE response starts. Mid-stream upstream failures should continue to fail safely; do not invent synthetic partial error events in this plan. |
| Web-search ids | Generate a unique `chatcmpl-...` id for each synthetic non-stream web-search response. |
| Web-search created | Add integer Unix `created` timestamp to synthetic non-stream web-search responses. |
| Web-search usage | Prefer `usage: None` if SDK compatibility checks pass; otherwise omit consistently. Do not estimate tokens. |

---

## 7. Implementation Steps

### 7.1 Route-level JSON parsing

- [ ] Add a small helper in `src/adapters/http_api.py`, for example `_parse_json_object(request: Request) -> dict[str, Any] | JSONResponse`.
- [ ] Catch malformed JSON exceptions from `request.json()` and return HTTP `400` with an OpenAI-style error payload.
- [ ] Keep non-object JSON handling in the same helper so malformed JSON and wrong top-level shape are handled consistently.
- [ ] Do not add request body size checks.

### 7.2 Lightweight chat completion validation

- [ ] Add a focused validation helper, either in `src/operations/chat_completion.py` or a small new module such as `src/core/chat_completion_contract.py`.
- [ ] Validate route-critical fields before `_handle_chat_completion()` calculates `is_stream`.
- [ ] Validate `model`, `messages`, message item shape, practical roles, supported content forms, `stream`, `tools`, and minimal function-tool shape.
- [ ] Keep existing conflict checks for mixed function/system tools and `reasoning.enabled` with tools.
- [ ] Avoid rejecting unknown request fields.
- [ ] Use `ValidationError` with clear `param` values for client-fixable fields.

### 7.3 OpenAI-style error consistency

- [ ] Reuse `openai_error_payload()` and `validation_response()` for all validation failures.
- [ ] If needed, extend `openai_error_payload()` to support explicit error `type` without breaking current callers.
- [ ] Ensure malformed JSON, non-object JSON, invalid schema, unsupported tool mixes, and auth failures all return a top-level `error` object.
- [ ] Keep validation failures at HTTP `400`.
- [ ] Avoid exposing internal exception text in non-validation errors.

### 7.4 Upstream vLLM error propagation

- [ ] Introduce a small upstream error representation, for example an `InferenceError` that can carry `status_code` and an optional safe OpenAI-style payload, or a new narrow error class if cleaner.
- [ ] In `VllmInferenceAdapter`, inspect `httpx.HTTPStatusError.response` before raising.
- [ ] If the response JSON has a top-level `error` object with safe scalar fields, preserve the payload and upstream status code.
- [ ] If JSON parsing fails or the shape is not OpenAI-style, raise a generic inference error without backend internals.
- [ ] Update `app_error_handler()` to honor the carried status/payload for safe upstream errors.
- [ ] Keep logging detailed enough for operators through existing `log_upstream_error()` while keeping client-facing messages safe.
- [ ] Apply the same policy to `list_models()`, non-stream `chat_completion()`, and stream startup failures where practical.

### 7.5 Web-search synthetic response polish

- [ ] Update `WebSearchOrchestrator._build_response()` to create a unique id, for example `chatcmpl-` plus a URL-safe random token.
- [ ] Add `created: int(time.time())`.
- [ ] Keep `object: "chat.completion"`.
- [ ] Preserve the existing `choices[0].index`, `choices[0].message`, and `choices[0].finish_reason` shape.
- [ ] Decide and test `usage` consistency. Prefer `usage: None` if SDK parsing and examples remain clean.
- [ ] Do not attempt token accounting.
- [ ] Do not change streaming web-search SSE behavior except where tests expose a direct compatibility issue.

### 7.6 Focused regression tests

- [ ] Add HTTP contract tests, likely `tests/test_http_api_contract.py`, using `httpx.ASGITransport` and fake inference.
- [ ] Cover malformed JSON with raw `content` and `Content-Type: application/json`.
- [ ] Cover non-object JSON bodies such as arrays and strings.
- [ ] Cover missing `messages`, non-list `messages`, and non-object message entries.
- [ ] Cover invalid `model` values.
- [ ] Cover invalid `stream` values and assert they do not enter the SSE branch.
- [ ] Cover invalid `tools` and invalid function tool shape.
- [ ] Add vLLM adapter tests with `httpx.MockTransport` or a small fake transport so live vLLM is not required.
- [ ] Cover upstream OpenAI-shaped error propagation.
- [ ] Cover upstream non-OpenAI error fallback.
- [ ] Add web-search response builder tests for unique id, `created`, `object`, `choices`, and `usage` decision.
- [ ] Keep existing service-level routing tests and extend only where route-level validation changes responsibilities.

### 7.7 Smoke and examples review

- [ ] Review smoke scripts to confirm they still validate the intended successful contract and do not need live negative tests.
- [ ] Add a smoke negative-contract check only if it stays fast and does not require vLLM, otherwise keep negative coverage in unit/ASGI tests.
- [ ] Review OpenAI SDK examples for any behavior affected by `usage: None` or validation wording.
- [ ] Update examples only if new compatibility wording or response fields should be documented.

### 7.8 Documentation

- [ ] Update `README.md`, `docs/ARCHITECTURE.md`, `docs/PRODUCTION.md`, `examples/python/README.md`, or `tests/smoke/README.md` only if API behavior or compatibility wording changes.
- [ ] Document that the project implements a practical Chat Completions-compatible subset, not full schema parity.
- [ ] Mention that validation intentionally permits unknown fields for vLLM pass-through.
- [ ] Do not add documentation for request body size limits.

---

## 8. Affected Files

| Path | Planned purpose |
|------|-----------------|
| `src/adapters/http_api.py` | Add safe JSON parsing and run lightweight contract validation before stream/non-stream branching. |
| `src/operations/chat_completion.py` | Extend or reuse request validation helpers; keep routing conflict validation close to service logic. |
| `src/core/openai_errors.py` | Reuse and possibly extend OpenAI-style error helpers for consistent validation and upstream payloads. |
| `src/core/errors.py` | Optionally carry safe upstream HTTP status/payload details on inference errors. |
| `src/adapters/vllm_inference.py` | Preserve safe upstream OpenAI-shaped errors and fall back to generic errors for unsafe/non-JSON failures. |
| `src/core/settings.py` | Review only; no planned setting is required for Plan 09. |
| `src/operations/web_search_pipeline.py` | Add unique id, `created`, and consistent `usage` handling to synthetic non-stream responses. |
| `tests/test_http_api_contract.py` *(new)* | Focused ASGI tests for malformed JSON and request schema validation. |
| `tests/test_chat_completion_validation.py` | Keep or adjust service-level validation tests as responsibilities are clarified. |
| `tests/test_http_auth.py` | Ensure auth behavior remains compatible with new parse/validation helpers. |
| `tests/test_http_stream_context.py` | Ensure stream request context behavior still passes after stream validation changes. |
| `tests/test_streaming.py` | Extend only if stream validation or upstream stream startup handling changes. |
| `tests/test_vllm_inference.py` *(new, optional)* | Adapter-level upstream error propagation tests with mocked HTTP transport. |
| `tests/test_web_search_response_contract.py` *(new, optional)* | Synthetic web-search response field tests. |
| `tests/smoke/` | Review; update only if contract wording or smoke expectations change. |
| `examples/python/` | Review; update only if SDK-visible behavior or docs change. |
| `README.md` / `docs/ARCHITECTURE.md` / `docs/PRODUCTION.md` | Minimal wording updates only if needed. |

---

## 9. Test Strategy

### Unit and ASGI tests

- Use in-process ASGI tests for HTTP contract behavior so validation failures do not require vLLM.
- Use fake inference objects for successful route dispatch and to assert invalid requests do not reach inference.
- Use raw request bodies for malformed JSON tests instead of `json=`.
- Assert HTTP status, top-level `error`, `error.message`, `error.type`, `error.code`, and `error.param` where applicable.
- Verify invalid `stream` values return JSON `400` instead of `text/event-stream`.

### Adapter tests

- Use `httpx.MockTransport` or monkeypatched clients for `VllmInferenceAdapter`.
- Test OpenAI-shaped upstream errors, for example:
  - upstream status `400`;
  - body `{"error": {"message": "...", "type": "invalid_request_error", "code": "...", "param": "model"}}`;
  - downstream preserves status and safe payload.
- Test non-JSON or unexpected upstream errors return generic safe payloads.
- Test no live vLLM is required.

### Web-search response tests

- Test `_build_response()` directly or through a narrow orchestrator path with fake dependencies.
- Assert response ids are unique across calls.
- Assert `created` is an integer timestamp.
- Assert `object == "chat.completion"`.
- Assert `choices[0].message.role == "assistant"`, content is preserved, annotations are included only when present, and `finish_reason == "stop"`.
- Assert the selected `usage` policy is stable.

### Regression focus

| Risk | Regression coverage |
|------|---------------------|
| Malformed JSON leaks framework errors | Raw malformed body returns OpenAI-style `400`. |
| Non-object JSON reaches service logic | Array/string/null JSON returns OpenAI-style `400`. |
| String stream flag accidentally triggers SSE | `"stream": "false"` returns JSON `400`. |
| Invalid tools are silently filtered | Non-object tool entries and malformed function tools return clear validation errors. |
| Unknown pass-through fields break | A request with extra vLLM/OpenAI fields still reaches fake inference unchanged. |
| Upstream useful errors are lost | OpenAI-shaped vLLM errors are preserved. |
| Upstream internals leak | Non-OpenAI upstream failures return generic safe errors. |
| Web-search synthetic responses are hard to parse | Response id, created, choices, object, and usage policy are covered. |
| Auth regresses | Existing auth tests continue passing. |
| Streaming cleanup regresses | Existing stream context and streaming tests continue passing. |

---

## 10. Validation Commands

Run the focused suite first:

```bash
uv run pytest tests/test_http_api_contract.py tests/test_chat_completion_validation.py tests/test_http_auth.py tests/test_http_stream_context.py tests/test_streaming.py
```

If adapter/web-search contract tests are added as separate files:

```bash
uv run pytest tests/test_vllm_inference.py tests/test_web_search_response_contract.py
```

Run lint and type checks:

```bash
uv run ruff check src tests examples
uv run basedpyright
```

Run the full test suite before completion:

```bash
uv run pytest
```

Optional live-stack smoke validation:

```bash
./tests/smoke/run_proxy_contract_smoke.sh
```

The smoke suite requires the stack to be running and healthy. Unit and ASGI tests must not require live vLLM.

---

## 11. Completion Criteria

- Malformed JSON returns HTTP `400` with an OpenAI-style error payload.
- Non-object JSON returns HTTP `400` with an OpenAI-style error payload.
- Missing or invalid `messages`, invalid `model`, invalid `stream`, invalid `tools`, and invalid function tool shape return clear validation errors.
- Unknown pass-through fields still reach vLLM/fake inference unless they conflict with proxy-owned behavior.
- `stream` must be boolean when present, and invalid stream values do not produce SSE responses.
- Existing auth behavior remains unchanged.
- Existing plain chat, streaming, function calling, reasoning, vision, and web-search flows continue to work.
- Upstream OpenAI-shaped vLLM errors are preserved when safe.
- Non-OpenAI upstream errors return a generic safe fallback.
- Non-stream web-search synthetic responses include unique ids, `created`, stable `object`, compatible `choices`, and a documented/tested `usage` policy.
- Focused tests pass without live vLLM.
- Full `uv run pytest`, `uv run ruff check src tests examples`, and `uv run basedpyright` pass.
- Documentation/examples are updated only where behavior or compatibility wording changed.
- No request body size limit feature is introduced.

---

## 12. Risks and Trade-offs

| Risk / trade-off | Mitigation |
|------------------|------------|
| Over-validation breaks SDK clients or vLLM-specific options | Validate only fields the proxy needs for routing and safety; pass unknown fields through. |
| Under-validation leaves confusing errors to vLLM | Validate common client mistakes early: body shape, messages, stream, model, tools, and function tool basics. |
| Role validation rejects a role vLLM could handle | Start with roles used by current examples and flows; add `developer` only after verifying backend compatibility. |
| Content validation becomes a partial OpenAI schema clone | Accept broad supported forms and reject only clearly unsupported shapes. |
| Upstream error propagation leaks backend details | Preserve only validated OpenAI-shaped payloads; otherwise use a generic fallback while logging operator details. |
| Stream errors after response start cannot become normal JSON errors | Limit Plan 09 to pre-stream/startup error propagation; document that mid-stream failures remain transport-level failures. |
| `usage: None` may not match every client expectation | Test with current OpenAI SDK examples; omit `usage` consistently if `None` causes practical issues. |
| Moving validation changes logging order | Keep request id and validation logging behavior intentional; ensure validation errors are still logged through existing handlers. |
| Additional helper modules add indirection | Prefer one small helper module only if it keeps `http_api.py` and `chat_completion.py` simpler. |

Operationally, the main failure mode to avoid is rejecting valid client requests before vLLM sees them. The plan therefore favors incremental validation and regression tests over a comprehensive schema rewrite.

---

## 13. Expected Engineering Impact

Plan 09 should make chat-proxy easier to operate and easier to integrate with SDK clients:

- client mistakes fail quickly with predictable OpenAI-style errors;
- operators get safer upstream error behavior without exposing backend internals;
- route decisions no longer depend on Python truthiness for contract-critical fields;
- web-search synthetic responses become closer to normal chat completions;
- tests define the implemented contract clearly without requiring a live model server;
- the repository remains a simple, maintainable self-hosted AI platform reference implementation rather than expanding into full API gateway or OpenAI Platform clone territory.

