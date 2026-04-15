# Replicate — Image Inference API Reference

> Base URL: `https://api.replicate.com/v1`  
> Auth: `Authorization: Bearer $REPLICATE_API_TOKEN`  
> Pattern: REST — async (default) or sync (`Prefer: wait`)  
> SDK: `replicate` (Python + JS)

---

## Architecture

Replicate uses a **prediction** model. Every inference call creates a prediction object that progresses through states: `starting → processing → succeeded | failed | canceled`.

Two modes:
- **Async** (default) — returns immediately with a prediction ID; poll or use webhooks
- **Sync** — add `Prefer: wait` header; blocks up to 60s

Model identifiers:
- Official: `{owner}/{name}` — e.g., `black-forest-labs/flux-schnell`
- Community: `{owner}/{name}:{version_id}` — e.g., `stability-ai/sdxl:39ed52f2…`

---

## Text-to-Image (T2I)

### Endpoints

```
# Official models (no version needed)
POST https://api.replicate.com/v1/models/{owner}/{name}/predictions

# Any model (universal endpoint, Aug 2025+)
POST https://api.replicate.com/v1/predictions
```

### Request Body

```json
{
  "version": "black-forest-labs/flux-schnell",   // or owner/name:version_id
  "input": {
    "prompt": "...",
    // model-specific parameters below
  },
  "webhook": "https://your-server.com/webhook",  // optional
  "webhook_events_filter": ["completed"],         // optional
  "stream": false                                 // optional streaming
}
```

### Common T2I Input Parameters (model-dependent)

| Parameter | Type | Notes |
|-----------|------|-------|
| `prompt` | string | **required** — text description |
| `negative_prompt` | string | What to exclude (SD-based models) |
| `width` | integer | Output width (typically 64–2048) |
| `height` | integer | Output height |
| `aspect_ratio` | string | e.g., `"16:9"`, `"1:1"` (FLUX models) |
| `num_inference_steps` | integer | Diffusion steps — default varies by model |
| `guidance_scale` | float | CFG scale for prompt adherence |
| `seed` | integer | Fixed seed for reproducibility |
| `num_outputs` | integer | Number of images (usually 1–4) |
| `output_format` | string | `"png"`, `"jpg"`, `"webp"` |
| `output_quality` | integer | 1–100, applies to jpg/webp |
| `go_fast` | boolean | Speed optimisation (FLUX models) |
| `megapixels` | string | `"1"` or `"0.25"` (FLUX Pro Ultra) |
| `raw` | boolean | Unprocessed natural-look output (FLUX Pro Ultra) |
| `safety_tolerance` | integer | 1–6, content moderation level (FLUX Pro) |
| `enhance_prompt` | boolean | Auto-expand prompt (FLUX Pro) |
| `lora_scale` | float | 0–1 LoRA influence |

### Example — Sync Request (curl)

```bash
curl -s -X POST \
  -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Prefer: wait" \
  https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions \
  -d '{
    "input": {
      "prompt": "Aerial drone shot of Lake Macquarie at golden hour, NSW Australia",
      "aspect_ratio": "16:9",
      "output_format": "jpg",
      "output_quality": 90
    }
  }'
```

### Example — Async Request (Python)

```python
import replicate

# Run and wait
output = replicate.run(
    "black-forest-labs/flux-schnell",
    input={"prompt": "a cat on a sailboat", "num_outputs": 1}
)
print(output[0])  # URL

# Or async with webhook
prediction = replicate.predictions.create(
    version="black-forest-labs/flux-schnell",
    input={"prompt": "a cat on a sailboat"},
    webhook="https://your-server.com/hook",
    webhook_events_filter=["completed"]
)
```

### Response Schema

```json
{
  "id": "xyz123",
  "status": "succeeded",
  "output": ["https://replicate.delivery/...image.png"],
  "metrics": {"predict_time": 1.23},
  "created_at": "2026-04-14T00:00:00Z",
  "completed_at": "2026-04-14T00:00:02Z"
}
```

---

## Image-to-Image (I2I)

I2I on Replicate is model-specific — each model that supports it defines its own input keys. Common patterns:

### Parameters (model-dependent)

