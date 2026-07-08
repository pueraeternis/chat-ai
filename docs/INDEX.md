# Documentation index

Navigation map for the **chat-ai** repository. Read this first at session start (see `.cursor/rules/05-workflow.mdc`).

## Documentation (`docs/`)

| Path | Purpose |
|------|---------|
| `docs/INDEX.md` | This file — project file map and entry points |
| `docs/ARCHITECTURE.md` | Current architecture: chat-proxy public API, internal vLLM/MCP/SearXNG, compatibility boundary, deployment profiles |
| `docs/DECISIONS.md` | Chronological architectural decision journal |
| `docs/PROGRESS.md` | Active plan pointer + archived wave journal |
| `docs/PRODUCTION.md` | Reference deployment: capacity planning, configurable ops, OWUI setup |
| `docs/plans/01-vllm-migration.md` | Completed: Triton → native vLLM |
| `docs/plans/02-chat-proxy-api.md` | Completed: OpenAI chat proxy, web_search, reasoning, web-search embed |
| `docs/plans/03-streaming.md` | Completed: SSE streaming, OWUI status/citations for web_search |
| `docs/plans/04-open-webui-web-search-filter.md` | Completed: OWUI Filter injects proxy `web_search` for UI |
| `docs/plans/05-chat-proxy-logging.md` | Completed: structured logging, web_search pipeline visibility |
| `docs/plans/06-web-search-temporal-grounding.md` | Completed: English system prompt + current date on web_search final LLM |
| `docs/plans/07-public-reference-documentation.md` | Completed: public reference documentation alignment |
| `docs/images/README.md` | Screenshot index (snake_case PNGs for GitHub README) |
| `docs/images/open_webui_web_search.png` | UI: proxy web search + citations |
| `docs/images/open_webui_plain_chat.png` | UI: plain chat |
| `docs/images/open_webui_document_chat.png` | UI: document upload chat |
| `docs/images/open_webui_url_chat.png` | UI: URL summary chat |
| `docs/images/multimodal_sample_image.png` | Vision smoke sample image |

## Runtime / deployment (root)

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Stack: vLLM, chat-proxy, web-search-mcp, SearXNG, Open WebUI |
| `Dockerfile.chat-proxy` | chat-proxy image |
| `Dockerfile.web-search-mcp` | web-search MCP HTTP + Playwright |
| `.env.example` | Template for Compose, smoke, local proxy (copy to `.env`) |
| `.env` | Local env (gitignored): HF cache, ports, secrets |
| `.python-version` | Python 3.12 for `uv` |
| `pyproject.toml` | Dependencies (FastAPI, MCP, Playwright, …) |
| `README.md` | Reference implementation overview, local quick start, deployment profiles |

## Client examples (`examples/python/`)

| Path | Purpose |
|------|---------|
| `examples/python/README.md` | Setup, env vars, script index |
| `examples/python/01_list_models.py` … `07_reasoning.py` | Minimal OpenAI SDK clients for chat-proxy |

## Smoke tests (`tests/smoke/`)

| Path | Purpose |
|------|---------|
| `tests/smoke/README.md` | Smoke index, env vars, expected response shapes |
| `tests/smoke/run_proxy_contract_smoke.sh` | Run all proxy contract checks |
| `tests/smoke/check_proxy_plain_chat.sh` | Plain chat via proxy |
| `tests/smoke/check_proxy_function_calling.sh` | Client `function` tool_calls |
| `tests/smoke/check_proxy_web_search.sh` | System `web_search` + annotations |
| `tests/smoke/check_proxy_vision.sh` | Multimodal `image_url` (`tests/test_image.jpg`) |
| `tests/smoke/check_vllm_models.sh` | `GET /v1/models` on vLLM (direct, optional debug) |
| `tests/smoke/check_vllm_tool_calls.sh` | vLLM function `tool_calls` (direct, optional debug) |
| `tests/smoke/check_proxy_models.sh` | Proxy `GET /v1/models` |

Requires running stack (`docker compose up`).

## Open WebUI (`open_webui/`)

| Path | Purpose |
|------|---------|
| `open_webui/functions/proxy_web_search_filter.py` | Filter: inject `web_search` tool in `inlet` |
| `open_webui/inject_web_search.py` | Inject helper for tests |
| `open_webui/README.md` | Import filter in OWUI Admin; proxy web search setup |

## Application code (`src/`)

| Path | Purpose |
|------|---------|
| `src/adapters/http_api.py` | FastAPI: `/v1/models`, `/v1/chat/completions` |
| `src/adapters/vllm_inference.py` | vLLM HTTP (`InferencePort`; async stream) |
| `src/adapters/mcp_tool_client.py` | MCP streamable HTTP `tools/call` |
| `src/core/logging_config.py` | Log level, JSON/text formatters |
| `src/core/request_context.py` | `request_id` contextvar for correlation |
| `src/core/log_events.py` | Request mode helpers and HTTP log events |
| `src/core/web_search_logging.py` | web_search pipeline stage log events |
| `src/core/system_tool_registry.py` | Map `tools[].type` → MCP URL + orchestrator |
| `src/operations/chat_completion.py` | Mode routing and validation |
| `src/operations/web_search_pipeline.py` | Web search steps 0-5 |
| `src/operations/search_locale.py` | SearXNG `en` / `ru` from user message script |
| `src/operations/reasoning_fallback.py` | Map vLLM `reasoning` field to `reasoning_content` if present |
| `src/web_search/` | Embedded web-search (core, operations, adapters, mcp_servers) |
| `config/web_search/` | Limits, fetch policies, SearXNG settings |
| `tests/` | Proxy + web_search unit tests |

## Tooling and rules (`.cursor/rules/`)

| Path | Purpose |
|------|---------|
| `.cursor/rules/00-project-structure.mdc` | Repo layout, `docs/` conventions |
| `.cursor/rules/01-code-standards.mdc` | Python style |
| `.cursor/rules/02-architecture-standards.mdc` | Onion architecture, MCP routing |
| `.cursor/rules/03-mcp-standards.mdc` | MCP tool contracts |
| `.cursor/rules/04-testing-standards.mdc` | pytest, smoke |
| `.cursor/rules/05-workflow.mdc` | Plans, PROGRESS, DECISIONS |
| `.cursor/rules/06-git-workflow.mdc` | Git conventions |

## Git / local (ignored)

| Path | Purpose |
|------|---------|
| `.git/` | Version control |
| `.venv/` | Local virtualenv |
| `.env` | Secrets and machine paths |

## External references

- vLLM: [docs.vllm.ai](https://docs.vllm.ai/)
- Qwen thinking: [Quickstart — enable_thinking](https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html)
- Qwen function calling: [Function Calling (vLLM)](https://qwen.readthedocs.io/en/latest/framework/function_call.html)
- vLLM reasoning: [Reasoning outputs](https://docs.vllm.ai/en/latest/features/reasoning_outputs/)
- Open WebUI: [open-webui](https://github.com/open-webui/open-webui)
- Open WebUI events: [Plugin events](https://docs.openwebui.com/features/extensibility/plugin/development/events/)
