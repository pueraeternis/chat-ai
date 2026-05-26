# Open WebUI extensions (chat-ai)

Functions for [Open WebUI](https://github.com/open-webui/open-webui) that integrate with **chat-proxy** (not the OWUI built-in Web Search stack).

## Proxy Web Search filter

**File:** `functions/proxy_web_search_filter.py`

When the user enables **Proxy Web Search** on a chat, the filter `inlet` appends a hosted OpenAI-style tool:

```json
{
  "type": "web_search",
  "search_context_size": "medium",
  "user_location": {
    "type": "approximate",
    "approximate": {
      "country": "RU",
      "city": "Saint Petersburg",
      "region": "Leningrad Oblast",
      "timezone": "Europe/Moscow"
    }
  }
}
```

Open WebUI forwards `tools` to `OPENAI_API_BASE_URL` (chat-proxy). Proxy runs orchestrated search + SSE status/citations (plans 02–03). SearXNG language (`en` / `ru`) comes from the user message text, not from these valves.

Shared inject logic for tests: `inject_web_search.py` (keep in sync with the filter file).

### Admin setup

1. **Disable** Admin → Settings → **Web Search** (avoid duplicate SearXNG with OWUI middleware). This is **not** the same as model capabilities below.
2. Ensure **Open WebUI** points at chat-proxy (`OPENAI_API_BASE_URL=http://chat-proxy:8080/v1` in Compose).
3. **Admin → Functions** → import or create `functions/proxy_web_search_filter.py`; keep the function **Active**.
4. **Admin → Settings → Models** → your model (e.g. `qwen3-vl-30b-instruct`):
   - **Filters** → enable **Proxy Web Search**.
   - **Capabilities** → enable **Citations** and **Status Updates** (required on OWUI v0.6.32 for proxy SSE UX; see below).
   - **Web Search** capability (globe) is **optional** when `require_web_search_feature` is `false` (default).
5. Optional: **Default Filters** so new chats start with the filter on.
6. In **Chat**, enable **Proxy Web Search** (chip under the input or **Integrations** menu). The filter `inlet` runs only when this toggle is on.

### Model capabilities (OWUI v0.6.32)

Proxy sends progress and sources in the same SSE stream as chat tokens:

```text
data: {"event": {"type": "status", "data": {"description": "Searching the web…", ...}}}
data: {"event": {"type": "citation", "data": {...}}}
```

On **Open WebUI v0.6.32** (pinned in Compose), those lines are **not shown** unless the model has:

| Capability | UI effect |
|------------|-----------|
| **Status Updates** | “Searching the web…”, “Fetching pages…”, “Generating answer…” |
| **Citations** | Source chips / footnotes for URLs from the proxy pipeline |

Search can still run without them (answer may cite real pages); only the UI feedback is missing. Enable both on the model and **Save & Update**.

**Where:** Admin → Settings → **Models** → edit model → section **Capabilities** (not Admin → Settings → Web Search).

### Valves (admin)

| Valve | Default | Purpose |
|-------|---------|---------|
| `country` | `RU` | `user_location` only |
| `city` | `Saint Petersburg` | approximate location |
| `region` | `Leningrad Oblast` | approximate location |
| `timezone` | `Europe/Moscow` | IANA timezone |
| `search_context_size` | `medium` | `low` \| `medium` \| `high` |
| `require_web_search_feature` | `false` | If `true`, inject only when `features.web_search` is set |

### Verify

1. **Proxy Web Search** on in chat; **Citations** + **Status Updates** on the model → news query shows status lines, source chips, streamed answer.
2. Filter off → plain chat (no proxy search).
3. Direct API without `tools` → no search (regression).
4. From repo root (stack up): `./tests/smoke/check_proxy_web_search.sh`

### Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Plausible news but no “Searching the web…” | Enable **Status Updates** on the model; search may still have run |
| No source chips / footnotes | Enable **Citations** on the model |
| No search at all | **Proxy Web Search** chip off, filter inactive in Functions, or model missing from **Filters** list |
| Double / odd search | Admin → **Web Search** still on — disable it |
| Debug without UI | `./tests/smoke/check_proxy_web_search.sh`; F12 → Network → completions → `tools` with `web_search` and SSE `event` lines |

Structured chat-proxy logging (web_search stages, URLs): see [docs/plans/05-chat-proxy-logging.md](../docs/plans/05-chat-proxy-logging.md) (implementation pending). Until then: smoke + `docker logs chat-proxy` (access only) + browser Network.

### Conflicts

The filter does **not** inject if `tools` already contains `web_search` or any `type: "function"` tool (proxy returns `400 conflicting_tools`).

Optional: enable model **Web Search** capability and set valve `require_web_search_feature=true` to tie injection to OWUI’s Web Search icon instead of only the filter chip.
