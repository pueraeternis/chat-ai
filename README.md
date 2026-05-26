# chat-ai

Local GPU stack: **Open WebUI** → **chat-proxy** (OpenAI API) → **vLLM** (Qwen3-VL) and **web-search MCP** (SearXNG + Playwright).

See [docs/INDEX.md](docs/INDEX.md) for documentation.

## Quick start

```bash
cp .env.example .env
# Edit HF_CACHE_ROOT, HF_HUB_CACHE, SEARXNG_SECRET for your machine
docker compose up -d --build
```

Smoke (with stack running):

```bash
./tests/smoke/check_proxy_models.sh
./tests/smoke/check_vllm_tool_calls.sh
```

Development:

```bash
uv sync
uv run pytest
uv run chat-proxy   # local proxy (needs vLLM + MCP URLs in env)
```
