#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:9999/v1/generate}"
MODEL_REF="${MODEL_REF:-flux-2-pro}"
PROMPT="${PROMPT:-A detailed photo of a beautiful Swedish 24yo blonde women in a small strappy red crop top smiling taking a phone selfie doing the peace sign with her fingers, she is in an apocalyptic city wasteland and. a nuclear mushroom cloud explosion is rising in the background , 35mm photograph, film, cinematic.}"
NEGATIVE_PROMPT="${NEGATIVE_PROMPT:-blurry, distorted, low quality, artifacts}"
WIDTH="${WIDTH:-1024}"
HEIGHT="${HEIGHT:-1024}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-png}"
SEED="${SEED:-}"
SAFETY_TOLERANCE="${SAFETY_TOLERANCE:-2}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

if [[ $# -gt 0 ]]; then
  PROMPT="$*"
fi

usage() {
  cat <<'USAGE'
Usage:
  scripts/test_bfl_t2i_curl.sh [prompt]

Environment overrides (optional):
  GATEWAY_URL       Default: http://127.0.0.1:8000/v1/generate
  MODEL_REF         Default: flux-2-pro
  PROMPT            Default: cinematic lighthouse prompt
  NEGATIVE_PROMPT   Default: blurry, distorted, low quality, artifacts
  WIDTH             Default: 1024
  HEIGHT            Default: 1024
  OUTPUT_FORMAT     Default: png
  SEED              Default: unset
  SAFETY_TOLERANCE  Default: 2
  TIMEOUT_SECONDS   Default: 300

Examples:
  scripts/test_bfl_t2i_curl.sh
  scripts/test_bfl_t2i_curl.sh "Aerial photo of Sydney Harbour at dawn"
  MODEL_REF=flux-2-pro-preview SEED=42 scripts/test_bfl_t2i_curl.sh
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

PAYLOAD="$({
  MODEL_REF="$MODEL_REF" \
  PROMPT="$PROMPT" \
  NEGATIVE_PROMPT="$NEGATIVE_PROMPT" \
  WIDTH="$WIDTH" \
  HEIGHT="$HEIGHT" \
  OUTPUT_FORMAT="$OUTPUT_FORMAT" \
  SEED="$SEED" \
  SAFETY_TOLERANCE="$SAFETY_TOLERANCE" \
  python3 - <<'PY'
import json
import os

payload = {
    "backend": "bfl",
    "model_ref": os.environ["MODEL_REF"],
    "prompt": os.environ["PROMPT"],
    "negative_prompt": os.environ["NEGATIVE_PROMPT"],
    "width": int(os.environ["WIDTH"]),
    "height": int(os.environ["HEIGHT"]),
    "output_format": os.environ["OUTPUT_FORMAT"],
    "backend_params": {
        "safety_tolerance": int(os.environ["SAFETY_TOLERANCE"]),
    },
}

seed = os.environ.get("SEED", "").strip()
if seed:
    payload["seed"] = int(seed)

print(json.dumps(payload, ensure_ascii=True))
PY
})"

echo "Sending BFL T2I request to ${GATEWAY_URL}..." >&2
RESPONSE="$(curl -sS --fail-with-body \
  -X POST "$GATEWAY_URL" \
  -H "Content-Type: application/json" \
  --max-time "$TIMEOUT_SECONDS" \
  --data "$PAYLOAD")"

RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE"' EXIT
printf '%s\n' "$RESPONSE" > "$RESPONSE_FILE"

python3 - "$RESPONSE_FILE" <<'PY'
import json
import sys

response_file = sys.argv[1]
with open(response_file, "r", encoding="utf-8") as handle:
  data = json.load(handle)

print(json.dumps(data, indent=2))
PY

python3 - "$RESPONSE_FILE" <<'PY'
import json
import sys

response_file = sys.argv[1]
with open(response_file, "r", encoding="utf-8") as handle:
  data = json.load(handle)

job_id = data.get("job_id")
status = data.get("status")
result = data.get("result") or {}
images = result.get("images") or []

print("")
print("Summary:")
print(f"  job_id: {job_id}")
print(f"  status: {status}")
if images:
    first = images[0]
    print(f"  image_url: {first.get('url')}")
    print(f"  local_path: {first.get('local_path')}")
else:
    print("  No images returned.")

if status != "succeeded":
  print(f"  error: {data.get('error')}")
  sys.exit(1)
PY