| Parameter | Type | Notes |
|-----------|------|-------|
| `image` | string | URL or base64 of input image |
| `prompt` | string | Transformation description |
| `strength` | float | 0–1, transformation degree (0 = keep, 1 = ignore) |
| `negative_prompt` | string | What to exclude |
| `guidance_scale` | float | CFG prompt adherence |
| `num_inference_steps` | integer | Steps |
| `seed` | integer | Reproducibility |
| `init_skip_fraction` | float | Some models: 0–1, how much to skip init image |
| `mask` | string | URL of inpainting mask |

### Example — I2I (flux-fill-dev for inpainting)

```bash
curl -s -X POST \
  -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Prefer: wait" \
  https://api.replicate.com/v1/models/black-forest-labs/flux-fill-dev/predictions \
  -d '{
    "input": {
      "prompt": "a calm ocean with sailboats",
      "image": "https://example.com/landscape.png",
      "mask": "https://example.com/mask.png"
    }
  }'
```

### Example — I2I (flux-dev-img2img)

```python
output = replicate.run(
    "black-forest-labs/flux-dev",
    input={
        "prompt": "transform into oil painting style",
        "image": "https://example.com/photo.jpg",
        "strength": 0.6,
        "num_inference_steps": 28
    }
)
```

---

## Available T2I Models (Official)

| Model | Description | Pricing |
|-------|-------------|---------|
| `black-forest-labs/flux-schnell` | 4-step ultra-fast FLUX.1 | ~$0.003/image |
| `black-forest-labs/flux-dev` | FLUX.1 [dev] — 12B experimental | ~$0.025/image |
| `black-forest-labs/flux-1.1-pro` | FLUX 1.1 Pro — top quality | ~$0.04/image |
| `black-forest-labs/flux-pro` | FLUX.1 [pro] — proprietary | ~$0.055/image |
| `black-forest-labs/flux-1.1-pro-ultra` | Up to 4MP, raw mode | ~$0.06/image |
| `black-forest-labs/flux-kontext-pro` | In-context image editing | Per image |
| `black-forest-labs/flux-kontext-max` | Kontext max quality | Per image |
| `ideogram-ai/ideogram-v3-turbo` | Fast Ideogram v3 | Per image |
| `ideogram-ai/ideogram-v3-balanced` | Quality/speed balance | Per image |
| `ideogram-ai/ideogram-v3-quality` | Maximum Ideogram quality | Per image |
| `recraft-ai/recraft-v3` | Recraft V3 — SOTA styles, SVG capable | Per image |
| `recraft-ai/recraft-v4` | Recraft V4 — art-directed | Per image |
| `bytedance/seedream-5-0-lite` | ByteDance Seedream 5 | Per image |
| `alibaba-cloud/wan-2-7-pro` | Wan 2.7 Pro — 4K, thinking mode | Per image |
| `stability-ai/stable-diffusion-3-5-large` | SD 3.5 Large | Per image |

## Available I2I Models (Official)

| Model | Description |
|-------|-------------|
| `black-forest-labs/flux-fill-dev` | Inpainting / outpainting |
| `black-forest-labs/flux-fill-pro` | Professional inpainting |
| `black-forest-labs/flux-depth-dev` | Depth-conditioned generation |
| `black-forest-labs/flux-canny-dev` | Edge-conditioned generation |
| `black-forest-labs/flux-redux-dev` | Image variation |
| `black-forest-labs/flux-kontext-pro` | Text-guided image editing |
| `bytedance/seededit-3-0` | Portrait/background editing |
| `alibaba-cloud/wan-2-7-pro` | Multi-reference editing |
| `topazlabs/image-upscale` | AI upscaling |
| `tencentarc/gfpgan` | Face restoration |

---

## Polling Pattern

```python
import replicate, time

# Create async prediction
pred = replicate.predictions.create(
    version="black-forest-labs/flux-dev",
    input={"prompt": "..."}
)

# Poll
while pred.status not in ["succeeded", "failed", "canceled"]:
    time.sleep(2)
    pred = replicate.predictions.get(pred.id)

print(pred.output)
```

---

## Notes

- Output URLs expire — save files immediately
- Sync mode (`Prefer: wait`) has a 60s timeout; use async for slow models
- `Cancel-After` header sets a deadline for the prediction itself
- Community models require the full `{owner}/{name}:{version_id}` string
- FLUX.2 models on Replicate accept up to 8 reference images for style transfer
