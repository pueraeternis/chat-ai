#!/usr/bin/env bash
# Smoke: client function tools via chat-proxy — tool_calls, content null, finish_reason tool_calls.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

payload="$(MODEL="${VLLM_SERVED_MODEL}" python3 <<'PY'
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

echo "POST ${CHAT_PROXY_BASE_URL}/chat/completions (function calling)"
response="$(smoke_post_chat "${payload}")" || smoke_fail "request failed"

if ! python3 -c "
import json
import sys

data = json.loads(sys.argv[1])
choice = (data.get('choices') or [{}])[0]
finish = choice.get('finish_reason')
msg = choice.get('message') or {}
tool_calls = msg.get('tool_calls') or []
if finish != 'tool_calls':
    raise SystemExit(f'expected finish_reason tool_calls, got {finish!r}')
if not tool_calls:
    raise SystemExit('expected non-empty message.tool_calls')
tc0 = tool_calls[0]
if tc0.get('type') != 'function':
    raise SystemExit(f\"expected tool_call type function, got {tc0.get('type')!r}\")
fn = (tc0.get('function') or {}).get('name')
if fn != 'get_weather':
    raise SystemExit(f'expected function name get_weather, got {fn!r}')
args = (tc0.get('function') or {}).get('arguments')
if not isinstance(args, str) or not args.strip():
    raise SystemExit('expected non-empty function.arguments JSON string')
content = msg.get('content')
if content is not None and content != '':
    raise SystemExit(f'expected message.content null or empty, got {content!r}')
print(f'OK: function calling — finish_reason=tool_calls, tool={fn!r}, id={tc0.get(\"id\")!r}')
" "${response}"; then
  echo "${response}" >&2
  smoke_fail "function calling response validation"
fi
