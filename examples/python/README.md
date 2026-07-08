# Python client examples (chat-proxy)

Minimal scripts showing how to call the **OpenAI Chat Completions-compatible** chat-proxy API from Python.

All examples target **chat-proxy** — not vLLM directly.

**Base URL (local default):** `http://localhost:${CHAT_PROXY_PORT:-18080}/v1`  
**Model id:** set via `VLLM_SERVED_MODEL` (see `.env.example`)

For a remote deployment, set `CHAT_PROXY_HOST` and `CHAT_PROXY_PORT` to your operator's public proxy endpoint.

## Setup

```bash
cd examples/python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Environment (optional — defaults work against local chat-proxy):

```bash
export CHAT_PROXY_HOST=localhost
export CHAT_PROXY_PORT=18080
export VLLM_SERVED_MODEL=qwen3-vl-30b-instruct   # match your deployment
export OPENAI_API_KEY=dummy
```

Remote example:

```bash
export CHAT_PROXY_HOST=your-proxy.example.com
export CHAT_PROXY_PORT=443
# Use https in settings.py or set base URL accordingly
```

## Scripts

| Script | Scenario |
|--------|----------|
| `01_list_models.py` | `GET /v1/models` |
| `02_plain_chat.py` | Text chat, non-streaming |
| `03_streaming.py` | Text chat, SSE stream |
| `04_function_calling.py` | Client tools: `tool_calls` + follow-up with `role: tool` |
| `05_web_search.py` | Hosted `web_search` tool + `url_citation` annotations |
| `06_vision.py` | Multimodal `image_url` (local file) |
| `07_reasoning.py` | Optional thinking via `reasoning.enabled` |

Each script prints the **full JSON response** from the API (`response.model_dump()`).  
Streaming (`03_streaming.py`) prints one JSON object per SSE chunk.

Run any script:

```bash
python 02_plain_chat.py
python 06_vision.py /path/to/image.jpg
```

Raw JSON via curl (no SDK). `Authorization` is an OpenAI-client placeholder — chat-proxy does not validate it:

```bash
curl -s "http://localhost:${CHAT_PROXY_PORT:-18080}/v1/chat/completions" \
  -H "Authorization: Bearer dummy" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"${VLLM_SERVED_MODEL:-qwen3-vl-30b-instruct}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hi\"}],\"max_tokens\":32}" \
  | python3 -m json.tool
```

## Notes for API users

- Target **chat-proxy** (`CHAT_PROXY_PORT`), not vLLM (`VLLM_PORT`).
- **Do not** mix `web_search` and `function` tools in one request (`400 conflicting_tools`).
- **Do not** combine `reasoning.enabled` with any `tools` (`400`).
- `web_search` requires `user_location` on the tool object.
- Web search can take several minutes; increase client timeout if needed.
- Streaming is supported for plain chat, functions, reasoning, and web search (web search emits status/citation SSE events before answer tokens).
- Supported API surface: `POST /v1/chat/completions`, `GET /v1/models` only — not the full OpenAI Platform.
- chat-proxy does not enforce `Authorization` headers; `OPENAI_API_KEY` is for SDK compatibility. Use a gateway for authenticated reference deployments.
