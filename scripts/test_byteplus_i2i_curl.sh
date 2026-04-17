#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:9999/v1/generate}"
MODEL_REF="${MODEL_REF:-ep-20260123162415-2wr9p}"
DEFAULT_REQUEST_PROMPT="A detailed photo of a beautiful Swedish blonde women in a small strappy red crop top smiling at you taking a phone selfie doing the peace sign with her fingers, she is in an apocalyptic city wasteland and. a nuclear mushroom cloud explosion is rising in the background , 35mm photograph, film, cinematic."
REQUEST_PROMPT="${BYTEPLUS_PROMPT:-$DEFAULT_REQUEST_PROMPT}"
IMAGE_PATH="${IMAGE_PATH:-image_ref.png}"
SIZE="${SIZE:-2048x2048}"
MODEL_SERIES="${MODEL_SERIES:-}"
NUM_IMAGES="${NUM_IMAGES:-1}"
SEED="${SEED:-}"
WATERMARK="${WATERMARK:-false}"
STRENGTH="${STRENGTH:-}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

if [[ $# -gt 0 ]]; then
  REQUEST_PROMPT="$*"
fi

usage() {
  cat <<'USAGE'
Usage:
  scripts/test_byteplus_i2i_curl.sh [prompt]

Environment overrides (optional):
  GATEWAY_URL     Default: http://127.0.0.1:9999/v1/generate
  MODEL_REF       Default: ep-20260123162415-2wr9p
  BYTEPLUS_PROMPT Default: same default prompt as the T2I script
  IMAGE_PATH      Default: image_ref.png
  SIZE            Default: 2048x2048
  MODEL_SERIES    Default: unset (set only for Seedream size snapping)
  NUM_IMAGES      Default: 1
  SEED            Default: unset
  WATERMARK       Default: false
  STRENGTH        Default: unset (optional i2i strength)
  TIMEOUT_SECONDS Default: 300

Examples:
  scripts/test_byteplus_i2i_curl.sh
  IMAGE_PATH=./image_ref.png MODEL_REF=seedream-4-0-250828 SIZE=1024x1024 MODEL_SERIES=seedream40 scripts/test_byteplus_i2i_curl.sh
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -f "$IMAGE_PATH" ]]; then
  echo "Image file not found: $IMAGE_PATH" >&2
  exit 1
fi

PAYLOAD_FILE="$(mktemp)"

{
  MODEL_REF="$MODEL_REF" \
  REQUEST_PROMPT="$REQUEST_PROMPT" \
  IMAGE_PATH="$IMAGE_PATH" \
  SIZE="$SIZE" \
  MODEL_SERIES="$MODEL_SERIES" \
  NUM_IMAGES="$NUM_IMAGES" \
  SEED="$SEED" \
  WATERMARK="$WATERMARK" \
  STRENGTH="$STRENGTH" \
  python3 - <<'PY'
import base64
import json
import mimetypes
import os
from pathlib import Path

path = Path(os.environ["IMAGE_PATH"]).expanduser().resolve()
raw = path.read_bytes()

mime_type, _ = mimetypes.guess_type(path.name)
if mime_type is None:
    mime_type = "image/png"

# BytePlus requires lowercase format in data URI.
mime_type = mime_type.lower()
image_b64 = base64.b64encode(raw).decode("ascii")
image_data_uri = f"data:{mime_type};base64,{image_b64}"

backend_params = {
    "size": os.environ["SIZE"],
    "watermark": os.environ["WATERMARK"].strip().lower() in {"1", "true", "yes", "y", "on"},
}

model_series = os.environ.get("MODEL_SERIES", "").strip()
if model_series:
    backend_params["model_series"] = model_series

payload = {
    "backend": "byteplus",
    "model_ref": os.environ["MODEL_REF"],
    "prompt": os.environ["REQUEST_PROMPT"],
    "num_images": int(os.environ["NUM_IMAGES"]),
    "i2i": {
        "source_image": image_data_uri,
    },
    "backend_params": backend_params,
}

seed = os.environ.get("SEED", "").strip()
if seed:
    payload["seed"] = int(seed)

strength = os.environ.get("STRENGTH", "").strip()
if strength:
    payload["i2i"]["strength"] = float(strength)

print(json.dumps(payload, ensure_ascii=True))
PY
} > "$PAYLOAD_FILE"

echo "Sending BytePlus I2I request to ${GATEWAY_URL}..." >&2
RESPONSE="$(curl -sS --fail-with-body \
  -X POST "$GATEWAY_URL" \
  -H "Content-Type: application/json" \
  --max-time "$TIMEOUT_SECONDS" \
  --data-binary "@$PAYLOAD_FILE")"

RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE"' EXIT
printf '%s\n' "$RESPONSE" > "$RESPONSE_FILE"

python3 - "$RESPONSE_FILE" <<'PY'
import json
import sys

response_file = sys.argv[1]
with open(response_file, "r", encoding="utf-8") as handle:
  data = json.load(handle)

request_i2i = ((data.get("request") or {}).get("i2i") or {})
if isinstance(request_i2i, dict):
  source_image = request_i2i.get("source_image")
  if isinstance(source_image, str) and source_image.startswith("data:image/"):
    request_i2i["source_image"] = "<redacted data URL>"

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
