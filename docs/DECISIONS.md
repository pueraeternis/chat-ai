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

**Decision:** Serve `Qwen/Qwen3-30B-A3B-Instruct-2507` with `--max-model-len 32768`, `--gpu-memory-utilization 0.9`, and `--served-model-name qwen3-30b-instruct` on a single NVIDIA GPU (device `0`, high-VRAM class).

**Reason:** Matches existing Triton vLLM backend settings in `models/qwen3-30b-instruct-2507/1/model.json`. Full 262K native context risks OOM on one GPU; 32K is the operational compromise per model card guidance.

**Rejected:** Defaulting to `--max-model-len 262144` on a single GPU without 1M-context tooling (DCA / multi-GPU setup).

## [2026-05-25] Tool calling: Hermes parser, no reasoning stack

**Decision:** Enable `--enable-auto-tool-choice` and `--tool-call-parser hermes`. Do not enable `--reasoning-parser` or thinking-mode templates for this deployment.

**Reason:** Qwen documentation recommends Hermes-style tool use for Qwen3. `Qwen3-30B-A3B-Instruct-2507` is **non-thinking only** (no `` blocks; `enable_thinking` not required). The model’s `tokenizer_config.json` chat template already embeds tool instructions and `<tool_call>` / `<tool_response>` XML; vLLM’s Hermes parser maps generations to OpenAI `tool_calls`.

**Rejected:** `qwen3_xml` / `qwen3_coder` parsers (target Qwen3-Coder, not this Instruct checkpoint); `--reasoning-parser qwen3` (wrong mode for Instruct-2507 and known tool-call interaction issues on thinking models).

## [2026-05-25] vLLM distribution and version

**Decision:** Use the official `vllm/vllm-openai` container image (CUDA 12.x tag, vLLM ≥ 0.12 recommended) instead of the custom Triton-based `Dockerfile`. Drop the Triton image build and `vllm_backend` clone.

**Reason:** Host CUDA 12.x drivers are backward-compatible with CUDA 12.x runtime images. Pinning vLLM ≥ 0.12 improves MoE (`qwen3_moe`) and tool-calling support versus v0.11.0 bundled in the current Triton image. Simpler operations and smaller maintenance surface.

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

**Reason:** Stable contract for API clients; hides vLLM and future inference backends behind an `InferencePort` adapter; central place for system-tool orchestration and response normalization.

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

**Decision:** Copy the **web-search** project into chat-ai under the `web_search` namespace (e.g. `src/web_search/{core,operations,adapters,mcp_servers}`, `config/web_search/`, `tests/web_search/`). Run **web-search-mcp** over **streamable HTTP** plus **SearXNG** in Compose. Imports refactored to `web_search.*` to avoid clashing with proxy `src/core/`.

**Reason:** Single repo for GPU stack + search; no dependency on an external checkout of the standalone web-search project at deploy time.

**Rejected:** Proxy reimplementing SearXNG/Playwright; leaving flat `from core import` packages that collide with proxy layers.

## [2026-05-26] System tools via MCP HTTP (integration bus)

**Decision:** **chat-proxy** connects hosted/system capabilities only through **MCP over HTTP** (`tools/call` on `/mcp`). Maintain a **system tool registry**: public `tools[].type` (e.g. `web_search`) → MCP server base URL + proxy-side orchestration. **web-search-mcp** is the first registered server. Additional capabilities in future waves = new MCP server in Compose + registry entry—not new ad-hoc HTTP clients per feature.

**Reason:** MCP is the standard integration surface; the same MCP servers can serve Open WebUI, local dev tools, and smoke tests. HTTP fits multi-container Compose. MCP stdio is only slightly faster than HTTP and does not apply across containers.

**Rejected:** MCP stdio as the primary proxy↔tool transport in production; exposing raw MCP wire protocol to application SDKs (clients use OpenAI Chat API with `tools[].type`); replacing MCP with direct in-process `operations` calls on the proxy hot path in v1.

## [2026-05-26] operations layer vs MCP tools

**Decision:** **`web_search.operations`** holds reusable business logic (`search_urls`, `fetch_page_markdown`, …) with explicit dependencies and `*Result` DTOs. **`web_search.mcp_servers`** registers thin MCP tools that delegate to operations. **Proxy** runs multi-step **orchestration** (router LLM, URL filter, final LLM, `annotations`) and invokes **MCP tools** (`search_urls`, `fetch_page_markdown`), not `operations` directly. Other hosts may call the same operations **in-process** without MCP.

