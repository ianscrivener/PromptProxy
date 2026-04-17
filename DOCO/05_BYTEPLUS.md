# BytePlus ModelArk — Image Inference API Reference

> Base URL: `https://ark.ap-southeast.bytepluses.com/api/v3`  
> Auth: `Authorization: Bearer $ARK_API_KEY`  
> Pattern: OpenAI-compatible REST (`/images/generations`)  
> SDK: `byteplussdkarkruntime` (Python), `openai` (compatible)  
> Docs: `https://docs.byteplus.com/en/docs/ModelArk`

---

## Architecture

BytePlus ModelArk is ByteDance's cloud AI platform (the international-facing counterpart to Volcano Engine). It uses an **OpenAI-compatible** image generation API at `/api/v3/images/generations`. 

Two image product families:
- **Seedream** — T2I; multimodal (text + image inputs), multi-reference
- **SeedEdit** — I2I; text-instructed image editing (portrait, background, lighting, viewpoint)

Rate limit: 500 images per minute (IPM) for Seedream 4.0+.

### PromptProxy integration notes

PromptProxy uses a size-only BytePlus request path:

- Requests are sent directly to `/api/v3/images/generations` via HTTP JSON.
- PromptProxy uses `backend_params.size` and does not build upstream BytePlus payloads from request `width` or `height`.
- For Seedream model series (`seedream50`, `seedream45`, `seedream40`), allowed size pairs are loaded from `seedream-allowed-sizes.json`.
- If a custom size is not an exact allowed pair, PromptProxy snaps to the nearest allowed size while preserving orientation.

BytePlus smoke test script notes:

- Script: `scripts/test_byteplus_t2i_curl.sh`
- Prompt env var: `BYTEPLUS_PROMPT` (not `PROMPT`)
- Common overrides: `MODEL_REF`, `MODEL_SERIES`, `SIZE`, `NUM_IMAGES`, `WATERMARK`, `TIMEOUT_SECONDS`

BytePlus I2I smoke test script notes:

- Script: `scripts/test_byteplus_i2i_curl.sh`
- Default source image: `image_ref.png` (override via `IMAGE_PATH`)
- Default prompt source: `BYTEPLUS_PROMPT` (falls back to the same default prompt text used by the T2I script)
- Common overrides: `MODEL_REF`, `SIZE`, `MODEL_SERIES`, `NUM_IMAGES`, `SEED`, `WATERMARK`, `STRENGTH`, `TIMEOUT_SECONDS`
- Payload behavior: local file is converted to `data:image/<format>;base64,...` before gateway submission

---

## Text-to-Image (T2I)

### Endpoint

```
POST https://ark.ap-southeast.bytepluses.com/api/v3/images/generations
```

### T2I Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | string | **required** | Model ID (see table below) |
| `prompt` | string | **required** | Text description of the image (recommended under 600 English words) |
| `image` | string | null | URL or base64 of reference image (for multi-image modes) |
| `size` | string | `"2K"` | `"1K"`, `"2K"`, `"4K"`, `"adaptive"`, or custom `"<width>x<height>"` |
| `n` | integer | 1 | Number of images to generate |
| `response_format` | string | `"url"` | `"url"` or `"b64_json"` |
| `seed` | integer | null | Fixed seed for reproducibility |
| `watermark` | boolean | false | Add ByteDance watermark |
| `stream` | boolean | false | Streaming response |
| `sequential_image_generation` | string | `"disabled"` | Use `"auto"` for related image batches; use `"disabled"` for single-image generation |
| `guidance_scale` | float | model default | Prompt adherence (SeedEdit: 5.5 typical) |

### Sequential and Single Image Modes (Seedream)

The following mode guidance applies to:

- `seedream-5-0-litenew`
- `seedream-4-5`
- `seedream-4-0`

Set `sequential_image_generation` as follows:

- `"auto"`: generate related images in sequence (batch behavior)
- `"disabled"`: generate a single image

Mode matrix:

| Scenario | Required Inputs | Output Limit | `sequential_image_generation` |
|----------|------------------|--------------|-------------------------------|
| Generate a batch of related images from multiple reference images + prompt | `image` array with 2-14 references + `prompt` | Input refs + output images must be `<= 15` | `"auto"` |
| Generate a batch of related images from a single reference image + prompt | `image` (single) + `prompt` | Up to 14 output images | `"auto"` |
| Generate a batch of related images from text only | `prompt` | Up to 15 output images | `"auto"` |
| Generate a single image from multiple reference images + prompt | `image` array with 2-14 references + `prompt` | Exactly 1 output image | `"disabled"` |
| Generate a single image from a single reference image + prompt | `image` (single) + `prompt` | Exactly 1 output image | `"disabled"` |
| Generate a single image from text only | `prompt` | Exactly 1 output image | `"disabled"` |

