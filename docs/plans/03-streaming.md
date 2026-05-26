# Plan 03 — Chat completions streaming (production)

**Status:** Active (documentation approved 2026-05-26).  
**Goal:** Enable `stream: true` on `POST /v1/chat/completions` so Open WebUI and OpenAI SDK clients get SSE token streaming; for `web_search`, show search progress and sources in Open WebUI while streaming the final LLM answer.

**Prerequisite:** Plan 02 implemented (non-stream proxy, web-search pipeline, Compose).  
**References:** [DECISIONS.md](../DECISIONS.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [02-chat-proxy-api.md](02-chat-proxy-api.md), [Open WebUI Events](https://docs.openwebui.com/features/extensibility/plugin/development/events/), [OWUI PR #12559](https://github.com/open-webui/open-webui/pull/12559) (SSE events), [OWUI issue #19250](https://github.com/open-webui/open-webui/issues/19250) (status bridge).

---

## 1. Problem

- Plan 02 rejects `stream: true` with `Streaming is not supported in v1` (400).
- Open WebUI sends `stream: true` by default → chat fails in UI.
- For `web_search`, users need progress (“searching…”) and source chips like built-in OWUI web search, not a silent multi-minute wait.

---

## 2. Decisions summary

| Topic | Decision |
|-------|----------|
| Scope | Production-grade streaming in one plan; implementation may land in ordered PRs, each mergeable |
| Transport | `text/event-stream`; async HTTP to vLLM; cancel upstream on client disconnect |
| Plain / reasoning / client `function` | **Passthrough** vLLM SSE bytes (minimal proxy logic) |
| `web_search` | **Orchestrated stream**: internal steps non-stream; SSE **status** + **citation** events; then passthrough final vLLM stream |
| SDK citations | Keep `message.annotations` (`url_citation`) on final non-stream chunk or last stream chunk where applicable |
| OWUI progress | SSE chunks `data: {"event": {"type": "status", "data": {...}}}` (see §4) |
| OWUI sources | SSE `citation` / `source` events (and/or top-level `sources` if verified on pinned OWUI) |
| Fake stream | **Rejected** — buffering full answer into one delta |
| OWUI built-in web search | **Disable** when using proxy `web_search` (avoid duplicate SearXNG) |
| External tool event API | **Not used** for chat-proxy as `OPENAI_API_BASE_URL` (no `X-Open-WebUI-*` headers on that path) |

Full rationale: [DECISIONS.md](../DECISIONS.md) entries from 2026-05-26 (plan 03).

---

## 3. API contract

### 3.1 Common

- `stream: false` — unchanged plan 02 behavior.
- `stream: true` — `Content-Type: text/event-stream`, OpenAI-style lines `data: {...}\n\n`, terminal `data: [DONE]\n\n`.
- Validation errors (conflicts, missing `user_location`, etc.) → **HTTP 4xx JSON** before any SSE body.
- vLLM errors before stream start → HTTP 4xx/5xx JSON; mid-stream failure → close stream (match vLLM / OpenAI behavior).
- `stream_options` / `include_usage` — passthrough to vLLM when present.

### 3.2 Mode matrix (`stream: true`)

| Mode | Behavior |
|------|----------|
| **Plain chat** | Proxy forwards body (minus proxy-only fields) with `stream: true` → passthrough vLLM SSE |
| **Reasoning** | Same + `chat_template_kwargs.enable_thinking`; passthrough deltas; map `reasoning` → `reasoning_content` only if vLLM emits separate field in stream (no tag parsing) |
| **Client functions** | Passthrough vLLM SSE for `tool_calls` deltas; align with non-stream normalization where a final aggregated message exists |
| **web_search** | Orchestrated (§3.3) |

### 3.3 `web_search` orchestrated stream

**Internal (no SSE to client):**

0. Router LLM (search? query) — sync completion  
1. MCP `search_urls`  
2. LLM URL filter  
3. Parallel `fetch_page_markdown`  
4. (Optional) router SKIP → single vLLM stream like plain chat  

**SSE to client (in order):**

1. **Status events** during steps 0–3, e.g.  
   - `description`: “Searching the web…”, “Fetching pages…”, “Generating answer…”  
   - `action`: `"web_search"` (matches OWUI native middleware)  
   - `done`: `false` while in progress; **must** emit final status with `done: true` before or when answer stream starts  
2. **Citation events** for fetched URLs (OWUI chips) — emit after fetch, before or with answer stream  
3. **vLLM stream** for final completion (`messages` + synthetic `role: tool` context) — passthrough chunks  
4. **`[DONE]`**

**Non-stream fallback:** `stream: false` keeps plan 02 JSON response (`content` + `annotations`).

**Rejected:** Rejecting all `web_search` + `stream` with 400 (plan 02 interim only).

---

## 4. Open WebUI SSE event format

Open WebUI (v0.6.32 in Compose) proxies external OpenAI backends and can interpret **non–chat.completion.chunk** lines in the same SSE stream when wrapped as:

```text
data: {"event": {"type": "status", "data": {"description": "Searching the web", "done": false, "action": "web_search"}}}

```

**Status** ([Events docs](https://docs.openwebui.com/features/extensibility/plugin/development/events/)):

| Field | Required | Notes |
|-------|----------|--------|
| `type` | yes | `"status"` inside `event` |
| `data.description` | yes | Shown above message; markdown OK |
| `data.done` | yes | `false` = shimmer; `true` = stop animation |
| `data.hidden` | no | default `false` |
| `data.action` | no | `"web_search"` for familiar UI |

Always send at least one status with `done: true` after search phase.

**Citations** — emit before answer tokens when possible:

```text
data: {"event": {"type": "citation", "data": {
  "document": ["excerpt or title"],
  "metadata": [{"source": "Page title", "url": "https://..."}],
  "source": {"name": "Page title", "url": "https://..."}
}}}
```

Also support OpenAI **`annotations`** / `url_citation` for SDK clients on the final message (plan 02); OWUI chips rely on `citation`/`source` events, not `annotations` alone.

**Verification:** After implementation, confirm in browser DevTools (OWUI → Network → chat completion stream) that status and citations render on **v0.6.32**. Newer OWUI may accept unwrapped `{"type":"status",...}` per [#19250](https://github.com/open-webui/open-webui/issues/19250) — optional follow-up.

**Not used:** `POST /api/v1/chats/{chat_id}/messages/{message_id}/event` from chat-proxy (requires OWUI to call proxy as an external **tool**, not as OpenAI base URL).

---

## 5. Application changes (implementation checklist)

### 5.1 Infrastructure

- [ ] `InferencePort`: add async stream method(s)
- [ ] `VllmInferenceAdapter`: `httpx.AsyncClient`, `stream=True`, byte iterator; separate connect vs read timeouts
- [ ] `http_api.py`: branch on `stream`; `StreamingResponse`; cancel vLLM on client disconnect
- [ ] Remove global `_reject_stream` in `chat_completion.py`

### 5.2 Passthrough modes

- [ ] Plain + multimodal stream
- [ ] Reasoning stream (`enable_thinking`)
- [ ] Client function stream

### 5.3 `web_search` orchestrated stream

- [ ] `WebSearchOrchestrator.run_stream()` (or equivalent): status/citation SSE helpers
- [ ] Final step: vLLM `stream: true`, passthrough
- [ ] Map fetched pages → `citation` events + final `annotations` for SDK

### 5.4 Tests

- [ ] Unit: routing stream/non-stream; status payload shape
- [ ] Unit/integration: mock vLLM SSE fixture → proxy forwards bytes + `[DONE]`
- [ ] Smoke: `curl -N` plain stream; web_search stream shows status lines (grep)
- [ ] Manual: Open WebUI chat + web_search tool request

### 5.5 Documentation (this wave)

- [x] `docs/plans/03-streaming.md`
- [x] `docs/DECISIONS.md`, `ARCHITECTURE.md`, `INDEX.md`, `PROGRESS.md`
- [ ] Update `tests/smoke/README.md` when smoke scripts exist

---

## 6. Deployment notes

- **Reverse proxy:** If nginx/traefik fronts chat-proxy, disable buffering for `/v1/chat/completions` when `stream=true`.
- **Open WebUI:** Keep `OPENAI_API_BASE_URL` → chat-proxy; turn off Admin **Web Search** when using proxy `tools: [{type: web_search}]` to avoid double search.
- **WebSocket:** OWUI UI still uses WebSocket for its own pipeline; external SSE events are bridged server-side — ensure ingress allows WebSocket to OWUI (not chat-proxy).

---

## 7. Acceptance criteria

1. **Plain:** `stream: true` → token deltas in Open WebUI; no “Streaming is not supported” error.
2. **Functions:** `stream: true` + `function` tools → valid streamed `tool_calls` (or final chunk consistent with vLLM).
3. **Reasoning:** `stream: true` + `reasoning.enabled` → streamed answer; no tools in same request.
4. **Web search:** `stream: true` + `web_search` → status visible during search; sources/citations appear; answer streams; `annotations` present for non-stream clients.
5. **Regression:** All plan 02 non-stream tests and smoke still pass.

---

## 8. Out of scope (plan 03)

- `/v1/responses`, embeddings, images API
- Multiple system tools per request
- Proxy-side `` / reasoning tag splitting in stream
- OWUI Filter/Pipe to auto-inject `web_search` tool (separate UX task)
- Upgrade OWUI solely for [#19250](https://github.com/open-webui/open-webui/issues/19250) unwrapped status format (verify on 0.6.32 first)