**Reason:** One logic path for search/fetch; MCP standardizes the proxy boundary; operations stay portable for non-MCP integrators documented in the original web-search repo.

**Rejected:** Duplicating search/fetch in proxy; requiring every consumer to use MCP (in-process remains valid outside chat-proxy).

## [2026-05-26] Optional reasoning (VL-Instruct hybrid)

**Decision:**

- Request: `"reasoning": { "enabled": true }` → proxy sets `chat_template_kwargs: { "enable_thinking": true }` on vLLM.
- Response: passthrough from vLLM. On Qwen3-VL-Instruct, chain-of-thought usually appears in `message.content`; `message.reasoning_content` only if vLLM exposes a separate `reasoning` field (proxy renames to `reasoning_content`). No proxy tag parsing or content heuristics.
- **Incompatible** in the same request with `web_search` or client `function` tools → **400**.
- Do not accept `reasoning_content` / `reasoning` in incoming `messages` from clients → **400** (multi-turn: only assistant `content` goes back to vLLM).

**Reason:** Product goal is “thinking model” UX without a separate Thinking checkpoint; VL-Instruct supports hybrid thinking per Qwen docs.

**Rejected:** Default-on Thinking VL model; always-on reasoning for tool-calling paths; streaming reasoning in v1; proxy-side `` tag splitting or last-line answer heuristics.

## [2026-05-26] vLLM parsers for plan 02 target stack

**Decision:** Keep `--tool-call-parser hermes` for client `function` tools. Add `--reasoning-parser qwen3` when reasoning is in scope. Smoke-test both parsers together on `Qwen3-VL-30B-A3B-Instruct`.

**Reason:** VL chat template uses `<tool_call>` … `</tool_call>` (Hermes-compatible). Qwen3 reasoning parser extracts thinking before `` per vLLM docs.

**Rejected:** Relying on proxy-only tag parsing without vLLM reasoning parser; `qwen3_xml` unless Hermes smoke fails.

## [2026-05-26] Plan 02 scope boundaries

**Decision:** Plan 02 delivers documentation-aligned proxy + web-search integration + Compose wiring + smoke/contract tests. Out of scope for plan 02: `stream: true` (reject with 400/501), multiple system tools per request, `/v1/responses`, additional system tools beyond `web_search`.

**Reason:** Focused, reviewable wave before streaming and more hosted tools.

## [2026-05-26] Plan 03 — production streaming on chat-proxy

**Decision:** Plan 03 adds `stream: true` on `POST /v1/chat/completions` for production use (Open WebUI default, OpenAI SDK). Remove the plan 02 reject path once implemented. Non-stream behavior unchanged.

**Reason:** Open WebUI requires SSE; streaming is not a throwaway MVP — implementation may merge in ordered slices (plain → reasoning/functions → web_search orchestration).

**Rejected:** Leaving streaming disabled indefinitely; fake streaming (single-chunk “stream”) for long operations.

## [2026-05-26] Streaming transport: async passthrough to vLLM

**Decision:** Use **async** HTTP (`httpx.AsyncClient`) and FastAPI `StreamingResponse` (`text/event-stream`). For plain chat, reasoning, and client `function` modes: **byte/lines passthrough** of vLLM SSE without reassembling the full completion on the proxy. On client disconnect, **cancel/close** the upstream vLLM stream. Timeouts: short connect timeout; read timeout suitable for long generations (aligned with `CHAT_PROXY_VLLM_TIMEOUT_SECONDS`).

**Reason:** Sync `Client` inside `async def` blocks the event loop; passthrough minimizes latency and parser bugs; cancellation avoids wasted GPU work.

**Rejected:** Buffering entire stream on proxy for passthrough modes; sync-only adapter for production.

## [2026-05-26] Streaming by request mode

**Decision:**

| Mode | `stream: true` behavior |
|------|-------------------------|
| Plain chat (+ vision) | Passthrough vLLM SSE |
| `reasoning.enabled` | Passthrough vLLM SSE with `enable_thinking`; map vLLM `reasoning` → `reasoning_content` only if vLLM emits a separate field in stream chunks (no `` tag parsing) |
| Client `function` tools | Passthrough vLLM SSE for tool-call deltas |
| `web_search` | **Orchestrated stream** (see next entry) |

**Reason:** Most modes are thin proxy; web_search is multi-step and needs custom pre-stream events.

**Rejected:** Rejecting all `web_search` + `stream` with 400 in plan 03 (acceptable only as plan 02 interim).

## [2026-05-26] `web_search` orchestrated streaming

