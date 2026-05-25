# Plan 01 — Triton to native vLLM migration

**Status:** Completed 2026-05-25.  
**Goal:** Replace Triton inference with native vLLM OpenAI API and enable Hermes-style tool calling for `Qwen/Qwen3-30B-A3B-Instruct-2507`; keep Open WebUI.

**References:** [DECISIONS.md](../DECISIONS.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [Qwen model card](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507), [Qwen function calling](https://qwen.readthedocs.io/en/latest/framework/function_call.html).

---

## 1. Docker Compose and environment

- [x] Replace `triton` service with `vllm` service using image `vllm/vllm-openai` (pinned tag ≥ v0.12, CUDA 12.x) — `docker-compose.yml`
- [x] Configure `command`: `vllm serve Qwen/Qwen3-30B-A3B-Instruct-2507` with `--host 0.0.0.0`, `--port 8000`, `--served-model-name qwen3-30b-instruct`, `--max-model-len 32768`, `--gpu-memory-utilization 0.9`, `--enable-auto-tool-choice`, `--tool-call-parser hermes` — `docker-compose.yml`
- [x] Retain GPU reservation (`device_ids: ["0"]`), `ipc: host`, `shm_size: 8g`, HF cache bind mount — `docker-compose.yml`
- [x] Remove Triton ports 18100–18102; publish vLLM OpenAI port via `VLLM_PORT` (default host `19000` → container `8000`) — `docker-compose.yml`, `.env`
- [x] Update Open WebUI `OPENAI_API_BASE_URL` to `http://vllm:8000/v1` and `depends_on: vllm` with healthcheck — `docker-compose.yml`
- [x] Replace `TRITON_*` / `TRITON_TOKENIZER` with `VLLM_*` in `.env`; document variables in `docs/ARCHITECTURE.md`
- [x] Add vLLM healthcheck: `GET http://127.0.0.1:8000/v1/models` with adequate `start_period` (model load ~15 min) — `docker-compose.yml`

## 2. Remove Triton build artifacts

- [x] Remove or archive `Dockerfile` (Triton + vllm_backend build) — root
- [x] Remove `requirements.txt` if only used for Triton image build (verify no other consumers) — root
- [x] Remove Triton model repository files `models/qwen3-30b-instruct-2507/config.pbtxt` and `models/.../model.json` after flags live in Compose — `models/`
- [x] Update `.dockerignore` if it referenced Triton-only paths — `.dockerignore` *(no change needed)*

## 3. Smoke and tool-calling verification

- [x] Add smoke script: `GET /v1/models` returns `qwen3-30b-instruct` — `tests/smoke/`
- [x] Add smoke script: chat completion with `tools` + `tool_choice: auto` yields `tool_calls` and `finish_reason: tool_calls` — `tests/smoke/`
- [ ] Manual check: Open WebUI chat with tools/MCP against new base URL — operator checklist in `docs/ARCHITECTURE.md`

## 4. Documentation sync (post-implementation)

- [x] Update `docs/ARCHITECTURE.md` diagrams to target state only after cutover — `docs/ARCHITECTURE.md`
- [x] Update `docs/INDEX.md` for any removed/added files — `docs/INDEX.md`
- [x] Archive completed checkboxes to `docs/PROGRESS.md` journal — `docs/PROGRESS.md`

## 5. Out of scope (this plan)

- Python `src/` application layer, MCP servers, and agent orchestration (future waves).
- 1M-token context (DCA / `config_1m.json` / multi-GPU).
- Qwen-Agent deployment as a required component.
- Upgrading Open WebUI image version (stay on `v0.6.32` unless separately planned).
