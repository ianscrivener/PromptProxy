#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8000/v1/generate}"
MODEL_REF="${MODEL_REF:-fal-ai/flux/dev}"
PROMPT="${PROMPT:-A detailed photo of a beautiful Swedish 24yo blonde women in a small strappy red crop top smiling taking a phone selfie doing the peace sign with her fingers, she is in an apocalyptic city wasteland and. a nuclear mushroom cloud explosion is rising in the background , 35mm photograph, film, cinematic.}"
NEGATIVE_PROMPT="${NEGATIVE_PROMPT:-blurry, distorted, low quality, artifacts}"
ASPECT_RATIO="${ASPECT_RATIO:-1:1}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-png}"
NUM_IMAGES="${NUM_IMAGES:-1}"
SEED="${SEED:-}"
SYNC_MODE="${SYNC_MODE:-true}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

if [[ $# -gt 0 ]]; then
  PROMPT="$*"
fi

usage() {
  cat <<'USAGE'
Usage:
  scripts/test_fal_t2i_curl.sh [prompt]

Environment overrides (optional):
  GATEWAY_URL      Default: http://127.0.0.1:8000/v1/generate
  MODEL_REF        Default: fal-ai/flux/dev
  PROMPT           Default: A detailed photo of a beautiful Swedish 24yo blonde women in a small strappy red crop top smiling taking a phone selfie doing the peace sign with her fingers, she is in an apocalyptic city wasteland and. a nuclear mushroom cloud explosion is rising in the background , 35mm photograph, film, cinematic.
  NEGATIVE_PROMPT  Default: blurry, distorted, low quality, artifacts
  ASPECT_RATIO     Default: 1:1
  OUTPUT_FORMAT    Default: png
  NUM_IMAGES       Default: 1
  SEED             Default: unset
  SYNC_MODE        Default: true
  TIMEOUT_SECONDS  Default: 300

Examples:
  scripts/test_fal_t2i_curl.sh
  scripts/test_fal_t2i_curl.sh "Portrait photo of a red fox in snowfall"
  SEED=42 ASPECT_RATIO=16:9 scripts/test_fal_t2i_curl.sh
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
  ASPECT_RATIO="$ASPECT_RATIO" \
  OUTPUT_FORMAT="$OUTPUT_FORMAT" \
  NUM_IMAGES="$NUM_IMAGES" \
  SEED="$SEED" \
  SYNC_MODE="$SYNC_MODE" \
  python3 - <<'PY'
import json
import os

payload = {
    "backend": "fal",
    "model_ref": os.environ["MODEL_REF"],
    "prompt": os.environ["PROMPT"],
    "negative_prompt": os.environ["NEGATIVE_PROMPT"],
    "aspect_ratio": os.environ["ASPECT_RATIO"],
    "output_format": os.environ["OUTPUT_FORMAT"],
    "num_images": int(os.environ["NUM_IMAGES"]),
    "backend_params": {
      "sync_mode": os.environ["SYNC_MODE"].strip().lower() in {"1", "true", "yes", "y", "on"}
    },
}

seed = os.environ.get("SEED", "").strip()
if seed:
    payload["seed"] = int(seed)

print(json.dumps(payload, ensure_ascii=True))
PY
})"

echo "Sending T2I request to ${GATEWAY_URL}..." >&2
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

# Avoid dumping megabytes of inline base64 to the terminal.
raw_response = ((data.get("result") or {}).get("raw_response") or {})
images = raw_response.get("images")
if isinstance(images, list):
  for image in images:
    if isinstance(image, dict):
      url = image.get("url")
      if isinstance(url, str) and url.startswith("data:image/"):
        image["url"] = "<redacted data URL>"

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