Practical request fields:

- Set `n` to your desired output count.
- For related-image batches, use `sequential_image_generation: "auto"`.
- For single-image requests, set `n: 1` and `sequential_image_generation: "disabled"`.

### T2I Request (curl)

```bash
curl -X POST \
  https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seedream-5-0-t2i-250624",
    "prompt": "Aerial view of a lake at sunrise, photorealistic, cinematic lighting",
    "size": "2K",
    "n": 1,
    "response_format": "url",
    "watermark": false
  }'
```

### T2I Request (Related batch from text prompt)

```bash
curl -X POST \
  https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seedream-4-5",
    "prompt": "A character turnaround sheet in consistent style",
    "n": 8,
    "sequential_image_generation": "auto",
    "size": "2K",
    "response_format": "url"
  }'
```

### T2I Request (Python SDK)

```python
import os
from byteplussdkarkruntime import Ark

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

response = client.images.generate(
    model="seedream-5-0-t2i-250624",
    prompt="A vibrant coral reef, underwater photography, 4K",
    size="2K",
    n=1,
    response_format="url",
    watermark=False
)

print(response.data[0].url)
```

### T2I Request (OpenAI-compatible Python)

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("ARK_API_KEY"),
    base_url="https://ark.ap-southeast.bytepluses.com/api/v3"
)

response = client.images.generate(
    model="seedream-4-0-250828",
    prompt="A serene mountain lake at dawn",
    size="2K"
)
print(response.data[0].url)
```

### T2I Request (Single image from multiple references + prompt)

```python
response = client.images.generate(
  model="seedream-4-0",
  prompt="Blend the subject style from all references into one hero image",
  image=[
    "https://example.com/ref-1.jpg",
    "https://example.com/ref-2.jpg",
    "https://example.com/ref-3.jpg"
  ],
  n=1,
  sequential_image_generation="disabled",
  size="2K"
)
print(response.data[0].url)
```

### T2I Response Schema

```json
{
  "data": [
    {
      "url": "https://ark-img.tos-ap-southeast-1.bytepluses.com/...",
      "b64_json": null
    }
  ],
  "created": 1744600000
}
```

---

## Image-to-Image (I2I) — SeedEdit

SeedEdit is BytePlus's dedicated image editing model. It excels at portrait editing, background changes, lighting/viewpoint transforms.

### Endpoint

Same as T2I:
```
POST https://ark.ap-southeast.bytepluses.com/api/v3/images/generations
```

### I2I Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | string | **required** | SeedEdit model ID |
| `prompt` | string | **required** | Edit instruction (recommended under 600 English words) |
| `image` | string or string[] | **required** | URL/base64 source image; `seedream-5-0-lite`, `seedream-4-5`, and `seedream-4-0` support single or multiple images |
| `size` | string | `"adaptive"` | `"adaptive"` preserves input dimensions; supports `"1K"`, `"2K"`, `"4K"`, and custom `"<width>x<height>"` |
| `seed` | integer | null | Reproducibility |
| `guidance_scale` | float | 5.5 | How closely to follow the edit prompt |
| `watermark` | boolean | true | Add watermark |
| `response_format` | string | `"url"` | `"url"` or `"b64_json"` |

### Image Input Requirements (`image`)

Input form:

- URL: must be publicly accessible by BytePlus.
- Base64: must use `data:image/<format>;base64,<payload>`.
- `<format>` must be lowercase (for example `data:image/png;base64,...`).

Supported formats:

- Baseline support: `JPEG`, `PNG`.
- Additional formats for `seedream-5-0-lite`, `seedream-4-5`, and `seedream-4-0`: `WEBP`, `BMP`, `TIFF`, `GIF`.

Limits and constraints:

| Constraint | `seedream-5-0-lite` / `seedream-4-5` / `seedream-4-0` | `seededit-3-0-i2i` / `seededit-3-0-t2i` |
|-----------|----------------------------------------------------------|-------------------------------------------|
| Aspect ratio (`width / height`) | `[1/16, 16]` | `[1/3, 3]` |
| Width and height | `> 14 px` | `> 14 px` |
| File size | `<= 10 MB` | `<= 10 MB` |
| Pixel count per image | `<= 6000 x 6000 = 36,000,000` | `<= 6000 x 6000 = 36,000,000` |
| Max reference images | Up to `14` | Up to `14` |

Notes:

- The pixel limit is on the product `width * height`, not on either dimension independently.
- For multi-reference workflows, keep `input_image_count + output_image_count <= 15` when using related-sequence generation.

### I2I Request (curl)

```bash
curl -X POST \
  https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seededit-3-0-i2i-250628",
    "prompt": "Make the background a tropical beach",
    "image": "https://example.com/portrait.jpg",
    "response_format": "url",
    "size": "adaptive",
    "seed": 42,
    "guidance_scale": 5.5,
    "watermark": false
  }'
