#!/usr/bin/env bash
# Run all chat-proxy contract smoke scripts in order (stack must be up).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_one() {
  local script="$1"
  echo ""
  echo "======== ${script} ========"
  "${SCRIPT_DIR}/${script}"
}

run_one check_proxy_models.sh
run_one check_proxy_plain_chat.sh
run_one check_proxy_stream.sh
run_one check_proxy_function_calling.sh
run_one check_proxy_web_search.sh
run_one check_proxy_vision.sh

echo ""
echo "All proxy contract smoke checks passed."
