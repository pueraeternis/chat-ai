#!/usr/bin/env bash
# Smoke: GET /v1/models lists served model qwen3-30b-instruct.
set -euo pipefail

BASE_URL="${VLLM_BASE_URL:-http://localhost:${VLLM_PORT:-19000}/v1}"
EXPECTED_ID="${VLLM_SERVED_MODEL:-qwen3-vl-30b-instruct}"

response="$(curl -sfS "${BASE_URL}/models")"
if ! python3 -c "
import json, sys
data = json.loads(sys.argv[1])
ids = {m['id'] for m in data.get('data', [])}
expected = sys.argv[2]
if expected not in ids:
    print(f'expected model id {expected!r}, got {sorted(ids)!r}', file=sys.stderr)
    sys.exit(1)
" "${response}" "${EXPECTED_ID}"; then
  echo "FAIL: /v1/models does not include ${EXPECTED_ID}" >&2
  echo "${response}" >&2
  exit 1
fi

echo "OK: /v1/models includes ${EXPECTED_ID}"
