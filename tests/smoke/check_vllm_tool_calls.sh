#!/usr/bin/env bash
# Smoke: chat completion with tools returns finish_reason=tool_calls and tool_calls[].
set -euo pipefail

BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:${VLLM_PORT:-19000}/v1}"
MODEL="${VLLM_SERVED_MODEL:-qwen3-vl-30b-instruct}"
API_KEY="${OPENAI_API_KEY:-dummy}"

payload="$(MODEL="${MODEL}" python3 <<'PY'
import json
import os

print(
    json.dumps(
        {
            "model": os.environ["MODEL"],
            "messages": [
                {
                    "role": "user",
                    "content": "What is the weather in San Francisco? Use the tool.",
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather for a city",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                    "description": "City name",
                                }
                            },
                            "required": ["city"],
                        },
                    },
                }
            ],
            "tool_choice": "auto",
            "max_tokens": 512,
        }
    )
)
PY
)"

response="$(curl -sfS "${BASE_URL}/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "${payload}")"

if ! python3 -c "
import json, sys
data = json.loads(sys.argv[1])
choice = (data.get('choices') or [{}])[0]
msg = choice.get('message') or {}
finish = choice.get('finish_reason')
tool_calls = msg.get('tool_calls') or []
if finish != 'tool_calls':
    print(f'expected finish_reason tool_calls, got {finish!r}', file=sys.stderr)
    sys.exit(1)
if not tool_calls:
    print('expected non-empty message.tool_calls', file=sys.stderr)
    sys.exit(1)
print(f'OK: finish_reason=tool_calls, tool_calls={len(tool_calls)}')
" "${response}"; then
  echo "FAIL: tool-calling smoke" >&2
  echo "${response}" >&2
  exit 1
fi
