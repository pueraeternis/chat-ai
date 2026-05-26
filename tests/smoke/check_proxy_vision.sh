#!/usr/bin/env bash
# Smoke: multimodal image_url via chat-proxy — VL model describes a bundled test image.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

: "${SMOKE_VISION_IMAGE_FILE:=${SCRIPT_DIR}/../test_image.jpg}"

if [[ ! -f "${SMOKE_VISION_IMAGE_FILE}" ]]; then
  smoke_fail "image not found: ${SMOKE_VISION_IMAGE_FILE}"
fi

payload="$(MODEL="${VLLM_SERVED_MODEL}" IMAGE_FILE="${SMOKE_VISION_IMAGE_FILE}" python3 <<'PY'
import base64
import json
import mimetypes
import os
from pathlib import Path

path = Path(os.environ["IMAGE_FILE"])
raw = path.read_bytes()
mime, _ = mimetypes.guess_type(path.name)
if not mime or not mime.startswith("image/"):
    mime = "image/jpeg"
b64 = base64.standard_b64encode(raw).decode("ascii")
data_url = f"data:{mime};base64,{b64}"

print(
    json.dumps(
        {
            "model": os.environ["MODEL"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe this image in one or two sentences. "
                                "Mention the main colors or objects you see."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
            "max_tokens": 256,
            "temperature": 0.2,
        }
    )
)
PY
)"

echo "POST ${CHAT_PROXY_BASE_URL}/chat/completions (vision, image=${SMOKE_VISION_IMAGE_FILE})"
response="$(smoke_post_chat "${payload}" "${SMOKE_CURL_MAX_TIME}")" || smoke_fail "request failed"

if ! python3 -c "
import json
import sys

data = json.loads(sys.argv[1])
choice = (data.get('choices') or [{}])[0]
if choice.get('finish_reason') != 'stop':
    raise SystemExit(f\"expected finish_reason stop, got {choice.get('finish_reason')!r}\")
msg = choice.get('message') or {}
content = msg.get('content')
if not isinstance(content, str) or len(content.strip()) < 15:
    raise SystemExit('expected descriptive non-empty message.content')
lower = content.lower()
if 'error' in lower and 'image' in lower:
    raise SystemExit(f'suspected image error in content: {content[:200]!r}')
print(f'OK: vision — finish_reason=stop, content={content.strip()[:120]!r}...')
" "${response}"; then
  echo "${response}" >&2
  smoke_fail "vision response validation"
fi
