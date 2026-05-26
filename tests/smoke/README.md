# Smoke tests

Scripts for a **running** stack (`docker compose up`). Load env from repo root:

```bash
set -a && source .env && set +a
```

## Prerequisites

| Check | Script |
|-------|--------|
| Proxy reachable, model listed | `check_proxy_models.sh` |

Direct vLLM (optional, bypass proxy):

| Check | Script |
|-------|--------|
| vLLM `/v1/models` | `check_vllm_models.sh` |
| vLLM function `tool_calls` | `check_vllm_tool_calls.sh` |

## Chat-proxy contract (plan 02)

All use `CHAT_PROXY_BASE_URL` (default `http://127.0.0.1:${CHAT_PROXY_PORT}/v1`).

| # | Scenario | Script | Typical timeout |
|---|----------|--------|-----------------|
| 1 | Plain chat | `check_proxy_plain_chat.sh` | `SMOKE_CURL_MAX_TIME` (300s) |
| 2 | Plain chat (SSE stream) | `check_proxy_stream.sh` | 300s |
| 3 | Client function calling | `check_proxy_function_calling.sh` | 300s |
| 4 | System `web_search` | `check_proxy_web_search.sh` | `SMOKE_WEB_SEARCH_CURL_MAX_TIME` (600s) |
| 5 | Vision (`image_url`) | `check_proxy_vision.sh` | 300s; uses `tests/test_image.jpg` (base64, no network) |

Run all proxy contract checks:

```bash
./tests/smoke/run_proxy_contract_smoke.sh
```

Reasoning (`reasoning.enabled`) is supported by the API but not covered by smoke: on Qwen3-VL, chain-of-thought usually appears in `message.content` as returned by vLLM.

## Environment

| Variable | Default | Used by |
|----------|---------|---------|
| `CHAT_PROXY_PORT` | `18080` | Proxy URL |
| `VLLM_SERVED_MODEL` | `qwen3-vl-30b-instruct` | Request `model` field |
| `OPENAI_API_KEY` | `dummy` | `Authorization` header |
| `SMOKE_CURL_MAX_TIME` | `300` | Most proxy POSTs |
| `SMOKE_WEB_SEARCH_CURL_MAX_TIME` | `600` | Web search pipeline |
| `SMOKE_VISION_IMAGE_FILE` | `tests/test_image.jpg` | Local image for vision smoke |

## Expected response shapes (summary)

1. **Plain chat:** `object: chat.completion`, `finish_reason: stop`, `message.content` string, no `tool_calls`.
2. **Plain stream:** `text/event-stream` with `chat.completion.chunk` lines and terminal `data: [DONE]`.
2. **Functions:** `finish_reason: tool_calls`, `message.tool_calls[]` with `type: function`, `message.content` null/empty.
3. **Web search:** `finish_reason: stop`, `message.content`, `message.annotations[]` with `type: url_citation`, no `tool_calls`.
4. **Vision:** `finish_reason: stop`, descriptive `message.content` for multimodal input.

On failure, scripts print the raw JSON body to stderr.
