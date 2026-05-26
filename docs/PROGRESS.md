# Progress

**Active plan:** [06-web-search-temporal-grounding.md](plans/06-web-search-temporal-grounding.md) *(documentation done; implementation pending)*

**Summary:** Plan 06 — English system prompt with real date on web_search final LLM only (fix “future news” rejections).

---

## Journal

### [2026-05-26] Plan 06 — documentation (web_search temporal grounding)

- Problem: final LLM dismisses fetched sources when dates exceed training-time “today” (e.g. claims May 2025 while sources show 2026).
- Decision: proxy prepends English system prompt with `datetime` + `user_location` timezone on final answer only.
- Added `docs/plans/06-web-search-temporal-grounding.md`; DECISIONS, INDEX, ARCHITECTURE cross-ref.

### [2026-05-26] Fix — SSE `request_id` context on stream close

- **Symptom (OWUI):** long answer + sources OK, then `TransferEncodingError: Not enough data to satisfy transfer length header`; `docker logs` showed `ValueError: Token was created in a different Context` in `_stream_with_logging`.
- **Cause:** `reset_request_id` ran in Starlette’s stream task while the token was created in the route handler task (`contextvars`).
- **Fix:** `http_api` — reset handler token before returning `StreamingResponse`; bind/reset `request_id` inside the stream generator. Test: `tests/test_http_stream_context.py`.
- **Deploy:** rebuild `chat-proxy` image (`docker compose build chat-proxy && docker compose up -d chat-proxy`).

### [2026-05-26] Plan 05 — implementation (chat-proxy logging)

- `src/core/logging_config.py`, `request_context.py`, `log_events.py`, `web_search_logging.py`; settings `log_level` / `log_json`.
- `http_api`: lifespan configure + startup line; per-request `request_id`, `request_start` / `request_end`.
- `web_search_pipeline`: stage events (router, hits, filter, fetch, complete).
- `chat_completion`: `route_mode`; MCP/vLLM `upstream_error`; validation log.
- Tests `test_request_logging.py`, `test_web_search_logging.py`; `.env.example`, compose comments; ARCHITECTURE + OWUI README.

### [2026-05-26] Plan 05 — documentation (chat-proxy logging)

- Recorded decisions: stdlib logging, `request_id`, web_search stage events, privacy limits, JSON optional.
- Added `docs/plans/05-chat-proxy-logging.md` (events, checklist, acceptance).

### [2026-05-26] Plan 04 — operator verification & docs (OWUI capabilities)

- Verified: filter inject without Web Search globe; real URLs in answers; UI status/citations after enabling model **Citations** + **Status Updates**.
- Updated `open_webui/README.md`, plan 04, ARCHITECTURE, DECISIONS (OWUI v0.6.32 display gate).

### [2026-05-26] Plan 04 — implementation (OWUI web search Filter)

- `open_webui/inject_web_search.py`: inject/skip helpers and `build_web_search_tool`.
- `open_webui/functions/proxy_web_search_filter.py`: toggleable Filter `inlet` (self-contained for OWUI import).
- `open_webui/README.md`: admin setup and verify steps.
- `tests/test_owui_inject_web_search.py`; `pyproject.toml` pytest `pythonpath` includes `open_webui`.

### [2026-05-26] Web search SearXNG locale (en / ru from query script)

- Added `src/operations/search_locale.py`: Latin → `en`, Cyrillic ≥ Latin → `ru`, else `en`.
- `web_search_pipeline` uses `searxng_locale_from_messages` instead of `user_location.country` → `ru-RU`/`en-US`.
- Tests `tests/test_search_locale.py`; updated DECISIONS, ARCHITECTURE, plans 02/04, INDEX.

### [2026-05-26] Plan 04 — documentation (OWUI web search Filter)

- Recorded decisions: Filter `inlet` injects `web_search`; disable OWUI built-in Web Search; no auto-inject for all API calls.
- Added `docs/plans/04-open-webui-web-search-filter.md` (flow, valves, admin setup, checklist).
- Updated `docs/ARCHITECTURE.md` (OWUI paths table), `docs/INDEX.md`; marked plan 03 completed.