```

### I2I Request via PromptProxy test script

```bash
scripts/test_byteplus_i2i_curl.sh
```

With overrides:

```bash
IMAGE_PATH=./image_ref.png \
MODEL_REF=ep-20260123162415-2wr9p \
SIZE=2048x2048 \
BYTEPLUS_PROMPT="Make the background a tropical beach" \
scripts/test_byteplus_i2i_curl.sh
```

Practical note for PromptProxy smoke tests:

- Some BytePlus endpoints reject `size: "adaptive"` for specific I2I routes and enforce a minimum pixel count.
- The current script default `SIZE=2048x2048` is chosen to satisfy those stricter endpoint validations.

### I2I Request (Python SDK)

```python
from byteplussdkarkruntime import Ark
import byteplus, os

client = Ark(api_key=os.environ.get("ARK_API_KEY"))

response = client.images.generate(
    model="seededit-3-0-i2i-250628",
    prompt="Make the bubbles heart-shaped",
    image="https://ark-doc.tos-ap-southeast-1.bytepluses.com/seededit_i2i.jpeg",
    response_format="url",
    size="adaptive",
    seed=123,
    guidance_scale=5.5,
    watermark=True
)

print(response.data[0].url)
```

---

## Multi-Image Input (Seedream 4.0+)

`seedream-5-0-lite`, `seedream-4-5`, and `seedream-4-0` natively support multiple reference images for subject-consistent generation.

Pass multiple images as an array:

```python
response = client.images.generate(
    model="seedream-4-0-250828",
    prompt="The person from image 1 wearing the outfit from image 2, in a park",
    image=[
        "https://example.com/person.jpg",
        "https://example.com/outfit.jpg"
    ],
    size="2K"
)
```

Up to **14 reference images** supported.

---

## Available Models

### T2I — Seedream Family

| Model ID | Version | Resolution | Notes |
|----------|---------|-----------|-------|
| `seedream-5-0-litenew` | Seedream 5.0 Lite New | 1K-2K | Supports sequence generation mode (`sequential_image_generation`) |
| `seedream-5-0-t2i-250624` | Seedream 5.0 | 1K–4K | Latest; reasoning + editing |
| `seedream-5-0-lite-t2i-250624` | Seedream 5.0 Lite | 1K–2K | Faster, lighter |
| `seedream-4-5-250905` | Seedream 4.5 | 1K–4K | Improved from 4.0; stronger editing |
| `seedream-4-0-250828` | Seedream 4.0 | 1K–4K | Multi-image fusion creation |
| `seedream-3-0-t2i-250228` | Seedream 3.0 | 1K–2K | Stable baseline |

### I2I — SeedEdit Family

| Model ID | Version | Notes |
|----------|---------|-------|
| `seededit-3-0-i2i-250628` | SeedEdit 3.0 | Portrait, background, lighting |
| `seededit-2-0-i2i` | SeedEdit 2.0 | Previous generation |

---

## Size Reference

| Size Key | Approximate Output |
|----------|--------------------|
| `"1K"` | ~1280×720 to 1024×1024 |
| `"2K"` | ~1920×1080 to 2048×2048 |
| `"4K"` | ~3840×2160 to 4096×4096 |
| `"adaptive"` | Matches input image dimensions (I2I) |
| `"<width>x<height>"` | Explicit custom size (for example `1664x2496`) |

Total output pixel range: 1280×720 to 4096×4096.

---

## Pricing (approx.)

| Model | Cost |
|-------|------|
| Seedream 4.0 | $0.03 / image |
| Seedream 4.5 | $0.045 / image |
| Seedream 5.0 | $0.035 / image |
| SeedEdit 3.0 | Per image (see docs) |

---

## Notes

- API is OpenAI-compatible — standard OpenAI Python/JS SDK works with `base_url` override
- Keep prompts under 600 English words to reduce detail loss from overlong prompts
- For `seedream-5-0-litenew`, `seedream-4-5`, and `seedream-4-0`, use `sequential_image_generation: "auto"` for related-image batches
- Use `sequential_image_generation: "disabled"` for single-image generation
- `size: "adaptive"` for SeedEdit preserves the input image's original aspect ratio and resolution
- In PromptProxy, prefer `backend_params.size` and optional `backend_params.model_series` for deterministic Seedream size normalization
- In PromptProxy scripts, use `BYTEPLUS_PROMPT`; avoid using shell `PROMPT` as an input variable
- `guidance_scale` in SeedEdit controls edit strength — lower = more conservative changes
- Rate limit is 500 images/minute; no charge for failed generations
- `eu-west-1` region supports `seed-2-0` and `seedream-5-0-lite` only; all models in `ap-southeast-1`
