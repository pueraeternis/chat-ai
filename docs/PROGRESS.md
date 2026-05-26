# Progress

**Active plan:** [plans/02-chat-proxy-api.md](plans/02-chat-proxy-api.md)

**Summary:** Documented target architecture for an OpenAI-compatible **chat-proxy** (system `web_search`, client `function` tools, optional `reasoning`), **Qwen3-VL-30B-A3B-Instruct** on vLLM, and embedded **web-search** via **MCP HTTP** (system tool registry; proxy orchestrates, MCP servers execute). Implementation not started; vLLM + Open WebUI run without proxy (plan 01).

---

## Journal

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