**Decision:** When `stream: true` and `tools` include `web_search`:

1. Run router, MCP search, URL filter, and page fetch **without** streaming (same logic as plan 02).
2. Emit **Open WebUI-compatible SSE status events** during that phase (search visible in UI).
3. Emit **citation/source** SSE events for fetched URLs (OWUI source chips).
4. Call vLLM final completion with `stream: true` and **passthrough** answer tokens.
5. For `stream: false`, keep plan 02 JSON (`content` + `annotations` `url_citation`).

If router returns SKIP, stream a single vLLM completion like plain chat (no MCP status sequence beyond optional “Generating answer…”).

**Reason:** Users see progress during long search; final answer still token-streamed; matches mental model discussed for production.

**Rejected:** Fake stream (one delta with full text after pipeline); streaming only the silent phase with JSON at end.

## [2026-05-26] Open WebUI: SSE status and citations from chat-proxy

**Decision:** When Open WebUI uses chat-proxy as `OPENAI_API_BASE_URL`, progress and sources are delivered in the **same SSE stream** as chat chunks, using the pipelines-compatible wrapper:

```json
{"event": {"type": "status", "data": {"description": "...", "done": false, "action": "web_search"}}}
{"event": {"type": "citation", "data": {"document": [...], "metadata": [...], "source": {"name": "...", "url": "..."}}}}
```

Always end the status sequence with `done: true`. Citations before or as answer streaming starts. Keep OpenAI **`annotations`** (`url_citation`) for non-OWUI SDK clients.

**Reason:** OWUI built-in web search uses internal `event_emitter` (`status`, `citation`); external OpenAI backends do not receive `X-Open-WebUI-Chat-Id` on `/v1/chat/completions`, so `POST /api/v1/chats/.../event` is **not** the primary integration for this deployment.

**Rejected:** Relying on OWUI Admin “Web Search” (SearXNG) in parallel with proxy `web_search` (duplicate search); assuming `message.annotations` alone renders OWUI source chips.

## [2026-05-26] Open WebUI operational note (web search)

**Decision:** When clients use proxy `tools: [{ "type": "web_search" }]`, **disable** Open WebUI’s built-in Web Search for that workflow to avoid double SearXNG and mixed UX. Document in plan 03 and ARCHITECTURE.

**Reason:** Built-in OWUI search runs in OWUI middleware before the model call; proxy `web_search` is a different code path.

**Rejected:** Documenting only proxy annotations without OWUI event format.

## [2026-05-26] Plan 04 — Open WebUI web search via Filter (not built-in OWUI search)

**Decision:** For browser users, wire **proxy hosted `web_search`** using an Open WebUI **Filter Function** (`inlet`) that appends `tools: [{ "type": "web_search", "user_location", "search_context_size" }]` before OWUI calls `OPENAI_API_BASE_URL` (chat-proxy). Filter source lives in repo under `open_webui/functions/`; operators import via Admin → Functions (no OWUI fork, no `FUNCTIONS_DIR`).

**Reason:** Matches OpenAI semantics (search only when tool present); reuses proxy orchestration + plan 03 SSE UX; API clients stay opt-in.

**Rejected:** Relying on OWUI Admin Web Search alone (OWUI middleware, not proxy `web_search`); auto-injecting `web_search` on every proxy request; forking `open-webui`.

## [2026-05-26] Filter injection rules

**Decision:**

- Inject only from Filter `inlet` when the filter is active for the chat (and optionally when `body.features.web_search` is true if valve `require_web_search_feature` is set).
- Skip injection if `tools` already includes `web_search` or any client `function` tool.
- Default `user_location` via filter **Valves** (e.g. US / New York); operators adjust per deployment.
- **Disable** OWUI global Web Search when this filter is the primary UI path.

**Reason:** Avoid `conflicting_tools` 400; avoid duplicate SearXNG; keep API contract explicit for non-UI clients.

**Rejected:** Mandatory search for all chats; using External Tool Events API from chat-proxy as OpenAI backend.

## [2026-05-26] SearXNG search language from query script (en / ru)

**Decision:** For `web_search`, set SearXNG `language` from the **last user message text**, not from `user_location.country`:

| User text | SearXNG `language` tag |
|-----------|-------------------------|
| Mostly **Latin** (A–Z) | `en` |
| **Cyrillic** count ≥ Latin | `ru` |
| No letters / other scripts (CJK, digits, …) | `en` (default) |

Implementation: `src/operations/search_locale.py` (`searxng_locale_from_messages`); used in `web_search_pipeline` for MCP `search_urls` and router prompt.

