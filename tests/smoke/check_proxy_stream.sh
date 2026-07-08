#!/usr/bin/env bash
# Smoke: plain chat streaming via chat-proxy — SSE deltas and [DONE].
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
            "stream": True,
        }
    )
)
PY
)"

echo "POST ${CHAT_PROXY_BASE_URL}/chat/completions (stream=true)"
response="$(
  curl -sfS -N --max-time "${SMOKE_CURL_MAX_TIME}" \
    "${CHAT_PROXY_BASE_URL}/chat/completions" \
    -H "Authorization: Bearer $(smoke_resolve_api_key)" \
    -H "Content-Type: application/json" \
    -d "${payload}"
)" || smoke_fail "stream request failed (is chat-proxy up?)"

if ! grep -q 'data: \[DONE\]' <<<"${response}"; then
  echo "${response}" >&2
  smoke_fail "missing data: [DONE] in SSE stream"
fi

if ! grep -q 'chat.completion.chunk' <<<"${response}"; then
  echo "${response}" >&2
  smoke_fail "missing chat.completion.chunk in SSE stream"
fi

echo "OK: plain stream — [DONE] and completion chunks present"
