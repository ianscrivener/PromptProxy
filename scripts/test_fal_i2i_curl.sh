#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8000/v1/generate}"
MODEL_REF="${MODEL_REF:-fal-ai/flux/dev/image-to-image}"
PROMPT="${PROMPT:-Convert this into a cinematic watercolor scene while preserving composition.}"
NEGATIVE_PROMPT="${NEGATIVE_PROMPT:-blurry, distorted, low quality, artifacts}"
STRENGTH="${STRENGTH:-0.75}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-png}"
SYNC_MODE="${SYNC_MODE:-true}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/test_fal_i2i_curl.sh <source_image_url_or_local_file>

Environment overrides (optional):
  GATEWAY_URL      Default: http://127.0.0.1:8000/v1/generate
  MODEL_REF        Default: fal-ai/flux/dev/image-to-image
  PROMPT           Default: cinematic watercolor transform prompt
  NEGATIVE_PROMPT  Default: blurry, distorted, low quality, artifacts
  STRENGTH         Default: 0.75
  OUTPUT_FORMAT    Default: png
  SYNC_MODE        Default: true
  TIMEOUT_SECONDS  Default: 300

Examples:
  scripts/test_fal_i2i_curl.sh https://example.com/source.jpg
  scripts/test_fal_i2i_curl.sh ./my_source.png
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

SOURCE_INPUT="$1"
SOURCE_IMAGE=""

if [[ "$SOURCE_INPUT" =~ ^https?:// ]]; then
  SOURCE_IMAGE="$SOURCE_INPUT"
elif [[ -f "$SOURCE_INPUT" ]]; then
  MIME_TYPE="$(file -b --mime-type "$SOURCE_INPUT")"
  BASE64_DATA="$(base64 < "$SOURCE_INPUT" | tr -d '\n')"
  SOURCE_IMAGE="data:${MIME_TYPE};base64,${BASE64_DATA}"
else
  echo "Error: source must be an HTTP(S) URL or an existing local file." >&2
  exit 1
fi

PAYLOAD="$({
  SOURCE_IMAGE="$SOURCE_IMAGE" \
  MODEL_REF="$MODEL_REF" \
  PROMPT="$PROMPT" \
  NEGATIVE_PROMPT="$NEGATIVE_PROMPT" \
  STRENGTH="$STRENGTH" \
  OUTPUT_FORMAT="$OUTPUT_FORMAT" \
  SYNC_MODE="$SYNC_MODE" \
  python3 - <<'PY'
import json
import os

payload = {
    "backend": "fal",
    "model_ref": os.environ["MODEL_REF"],
    "prompt": os.environ["PROMPT"],
    "negative_prompt": os.environ["NEGATIVE_PROMPT"],
    "output_format": os.environ["OUTPUT_FORMAT"],
    "i2i": {
        "source_image": os.environ["SOURCE_IMAGE"],
        "strength": float(os.environ["STRENGTH"]),
    },
    "backend_params": {
      "sync_mode": os.environ["SYNC_MODE"].strip().lower() in {"1", "true", "yes", "y", "on"}
    },
}
print(json.dumps(payload, ensure_ascii=True))
PY
})"

echo "Sending I2I request to ${GATEWAY_URL}..." >&2
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
