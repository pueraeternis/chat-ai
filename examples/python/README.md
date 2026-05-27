# Python client examples (chat-proxy)

Minimal scripts showing how to call the **OpenAI-compatible** chat-proxy API from Python.

**Base URL (production):** `http://<host>:19000/v1`  
**Model id (production):** `qwen3-vl-235b-instruct`

## Setup

```bash
cd examples/python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Environment (optional — defaults work against local/prod proxy):

```bash
export CHAT_PROXY_HOST=172.16.20.25   # or localhost
export CHAT_PROXY_PORT=19000
export VLLM_SERVED_MODEL=qwen3-vl-235b-instruct
export OPENAI_API_KEY=dummy
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

Raw JSON via curl (no SDK):

```bash
curl -s http://localhost:18080/v1/chat/completions \
  -H "Authorization: Bearer dummy" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-vl-30b-instruct","messages":[{"role":"user","content":"Say hi"}],"max_tokens":32}' \
  | python3 -m json.tool
```

## Notes for API users

- **Do not** mix `web_search` and `function` tools in one request (`400 conflicting_tools`).
- **Do not** combine `reasoning.enabled` with any `tools` (`400`).
- `web_search` requires `user_location` on the tool object.
- Web search can take several minutes; increase client timeout if needed.
- Streaming is supported for plain chat, functions, reasoning, and web search (web search emits status/citation SSE events before answer tokens).
