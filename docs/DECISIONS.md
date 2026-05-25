# Architectural decisions

Chronological journal. New entries are appended at the end.

## [2026-05-25] Replace Triton with native vLLM for inference

**Decision:** Remove NVIDIA Triton Server (including the OpenAI frontend on port 9000) and serve `Qwen/Qwen3-30B-A3B-Instruct-2507` via the vLLM OpenAI-compatible API (`vllm serve`) in Docker Compose.

**Reason:** Triton’s OpenAI frontend does not expose native OpenAI tool calling (`tool_calls`, `finish_reason: tool_calls`). Open WebUI and agent flows require a server that parses model output into standard `tool_calls`. Native vLLM supports this with `--enable-auto-tool-choice` and a tool-call parser.

**Rejected:** Keeping Triton and adding a separate proxy/parser layer; using Qwen-Agent as mandatory middleware between Open WebUI and the model (adds complexity when vLLM alone satisfies the protocol).

## [2026-05-25] Keep Open WebUI as the only user-facing application

**Decision:** Retain `ghcr.io/open-webui/open-webui` unchanged in role; point `OPENAI_API_BASE_URL` at the vLLM service (`http://vllm:8000/v1`) instead of Triton.

**Reason:** UI, RAG embeddings, and session data already live in Open WebUI. The migration scope is the inference backend only.

**Rejected:** Replacing Open WebUI with Qwen-Agent UI or a custom frontend in this phase.

## [2026-05-25] Model and runtime parameters

**Decision:** Serve `Qwen/Qwen3-30B-A3B-Instruct-2507` with `--max-model-len 32768`, `--gpu-memory-utilization 0.9`, and `--served-model-name qwen3-30b-instruct` on a single NVIDIA GPU (device `0`, A100 80GB).

**Reason:** Matches existing Triton vLLM backend settings in `models/qwen3-30b-instruct-2507/1/model.json`. Full 262K native context risks OOM on one GPU; 32K is the operational compromise per model card guidance.

**Rejected:** Defaulting to `--max-model-len 262144` on a single A100 without 1M-context tooling (DCA / multi-GPU setup).

## [2026-05-25] Tool calling: Hermes parser, no reasoning stack

**Decision:** Enable `--enable-auto-tool-choice` and `--tool-call-parser hermes`. Do not enable `--reasoning-parser` or thinking-mode templates for this deployment.

**Reason:** Qwen documentation recommends Hermes-style tool use for Qwen3. `Qwen3-30B-A3B-Instruct-2507` is **non-thinking only** (no `` blocks; `enable_thinking` not required). The model’s `tokenizer_config.json` chat template already embeds tool instructions and `<tool_call>` / `<tool_response>` XML; vLLM’s Hermes parser maps generations to OpenAI `tool_calls`.

**Rejected:** `qwen3_xml` / `qwen3_coder` parsers (target Qwen3-Coder, not this Instruct checkpoint); `--reasoning-parser qwen3` (wrong mode for Instruct-2507 and known tool-call interaction issues on thinking models).

## [2026-05-25] vLLM distribution and version

**Decision:** Use the official `vllm/vllm-openai` container image (CUDA 12.x tag, vLLM ≥ 0.12 recommended) instead of the custom Triton-based `Dockerfile`. Drop the Triton image build and `vllm_backend` clone.

**Reason:** Host driver 575.51.03 (CUDA 12.9) is backward-compatible with CUDA 12.x runtime images. Pinning vLLM ≥ 0.12 improves MoE (`qwen3_moe`) and tool-calling support versus v0.11.0 bundled in the current Triton image. Simpler operations and smaller maintenance surface.

**Rejected:** Continuing to maintain `nvcr.io/nvidia/tritonserver` + pip-installed `vllm==0.11.0` + `vllm_backend` branch `r25.03`.

## [2026-05-25] Remove Triton model repository layout

**Decision:** After migration, delete or stop using `models/*/config.pbtxt` and Triton `model.json` repository layout; pass model id and flags via vLLM CLI / Compose `command` and `.env`.

**Reason:** vLLM loads Hugging Face weights from `HF_CACHE_ROOT`; Triton repository metadata is irrelevant to native vLLM.

**Rejected:** Keeping `models/` as a pseudo-config directory without Triton (optional env-file only if team prefers; default is Compose + `.env`).

## [2026-05-25] Networking, cache, and RAG

**Decision:** Keep Docker network `chat-ai-stack`, bind-mount `HF_CACHE_ROOT` into the vLLM container, and keep Open WebUI RAG on local embeddings (`RAG_EMBEDDING_MODEL=BAAI/bge-m3` via `HF_HUB_CACHE`) without routing embeddings through the LLM server.

**Reason:** Preserves existing host cache layout and isolates chat inference from embedding I/O.

**Rejected:** Exposing Triton HTTP/gRPC/metrics ports (18100–18102); they are unused by Open WebUI.

## [2026-05-25] Environment variable naming

**Decision:** Replace `TRITON_*` variables with `VLLM_*` (e.g. `VLLM_PORT` for host-published OpenAI port, default mapping to container `8000`). Remove `TRITON_TOKENIZER` (was a separate HF id for Triton’s OpenAI frontend, not the served 30B model).

**Reason:** Clear configuration contract aligned with the new service name and a single model tokenizer from `Qwen/Qwen3-30B-A3B-Instruct-2507`.

**Rejected:** Retaining `TRITON_*` names as aliases after cutover.

## [2026-05-25] Validation criteria for native tools

**Decision:** Acceptance requires `POST /v1/chat/completions` with `tools` to return `finish_reason: tool_calls` and a non-empty `message.tool_calls` array; second turn with `role: tool` + `tool_call_id` must produce a normal assistant `content` reply. Repeat from Open WebUI with function tools or MCP enabled.

**Reason:** Aligns with Qwen function-calling documentation and Open WebUI’s OpenAI client expectations.

**Rejected:** Accepting tool calls visible only as raw `<tool_call>` XML inside `content` without structured `tool_calls`.
