# Shared helpers for chat-proxy smoke scripts. Source from other scripts:
#   source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

: "${CHAT_PROXY_BASE_URL:=http://localhost:${CHAT_PROXY_PORT:-18080}/v1}"
: "${VLLM_SERVED_MODEL:=qwen3-vl-30b-instruct}"
: "${OPENAI_API_KEY:=dummy}"
: "${SMOKE_CURL_MAX_TIME:=300}"

smoke_fail() {
  echo "FAIL: $*" >&2
  exit 1
}

smoke_post_chat() {
  local payload="$1"
  local max_time="${2:-$SMOKE_CURL_MAX_TIME}"
  curl -sfS --max-time "$max_time" \
    "${CHAT_PROXY_BASE_URL}/chat/completions" \
    -H "Authorization: Bearer ${OPENAI_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}