**`user_location`** remains **required** on the tool (OpenAI hosted-tool shape: ISO `country`, optional `city` / `region` / `timezone`). It does **not** select SearXNG locale. City names are not valid SearXNG language tags; regional tags like `ru-RU` are optional and not used by this rule.

**Reason:** Operators and users expect search results in the language of the question; SearXNG documents language/region tags `en`, `ru`, `en-US`, `ru-RU`, etc. ([SearXNG locales](https://docs.searxng.org/src/searx.locales.html)).

**Rejected:** Mapping only `user_location.approximate.country` → `ru-RU` / `en-US`; using city name as SearXNG `language`.

## [2026-05-26] OWUI model capabilities for proxy search UX (v0.6.32)

**Decision:** When Open WebUI uses chat-proxy as `OPENAI_API_BASE_URL` with the **Proxy Web Search** filter, enable per-model **Capabilities → Citations** and **Status Updates** (Admin → Settings → Models). Proxy SSE already sends `event.status` and `event.citation`; on OWUI **v0.6.32** the UI does not render them without these flags. Global Admin **Web Search** remains **disabled** to avoid duplicate SearXNG.

**Reason:** Operator verification showed real fetched content without UI feedback until capabilities were enabled; filter inject does not require the Web Search globe when `require_web_search_feature` is false.

**Rejected:** Assuming plan 03 SSE alone is sufficient for OWUI display without model capability flags on v0.6.32.

## [2026-05-26] Plan 05 — chat-proxy structured logging

**Decision:** Add application logging to **chat-proxy** using Python **`logging`** (stdlib). Configure via `CHAT_PROXY_LOG_LEVEL` (default `INFO`) and optional `CHAT_PROXY_LOG_JSON` for machine-readable lines. Assign a **`request_id`** (UUID) per `POST /v1/chat/completions` and include it on every log record for that request.

**web_search (required operator visibility):** Log explicit stages: request `mode=web_search`; `router_result` (`SEARCH` \| `SKIP`); `search_hits` with URL list from SearXNG; `url_filter_result` with selected URLs; `fetch_results` (requested vs fetched vs failed); `web_search_complete` with outcome and timing. Do **not** log full `messages` or page markdown at INFO.

**Non-search:** Log `mode` (`plain`, `reasoning`, `function`) at request start/end with duration; log validation and upstream errors without bodies.

**Reason:** Plan 04 operator work showed search can run while UI omits status; smoke/DevTools are insufficient for routine ops. Logs must answer “was web_search invoked and what URLs were used?” from `docker logs chat-proxy` alone.

**Rejected:** New logging dependencies (structlog/loguru) in v1; logging full prompts/responses; scope including web-search-mcp or OWUI in the same wave.

## [2026-05-26] SSE stream: `request_id` contextvar scope

**Decision:** For `stream: true`, log `request_start` in the route handler with `request_id` set via `contextvars`, then **reset the handler token** before returning `StreamingResponse`. Re-bind `request_id` at the start of the SSE body generator and call `request_end` + `reset_request_id` in that generator’s `finally` (same async task Starlette uses for `stream_response`).

**Reason:** Resetting a `ContextVar` token from the handler after the stream finishes fails with `ValueError: Token was created in a different Context`, aborts ASGI, and OWUI shows `TransferEncodingError` even when web search and the answer succeeded.

**Rejected:** Passing the handler’s reset token into `_stream_with_logging`; skipping reset on streams (leaks context between requests on shared workers).

## [2026-05-26] Plan 06 — web_search final answer: temporal grounding system prompt

**Decision:** On the **final** vLLM call after page fetch (non-stream `_final_answer` and stream `_final_stream_body`), prepend one **`role: system`** message built by the proxy. Prompt text is **English** (project standard). Include **today’s date** from `datetime` at request time, with timezone from `user_location.approximate.timezone` (IANA) when valid, else **UTC**. Instruct the model to treat the following `tool` message as live web evidence and **not** to reject sources as “from the future” or fake solely because publication dates are after its training-time assumptions about the current year.

**Reason:** OWUI verification showed successful search/fetch but answers denying breaking news (e.g. comparing source dates in 2026 to an internal “May 2025” today). User language varies; prompts in code stay English. OWUI per-model system prompts are not a reliable substitute for API clients.

**Rejected:** Russian (or locale-matched) proxy prompts; relying only on OWUI Admin system prompt; injecting date only in OWUI filter; post-filtering assistant text for phrases like “fake”; changing router/URL-filter prompts for this problem.
