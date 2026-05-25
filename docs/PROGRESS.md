# Progress

**Active plan:** *(none — plan 01 completed 2026-05-25)*

**Summary:** Inference runs on native vLLM (`vllm/vllm-openai`) with Hermes tool calling for `Qwen/Qwen3-30B-A3B-Instruct-2507`; Open WebUI points at `http://vllm:8000/v1`. Triton image build, model repository, and `TRITON_*` env vars removed.

---

## Journal

### [2026-05-25] Plan 01 — Triton → native vLLM

- Replaced `triton` Compose service with `vllm` (`vllm/vllm-openai:v0.12.0`, Hermes tool parser, `qwen3-30b-instruct`).
- Updated Open WebUI `OPENAI_API_BASE_URL` and `depends_on` healthcheck.
- Migrated `.env`: `VLLM_PORT`, `VLLM_IMAGE_TAG`; removed `TRITON_*`, `COMPOSE_BAKE`.
- Removed `Dockerfile`, `requirements.txt`, `models/qwen3-30b-instruct-2507/*`.
- Added `tests/smoke/check_vllm_models.sh`, `tests/smoke/check_vllm_tool_calls.sh`.
- Updated `docs/ARCHITECTURE.md`, `docs/INDEX.md`.
