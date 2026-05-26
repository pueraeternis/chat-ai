# Progress

**Active plan:** [plans/02-chat-proxy-api.md](plans/02-chat-proxy-api.md)

**Summary:** Plan 02 implemented in code: **chat-proxy** (FastAPI), embedded **web-search** (`src/web_search/`), Compose stack (vLLM, SearXNG, web-search-mcp, chat-proxy, Open WebUI). Unit tests pass (`uv run pytest`). Full stack smoke requires GPU + `docker compose up`.

---

## Journal

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
