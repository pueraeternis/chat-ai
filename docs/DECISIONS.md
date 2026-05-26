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

## [2026-05-26] Inference model: Qwen3-VL-30B-A3B-Instruct

**Decision:** Serve `Qwen/Qwen3-VL-30B-A3B-Instruct` via vLLM (vision-language MoE, ~30.5B total / ~3.3B active). Rename served model id to `qwen3-vl-30b-instruct` when proxy cutover is implemented (Compose may still expose legacy `qwen3-30b-instruct` until then).

**Reason:** Multimodal chat (images) plus text; hybrid thinking via `enable_thinking` on request (unlike text-only `Qwen3-30B-A3B-Instruct-2507`, which has no thinking toggle). Same Hermes-compatible `<tool_call>` / `<tool_response>` chat template family.

**Rejected:** `Qwen/Qwen3-VL-30B-A3B-Thinking` as the default checkpoint (thinking-only; disabling reasoning is unreliable per HF community reports); keeping text-only `Instruct-2507` when VL is required.

## [2026-05-26] Chat proxy: single OpenAI Chat API surface

**Decision:** Add a Python **chat-proxy** service exposing only `POST /v1/chat/completions` and `GET /v1/models` (passthrough). Clients (OpenAI SDK, internal apps) point `base_url` at the proxy, not at vLLM directly. Open WebUI switches to the proxy after plan 02 implementation.

**Reason:** Stable contract for the company; hides vLLM and future inference backends behind an `InferencePort` adapter; central place for system-tool orchestration and response normalization.

**Rejected:** Adding `/v1/responses` in plan 02; exposing vLLM directly as the long-term public API; inventing non-OpenAI endpoint names.

## [2026-05-26] Two request modes (mutually exclusive tools)

**Decision:**

1. **System tools** — entries in `tools[]` with `type` other than `function` (first: `web_search`). Executed entirely on the proxy; client receives one `chat.completion` with `finish_reason: stop`, final `content`, and optional `annotations` (`url_citation`). No `tool_calls` exposed for system tools.
2. **Client function calling** — `tools[]` with `type: "function"` only. Proxy forwards to vLLM; response may have `tool_calls`, `content: null`, `finish_reason: tool_calls`. Client executes functions and sends `role: tool` on the next turn (proxy passthrough).

**Conflict rule:** If a request contains both a system tool (e.g. `web_search`) and any `type: "function"` tool, return **400** `invalid_request_error` / `conflicting_tools`.

**Reason:** Matches OpenAI built-in tools vs function-calling separation; avoids ambiguous orchestration.

**Rejected:** Mixed system + client tools in one request (v1); exposing system `web_search` as a client-executed `function` tool.

## [2026-05-26] System tool contract: `web_search`

**Decision:** Enable web search via:

```json
"tools": [{
  "type": "web_search",
  "search_context_size": "low" | "medium" | "high",
  "user_location": {
    "type": "approximate",
    "approximate": { "country", "city", "region", "timezone" }
  }
}]
```

- `user_location` is **required** for `web_search` (stricter than OpenAI’s optional field).
- `search_context_size` controls URL count and markdown budget in the pipeline (defaults documented in plan 02).
- v1: **one** system tool per request.

**Orchestration (server-side):** internal router LLM → MCP `search_urls` (10 hits) → LLM URL filter → parallel MCP `fetch_page_markdown` → final LLM → response with `annotations` (`url_citation`) and answer in `content`. System tools are stripped before calls to vLLM.

**Reason:** OpenAI-like “hosted web search” UX (one HTTP round-trip); reuse existing web-search MCP (`search_urls`, `fetch_page_markdown`).

**Rejected:** Primary enablement via `web_search_options` only; mandatory `mcp_web_search` function name in client `tools`; returning raw `<tool_call>` XML to the client for search.

## [2026-05-26] Embed web-search in this repository

**Decision:** Copy the **web-search** project into chat-ai (`src/web_search/` or workspace package): `core`, `operations`, `adapters`, `config`, tests; run MCP HTTP (+ SearXNG) in Compose. Proxy uses an MCP **client** (`tools/call`); business logic stays in web-search operations.

**Reason:** Single repo for GPU stack + search; no dependency on an external `~/projects/web-search` path at deploy time.

**Rejected:** Proxy reimplementing SearXNG/Playwright; mandatory in-process-only integration without MCP in v1 (in-process may follow as optimization).

## [2026-05-26] Optional reasoning (VL-Instruct hybrid)

**Decision:**

- Request: `"reasoning": { "enabled": true }` → proxy sets `chat_template_kwargs: { "enable_thinking": true }` on vLLM.
- Response: `message.reasoning_content` (chain-of-thought) and `message.content` (final answer). Prefer vLLM `--reasoning-parser qwen3`; proxy fallback parser splits `` / `` if reasoning appears inside `content`.
- **Incompatible** in the same request with `web_search` or client `function` tools → **400**.
- Do not accept `reasoning_content` / `reasoning` in incoming `messages` from clients → **400** (multi-turn: only assistant `content` goes back to vLLM).

**Reason:** Company expects “thinking model” UX without a separate Thinking checkpoint; VL-Instruct supports hybrid thinking per Qwen docs.

**Rejected:** Default-on Thinking VL model; always-on reasoning for tool-calling paths; streaming reasoning in v1.

## [2026-05-26] vLLM parsers for plan 02 target stack

**Decision:** Keep `--tool-call-parser hermes` for client `function` tools. Add `--reasoning-parser qwen3` when reasoning is in scope. Smoke-test both parsers together on `Qwen3-VL-30B-A3B-Instruct`.

**Reason:** VL chat template uses `<tool_call>` … `</tool_call>` (Hermes-compatible). Qwen3 reasoning parser extracts thinking before `` per vLLM docs.

**Rejected:** Relying on proxy-only tag parsing without vLLM reasoning parser; `qwen3_xml` unless Hermes smoke fails.

## [2026-05-26] Plan 02 scope boundaries

**Decision:** Plan 02 delivers documentation-aligned proxy + web-search integration + Compose wiring + smoke/contract tests. Out of scope for plan 02: `stream: true` (reject with 400/501), multiple system tools per request, `/v1/responses`, additional system tools beyond `web_search`.

**Reason:** Focused, reviewable wave before streaming and more hosted tools.
