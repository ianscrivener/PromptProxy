# Black Forest Labs (BFL) — Image Inference API Reference

> Base URL: `https://api.bfl.ai/v1`  
> Regional: `https://api.eu.bfl.ai/v1` | `https://api.us.bfl.ai/v1`  
> Auth: `x-key: YOUR_BFL_API_KEY`  
> Pattern: REST async — POST to create, poll `polling_url` for result  
> Docs: `https://docs.bfl.ai`

---

## Architecture

BFL uses an **asynchronous two-step pattern**:

1. **POST** to endpoint → receive `{id, polling_url}`
2. **GET** `polling_url` repeatedly → check `status` field until `"Ready"`

Result URLs (`result.sample`) are signed, served from delivery CDN, and **expire in 10 minutes**. Download immediately.

All FLUX.2 models natively handle both T2I and I2I in a single architecture — no separate endpoint needed.

---

## Text-to-Image (T2I)

### Endpoint

```
POST https://api.bfl.ai/v1/{model-name}
```

### T2I Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Image description (2–2000 chars recommended) |
| `width` | integer | 1024 | Output width in pixels |
| `height` | integer | 1024 | Output height in pixels |
| `seed` | integer | null | Fixed seed for reproducibility |
| `output_format` | string | `"jpeg"` | `"jpeg"` or `"png"` |
| `safety_tolerance` | integer | 2 | Content moderation: 0 (strict) → 6 (permissive) |
| `prompt_upsampling` | boolean | false | Auto-enhance/expand prompt before generation |
| `num_inference_steps` | integer | model default | Steps — only applicable on `flux-2-flex` and `flux-2-dev` |
| `guidance_scale` | float | model default | CFG — only on `flux-2-flex` and `flux-2-dev` |
| `raw` | boolean | false | Natural, less-processed output (flux-1.1-pro-ultra) |
| `aspect_ratio` | string | null | e.g., `"16:9"`, `"4:3"` — used on Ultra instead of width/height |

### Example Request (bash)

```bash
request=$(curl -s -X POST https://api.bfl.ai/v1/flux-2-pro \
  -H "x-key: $BFL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Aerial photograph of Lake Macquarie at golden hour, NSW Australia, ultra-detailed, dramatic light",
    "width": 1440,
    "height": 960,
    "output_format": "jpeg",
    "safety_tolerance": 2,
    "prompt_upsampling": false
  }')

polling_url=$(echo $request | jq -r .polling_url)

# Poll until ready
while true; do
  sleep 0.5
  result=$(curl -s -X GET "$polling_url" -H "x-key: $BFL_API_KEY")
  status=$(echo $result | jq -r .status)
  if [ "$status" = "Ready" ]; then
    echo "Image URL: $(echo $result | jq -r .result.sample)"
    break
  fi
done
```

### Example Request (Python)

```python
import requests, time

API_KEY = "your-key-here"
BASE_URL = "https://api.bfl.ai/v1"

# Submit
resp = requests.post(
    f"{BASE_URL}/flux-2-pro",
    headers={"x-key": API_KEY},
    json={
        "prompt": "A serene lake at sunrise, photorealistic",
        "width": 1024,
        "height": 1024,
        "output_format": "jpeg"
    }
)
polling_url = resp.json()["polling_url"]

# Poll
while True:
    result = requests.get(polling_url, headers={"x-key": API_KEY}).json()
    if result["status"] == "Ready":
        print(result["result"]["sample"])  # signed image URL
        break
    elif result["status"] in ("Error", "Failed"):
        raise Exception(result)
    time.sleep(0.5)
```

### T2I Response Schema

Initial POST response:
```json
{
  "id": "abc123",
  "polling_url": "https://api.bfl.ai/v1/get_result?id=abc123"
}
```

Poll response when `status == "Ready"`:
```json
{
  "id": "abc123",
  "status": "Ready",
  "result": {
    "sample": "https://delivery-eu.bfl.ai/...signed-url.jpg"
  }
}
```

---

## Image-to-Image (I2I)

FLUX.2 handles I2I natively via reference image inputs. The approach differs by model:

### FLUX.2 [pro] / [flex] / [max] — Reference Image Editing

