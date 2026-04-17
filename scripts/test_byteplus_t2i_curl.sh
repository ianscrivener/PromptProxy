#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:9999/v1/generate}"
MODEL_REF="${MODEL_REF:-ep-20260123162415-2wr9p}"
DEFAULT_REQUEST_PROMPT="A detailed photo of a beautiful Swedish blonde women in a small strappy red crop top smiling at you taking a phone selfie doing the peace sign with her fingers, she is in an apocalyptic city wasteland and. a nuclear mushroom cloud explosion is rising in the background , 35mm photograph, film, cinematic."
REQUEST_PROMPT="${BYTEPLUS_PROMPT:-$DEFAULT_REQUEST_PROMPT}"
SIZE="${SIZE:-2048x2048}"
MODEL_SERIES="${MODEL_SERIES:-seedream45}"
NUM_IMAGES="${NUM_IMAGES:-1}"
SEED="${SEED:-}"
WATERMARK="${WATERMARK:-false}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

if [[ $# -gt 0 ]]; then
  REQUEST_PROMPT="$*"
fi

usage() {
  cat <<'USAGE'
Usage:
  scripts/test_byteplus_t2i_curl.sh [prompt]

Environment overrides (optional):
  GATEWAY_URL     Default: http://127.0.0.1:9999/v1/generate
  MODEL_REF       Default: ep-20260123162415-2wr9p
  BYTEPLUS_PROMPT Default: cinematic mountain village prompt
  SIZE            Default: 2048x2048
  MODEL_SERIES    Default: seedream45 (seedream50|seedream45|seedream40)
  NUM_IMAGES      Default: 1
  SEED            Default: unset
  WATERMARK       Default: false
  TIMEOUT_SECONDS Default: 300

Examples:
  scripts/test_byteplus_t2i_curl.sh
  scripts/test_byteplus_t2i_curl.sh "Portrait photo of a fox in snowfall"
  MODEL_REF=seedream-4-5-250905 MODEL_SERIES=seedream45 SIZE=4704x3520 scripts/test_byteplus_t2i_curl.sh
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

PAYLOAD="$({
  MODEL_REF="$MODEL_REF" \
  REQUEST_PROMPT="$REQUEST_PROMPT" \
  SIZE="$SIZE" \
  MODEL_SERIES="$MODEL_SERIES" \
  NUM_IMAGES="$NUM_IMAGES" \
  SEED="$SEED" \
  WATERMARK="$WATERMARK" \
  python3 - <<'PY'
import json
import os

payload = {
    "backend": "byteplus",
    "model_ref": os.environ["MODEL_REF"],
  "prompt": os.environ["REQUEST_PROMPT"],
    "num_images": int(os.environ["NUM_IMAGES"]),
    "backend_params": {
    "size": os.environ["SIZE"],
        "model_series": os.environ["MODEL_SERIES"],
        "watermark": os.environ["WATERMARK"].strip().lower() in {"1", "true", "yes", "y", "on"},
    },
}

seed = os.environ.get("SEED", "").strip()
if seed:
    payload["seed"] = int(seed)

print(json.dumps(payload, ensure_ascii=True))
PY
})"

echo "Sending BytePlus T2I request to ${GATEWAY_URL}..." >&2
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

raw_response = ((data.get("result") or {}).get("raw_response") or {})
image_data = raw_response.get("data")
if isinstance(image_data, list):
  for image in image_data:
    if isinstance(image, dict):
      b64_json = image.get("b64_json")
      if isinstance(b64_json, str) and b64_json:
        image["b64_json"] = "<redacted base64>"

result_images = ((data.get("result") or {}).get("images") or [])
if isinstance(result_images, list):
  for image in result_images:
    if isinstance(image, dict):
      original_url = image.get("original_url")
      if isinstance(original_url, str) and original_url.startswith("data:image/"):
        image["original_url"] = "<redacted data URL>"

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
