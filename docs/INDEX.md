# Documentation index

Navigation map for the **chat-ai** repository. Read this first at session start (see `.cursor/rules/05-workflow.mdc`).

## Documentation (`docs/`)

| Path | Purpose |
|------|---------|
| `docs/INDEX.md` | This file — project file map and entry points |
| `docs/ARCHITECTURE.md` | System design: vLLM + Open WebUI, tool-calling flow, env vars |
| `docs/DECISIONS.md` | Chronological architectural decision journal |
| `docs/PROGRESS.md` | Active plan pointer + archived wave journal |
| `docs/plans/01-vllm-migration.md` | Completed checklist: Triton → native vLLM |

## Runtime / deployment (root)

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Stack: vLLM inference + Open WebUI, GPU, networks, healthchecks |
| `.env` | Local env (not committed): HF cache paths, `VLLM_*`, `OPENAI_API_KEY`, RAG model |
| `.python-version` | Python 3.12 for `uv` / local tooling |
| `pyproject.toml` | Project metadata (`chat-ai`); dependencies empty until app code lands |

## Smoke tests (`tests/smoke/`)

| Path | Purpose |
|------|---------|
| `tests/smoke/check_vllm_models.sh` | `GET /v1/models` includes `qwen3-30b-instruct` |
| `tests/smoke/check_vllm_tool_calls.sh` | Chat completion with tools returns `tool_calls` |

Requires running vLLM (e.g. after `docker compose up`). Uses `VLLM_PORT` / `VLLM_BASE_URL` from the environment.

## Tooling and rules (`.cursor/rules/`)

| Path | Purpose |
|------|---------|
| `.cursor/rules/00-project-structure.mdc` | Repo layout, naming, `docs/` conventions |
| `.cursor/rules/01-code-standards.mdc` | Python style and quality |
| `.cursor/rules/02-architecture-standards.mdc` | Onion architecture, async/sync I/O, agent MCP routing |
| `.cursor/rules/03-mcp-standards.mdc` | MCP server and tool contract rules |
| `.cursor/rules/04-testing-standards.mdc` | pytest, smoke tests, coverage |
| `.cursor/rules/05-workflow.mdc` | Plans, PROGRESS, DECISIONS, session protocol |
| `.cursor/rules/06-git-workflow.mdc` | Commits, conventional messages, what not to commit |

## Planned application code (not in repo yet)

Per project structure rules; future waves will add:

| Path | Purpose |
|------|---------|
| `src/core/` | Domain types, errors |
| `src/operations/` | Use cases |
| `src/adapters/` | HTTP, GPU, external I/O |
| `src/mcp_servers/` | MCP transport and tool schemas |
| `tests/` | Unit and integration tests (beyond smoke) |

## Git / local (ignored)

| Path | Purpose |
|------|---------|
| `.git/` | Version control |
| `.venv/` | Local virtualenv (`uv`) |
| `.env` | Secrets and machine-specific paths (gitignored) |

## External references

- Model: [Qwen/Qwen3-30B-A3B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507)
- Tool calling: [Qwen — Function Calling (vLLM)](https://qwen.readthedocs.io/en/latest/framework/function_call.html)
- vLLM Docker: [Using Docker](https://docs.vllm.ai/en/latest/deployment/docker.html)
- Open WebUI: [ghcr.io/open-webui/open-webui](https://github.com/open-webui/open-webui)