### [2026-05-26] Plan 03 — implementation (SSE streaming)

- `InferencePort.chat_completion_stream`; `VllmInferenceAdapter` async client with connect/read timeouts.
- `http_api`: `StreamingResponse` for `stream: true`; cancel upstream on client disconnect.
- Passthrough: `stream_passthrough`, reasoning delta rename in `stream_reasoning`.
- `WebSearchOrchestrator.run_stream`: status/citation SSE, then vLLM stream + optional `annotations` chunk.
- Tests: `test_sse_events.py`, `test_streaming.py`; smoke `check_proxy_stream.sh`.

### [2026-05-26] Plan 03 — documentation (streaming + Open WebUI)

- Recorded plan 03 decisions in `docs/DECISIONS.md`: async passthrough, mode matrix, `web_search` orchestrated stream, OWUI SSE `event` wrapper, disable duplicate OWUI web search.
- Added `docs/plans/03-streaming.md` (contract, OWUI format, checklist, acceptance).
- Updated `docs/ARCHITECTURE.md` (streaming section, web_search UX path).
- Updated `docs/INDEX.md`; marked plan 02 completed in `docs/plans/02-chat-proxy-api.md`.

### [2026-05-26] Plan 02 — implementation (chat-proxy + web-search embed)

- Copied web-search into `src/web_search/`, `config/web_search/`, `tests/web_search/`; imports `web_search.*`.
- Added chat-proxy: `src/core/`, `src/operations/`, `src/adapters/http_api.py` (modes, validation, vLLM adapter, MCP client, web search pipeline).
- Compose: `searxng`, `web-search-mcp`, `chat-proxy`; vLLM `qwen3-vl-30b-instruct`, `--reasoning-parser qwen3`; Open WebUI → proxy.
- `pyproject.toml` deps; `Dockerfile.chat-proxy`, `Dockerfile.web-search-mcp`; smoke `check_proxy_models.sh`; model id defaults updated.

### [2026-05-26] Plan 02 — documentation (chat-proxy API)

- Appended decisions to `docs/DECISIONS.md`: VL-Instruct model, proxy surface, tool modes, `web_search` contract, web-search embed, reasoning, vLLM parsers.
- Added `docs/plans/02-chat-proxy-api.md` (API contract, pipeline, checklist, acceptance).
- Updated `docs/ARCHITECTURE.md` (target diagram, proxy modes, vLLM/web-search).
- Updated `docs/INDEX.md` (plan 02, planned `src/` layout, external links).

### [2026-05-26] Plan 02 — docs: MCP HTTP integration bus

- Recorded decisions: system tools via **MCP HTTP** (registry, future servers); **operations** inside MCP servers, proxy orchestrates via `tools/call`; stdio/in-process not primary for proxy.
- Updated `docs/ARCHITECTURE.md` (system tool integration bus, web_search layout).
- Updated `docs/plans/02-chat-proxy-api.md` (`McpToolClient`, registry, out-of-scope).

### [2026-05-25] Plan 01 — Triton → native vLLM

- Replaced `triton` Compose service with `vllm` (`vllm/vllm-openai:v0.12.0`, Hermes tool parser).
- Updated Open WebUI `OPENAI_API_BASE_URL` and `depends_on` healthcheck.
- Migrated `.env`: `VLLM_PORT`, `VLLM_IMAGE_TAG`; removed `TRITON_*`, `COMPOSE_BAKE`.
- Removed `Dockerfile`, `requirements.txt`, `models/qwen3-30b-instruct-2507/*`.
- Added `tests/smoke/check_vllm_models.sh`, `tests/smoke/check_vllm_tool_calls.sh`.
- Updated `docs/ARCHITECTURE.md`, `docs/INDEX.md`.
- Compose model id updated to `Qwen/Qwen3-VL-30B-A3B-Instruct` (post–plan 01; served name still `qwen3-30b-instruct` until plan 02).
