#!/usr/bin/env bash
# Smoke: system web_search via chat-proxy — stop, content, url_citation annotations (no tool_calls).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

: "${SMOKE_WEB_SEARCH_CURL_MAX_TIME:=600}"

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
                    "content": (
                        "Use web search: what is the current stable Python release "
                        "version number? Cite sources."
                    ),
                }
            ],
            "tools": [
                {
                    "type": "web_search",
                    "search_context_size": "low",
                    "user_location": {
                        "type": "approximate",
                        "approximate": {
                            "country": "US",
                            "city": "San Francisco",
                            "region": "California",
                            "timezone": "America/Los_Angeles",
                        },
                    },
                }
            ],
            "max_tokens": 1024,
        }
    )
)
PY
)"

echo "POST ${CHAT_PROXY_BASE_URL}/chat/completions (web_search; timeout ${SMOKE_WEB_SEARCH_CURL_MAX_TIME}s)"
response="$(smoke_post_chat "${payload}" "${SMOKE_WEB_SEARCH_CURL_MAX_TIME}")" \
  || smoke_fail "request failed (need vllm + web-search-mcp + searxng healthy)"

if ! python3 -c "
import json
import sys

data = json.loads(sys.argv[1])
choice = (data.get('choices') or [{}])[0]
if choice.get('finish_reason') != 'stop':
    raise SystemExit(f\"expected finish_reason stop, got {choice.get('finish_reason')!r}\")
msg = choice.get('message') or {}
if msg.get('role') != 'assistant':
    raise SystemExit(f\"expected role assistant, got {msg.get('role')!r}\")
content = msg.get('content')
if not isinstance(content, str) or len(content.strip()) < 20:
    raise SystemExit('expected substantial message.content')
if msg.get('tool_calls'):
    raise SystemExit('web_search must not expose tool_calls to the client')
annotations = msg.get('annotations') or []
if not annotations:
    raise SystemExit(
        'expected message.annotations with url_citation (search may have been skipped)'
    )
for i, ann in enumerate(annotations):
    if ann.get('type') != 'url_citation':
        raise SystemExit(f'annotations[{i}] type must be url_citation')
    cite = ann.get('url_citation') or {}
    if not cite.get('url'):
        raise SystemExit(f'annotations[{i}] missing url_citation.url')
print(
    f'OK: web_search — finish_reason=stop, content_len={len(content)}, '
    f'annotations={len(annotations)}'
)
" "${response}"; then
  echo "${response}" >&2
  smoke_fail "web_search response validation"
fi