Add `image_prompt` (or `image_prompt_strength`) to guide generation from a reference:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Edit instruction or new description |
| `image_prompt` | string | null | Base64 or URL of reference image |
| `image_prompt_strength` | float | 0.1 | 0–1: how much the reference influences output |
| `width` | integer | 1024 | Output width |
| `height` | integer | 1024 | Output height |
| `seed` | integer | null | Reproducibility |
| `output_format` | string | `"jpeg"` | Output format |
| `safety_tolerance` | integer | 2 | Content moderation |

### FLUX.1 Fill [pro] — Inpainting

```
POST https://api.bfl.ai/v1/flux-pro-1.1-fill
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | **required** — fill description |
| `image` | string | **required** — base64 of source image |
| `mask` | string | **required** — base64 of mask (white = fill area) |
| `output_format` | string | `"jpeg"` or `"png"` |

### FLUX.1 Kontext — In-Context Editing

```
POST https://api.bfl.ai/v1/flux-kontext-pro
POST https://api.bfl.ai/v1/flux-kontext-max
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | **required** — edit instruction |
| `input_image` | string | **required** — base64 or URL |
| `output_format` | string | `"jpeg"` or `"png"` |
| `safety_tolerance` | integer | 0–6 |
| `seed` | integer | Reproducibility |

### Example — I2I with Reference (FLUX.2 flex)

```python
import base64, requests, time

with open("source.jpg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

resp = requests.post(
    "https://api.bfl.ai/v1/flux-2-flex",
    headers={"x-key": API_KEY},
    json={
        "prompt": "Transform to watercolour painting style",
        "image_prompt": img_b64,
        "image_prompt_strength": 0.6,
        "width": 1024,
        "height": 1024,
        "output_format": "png"
    }
)
polling_url = resp.json()["polling_url"]
# ... poll as above
```

---

## Available Models

### T2I + I2I Models

| Endpoint | Model | Notes |
|----------|-------|-------|
| `flux-2-pro-preview` | FLUX.2 [pro] Preview | Latest preview — best starting point |
| `flux-2-pro` | FLUX.2 [pro] | Production-pinned FLUX.2 pro |
| `flux-2-max` | FLUX.2 [max] | Maximum quality, slower |
| `flux-2-flex` | FLUX.2 [flex] | Adjustable steps/guidance — developer-friendly |
| `flux-2-dev` | FLUX.2 [dev] | Open-weight 32B, requires commercial license |
| `flux-2-klein-9b-preview` | FLUX.2 [klein] 9B | Compact, fast; preview |
| `flux-pro-1.1` | FLUX 1.1 [pro] | Previous gen, stable |
| `flux-pro-1.1-ultra` | FLUX 1.1 [pro] Ultra | Up to 4MP, raw mode |
| `flux-pro` | FLUX.1 [pro] | Original pro, pinned |
| `flux-dev` | FLUX.1 [dev] | Open-weight 12B |

### Specialised Editing Models

| Endpoint | Use Case |
|----------|----------|
| `flux-kontext-pro` | Natural language in-context editing |
| `flux-kontext-max` | Max quality in-context editing |
| `flux-pro-1.1-fill` | Inpainting / outpainting |
| `flux-dev-depth` | Depth-conditioned editing |
| `flux-dev-canny` | Edge-conditioned editing |
| `flux-dev-redux` | Image variation |

---

## Regional Endpoints

| Region | API Endpoint | Delivery CDN |
|--------|-------------|--------------|
| Global (auto) | `api.bfl.ai` | auto-routed |
| Europe | `api.eu.bfl.ai` | `delivery-eu.bfl.ai` |
| US | `api.us.bfl.ai` | `delivery-us.bfl.ai` |

Use the `polling_url` exactly as returned — don't swap regional URLs.

---

## Pricing (approx.)

| Tier | Rate |
|------|------|
| FLUX.2 [pro] | ~$0.03 / megapixel |
| FLUX.2 [flex] | ~$0.012 / megapixel |
| FLUX.1 [pro] Ultra | ~$0.06 / megapixel |
| FLUX.1 Kontext Pro | ~$0.04 / image |

---

## Notes

- `polling_url` must be used exactly as returned; do not reconstruct from `id`
- Result URLs expire in **10 minutes** — download and store immediately
- Preview endpoints (`-preview` suffix) reflect latest advances; non-preview is version-pinned
- FLUX.2 models accept up to 10 reference images for multi-reference composition
- Commercial use of `flux-2-dev` requires separate licensing via BFL
- `prompt_upsampling` adds BFL's own prompt expansion; can improve results but reduces prompt control
