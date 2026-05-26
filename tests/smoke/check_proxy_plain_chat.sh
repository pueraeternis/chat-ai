#!/usr/bin/env bash
# Smoke: plain chat via chat-proxy — OpenAI chat.completion shape, stop + assistant content.
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
                    "content": "Reply with exactly one word: ok",
                }
            ],
            "max_tokens": 64,
            "temperature": 0,
        }
    )
)
PY
)"

echo "POST ${CHAT_PROXY_BASE_URL}/chat/completions (plain chat)"
response="$(smoke_post_chat "${payload}")" || smoke_fail "request failed (is chat-proxy up?)"

if ! python3 -c "
import json
import sys

data = json.loads(sys.argv[1])
if data.get('object') != 'chat.completion':
    raise SystemExit(f\"expected object chat.completion, got {data.get('object')!r}\")
if not data.get('model'):
    raise SystemExit('missing model')
choices = data.get('choices') or []
if len(choices) != 1:
    raise SystemExit(f'expected 1 choice, got {len(choices)}')
choice = choices[0]
if choice.get('finish_reason') != 'stop':
    raise SystemExit(f\"expected finish_reason stop, got {choice.get('finish_reason')!r}\")
msg = choice.get('message') or {}
if msg.get('role') != 'assistant':
    raise SystemExit(f\"expected role assistant, got {msg.get('role')!r}\")
content = msg.get('content')
if not isinstance(content, str) or not content.strip():
    raise SystemExit('expected non-empty message.content string')
if msg.get('tool_calls'):
    raise SystemExit('plain chat must not return tool_calls')
print(f'OK: plain chat — finish_reason=stop, content={content.strip()!r}')
" "${response}"; then
  echo "${response}" >&2
  smoke_fail "plain chat response validation"
fi
