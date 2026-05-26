# Documentation index

Navigation map for the **chat-ai** repository. Read this first at session start (see `.cursor/rules/05-workflow.mdc`).

## Documentation (`docs/`)

| Path | Purpose |
|------|---------|
| `docs/INDEX.md` | This file — project file map and entry points |
| `docs/ARCHITECTURE.md` | Target design: chat-proxy, vLLM (Qwen3-VL), web-search MCP, Open WebUI |
| `docs/DECISIONS.md` | Chronological architectural decision journal |
| `docs/PROGRESS.md` | Active plan pointer + archived wave journal |
| `docs/plans/01-vllm-migration.md` | Completed: Triton → native vLLM |
| `docs/plans/02-chat-proxy-api.md` | **Active:** OpenAI chat proxy, web_search, reasoning, web-search embed |

## Runtime / deployment (root)

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Stack: vLLM + Open WebUI today; + proxy, SearXNG, MCP in plan 02 |
| `.env` | Local env: HF cache, `VLLM_*`, `OPENAI_API_KEY`, RAG model |
| `.python-version` | Python 3.12 for `uv` |
| `pyproject.toml` | Project metadata; deps populated in plan 02 |

## Smoke tests (`tests/smoke/`)

| Path | Purpose |
|------|---------|
| `tests/smoke/check_vllm_models.sh` | `GET /v1/models` on vLLM |
| `tests/smoke/check_vllm_tool_calls.sh` | vLLM function `tool_calls` |

Plan 02 will add proxy smoke scripts. Requires running stack (`docker compose up`).

## Planned application code (plan 02)

| Path | Purpose |
|------|---------|
| `src/adapters/` | vLLM HTTP, MCP HTTP client, FastAPI routes |
| `src/core/system_tool_registry.py` | *(plan 02)* Map `tools[].type` → MCP server + orchestrator |
| `src/operations/` | Chat routing, web search pipeline |
| `src/core/` | Types, errors, request/response models |
| `src/web_search/` | Embedded web-search (core, operations, adapters, mcp_servers) |
| `tests/` | Unit + integration tests |

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

- Model: [Qwen/Qwen3-VL-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-30B-A3B-Instruct)
- Qwen thinking: [Quickstart — enable_thinking](https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html)
- Qwen function calling: [Function Calling (vLLM)](https://qwen.readthedocs.io/en/latest/framework/function_call.html)
- vLLM reasoning: [Reasoning outputs](https://docs.vllm.ai/en/latest/features/reasoning_outputs/)
- vLLM Qwen3-VL: [Usage guide](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3-VL.html)
- Open WebUI: [open-webui](https://github.com/open-webui/open-webui)
