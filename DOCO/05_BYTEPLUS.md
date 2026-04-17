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
| `prompt` | string | **required** | Text description of the image |
| `image` | string | null | URL or base64 of reference image (for multi-image modes) |
| `size` | string | `"2K"` | `"1K"`, `"2K"`, `"4K"`, `"adaptive"`, or custom `"<width>x<height>"` |
| `n` | integer | 1 | Number of images to generate |
| `response_format` | string | `"url"` | `"url"` or `"b64_json"` |
| `seed` | integer | null | Fixed seed for reproducibility |
| `watermark` | boolean | false | Add ByteDance watermark |
| `stream` | boolean | false | Streaming response |
| `sequential_image_generation` | string | `"disabled"` | `"enabled"` to generate a consistent image set |
| `guidance_scale` | float | model default | Prompt adherence (SeedEdit: 5.5 typical) |

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
| `prompt` | string | **required** | Edit instruction |
| `image` | string | **required** | URL or base64 of source image |
| `size` | string | `"adaptive"` | `"adaptive"` preserves input dimensions; supports `"1K"`, `"2K"`, `"4K"`, and custom `"<width>x<height>"` |
| `seed` | integer | null | Reproducibility |
| `guidance_scale` | float | 5.5 | How closely to follow the edit prompt |
| `watermark` | boolean | true | Add watermark |
| `response_format` | string | `"url"` | `"url"` or `"b64_json"` |

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

Seedream 4.0 and later natively support multiple reference images for subject-consistent generation.

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

Up to **10 reference images** supported (Seedream 4.0+).

---

## Available Models

### T2I — Seedream Family

| Model ID | Version | Resolution | Notes |
|----------|---------|-----------|-------|
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
- `sequential_image_generation: "enabled"` creates a thematically consistent image set (like a storyboard)
- `size: "adaptive"` for SeedEdit preserves the input image's original aspect ratio and resolution
- In PromptProxy, prefer `backend_params.size` and optional `backend_params.model_series` for deterministic Seedream size normalization
- In PromptProxy scripts, use `BYTEPLUS_PROMPT`; avoid using shell `PROMPT` as an input variable
- `guidance_scale` in SeedEdit controls edit strength — lower = more conservative changes
- Rate limit is 500 images/minute; no charge for failed generations
- `eu-west-1` region supports `seed-2-0` and `seedream-5-0-lite` only; all models in `ap-southeast-1`
