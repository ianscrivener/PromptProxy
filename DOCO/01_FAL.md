# FAL.ai — Image Inference API Reference

> Base URL: `https://fal.run`  
> Auth: `Authorization: Key YOUR_API_KEY`  
> Pattern: REST with synchronous run, async queue, or webhook  
> SDK: `@fal-ai/client` (JS) / `fal-client` (Python)

---

## Architecture

FAL uses a **serverless, globally distributed** inference engine. Requests can be made three ways:

1. **Synchronous** — `fal.run()` — blocks until result
2. **Queue** — `fal.queue.submit()` → poll `fal.queue.status()` → `fal.queue.result()`
3. **Webhook** — submit with `webhookUrl`, FAL POSTs result back

All endpoints follow the pattern: `POST https://fal.run/{endpoint_id}`

---

## Text-to-Image (T2I)

### Endpoint

```
POST https://fal.run/{endpoint_id}
```

### Common T2I Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Text description of the image |
| `negative_prompt` | string | `""` | What to avoid in the output |
| `image_size` | string or object | `"landscape_4_3"` | Preset: `square_hd`, `square`, `portrait_4_3`, `portrait_16_9`, `landscape_4_3`, `landscape_16_9`; or `{width, height}` |
| `width` | integer | 512 | Custom width (must be multiple of 8) |
| `height` | integer | 512 | Custom height (must be multiple of 8) |
| `num_inference_steps` | integer | 28 | Diffusion steps (higher = better quality, slower) |
| `guidance_scale` | float | 3.5 | CFG scale — how closely output follows the prompt |
| `num_images` | integer | 1 | Number of images to generate |
| `seed` | integer | null | Fixed seed for reproducibility |
| `output_format` | string | `"jpeg"` | `"jpeg"`, `"png"`, `"webp"` |
| `enable_safety_checker` | boolean | true | NSFW content filter |
| `sync_mode` | boolean | false | Wait for image in response body (vs CDN URL) |
| `lora_scale` | float | 1.0 | Scale for LoRA adaptation (where supported) |
| `acceleration` | string | `"none"` | Speed mode: `"none"`, `"hyper"` (model-dependent) |

### Example Request (curl)

```bash
curl -X POST https://fal.run/fal-ai/flux/dev \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Aerial photo of Wangi Wangi at sunset, Lake Macquarie, moody light",
    "image_size": "landscape_16_9",
    "num_inference_steps": 28,
    "guidance_scale": 3.5,
    "num_images": 1,
    "output_format": "jpeg"
  }'
```

### Example Request (Python)

```python
import fal_client

result = fal_client.run(
    "fal-ai/flux/dev",
    arguments={
        "prompt": "Aerial photo of Wangi Wangi at sunset",
        "image_size": "landscape_16_9",
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "output_format": "jpeg"
    }
)
print(result["images"][0]["url"])
```

### T2I Response Schema

```json
{
  "images": [
    {
      "url": "https://fal.media/files/...",
      "content_type": "image/jpeg",
      "width": 1366,
      "height": 768
    }
  ],
  "seed": 12345,
  "prompt": "...",
  "has_nsfw_concepts": [false]
}
```

---

## Image-to-Image (I2I)

### Endpoint

Append `/image-to-image` or use a dedicated I2I model endpoint.

```
POST https://fal.run/{endpoint_id}
POST https://fal.run/fal-ai/flux/dev/image-to-image
POST https://fal.run/fal-ai/lcm   (supports both T2I and I2I via image_url param)
```

### I2I Parameters (additions to T2I)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_url` | string | **required** | URL or base64 of source image |
| `strength` | float | 0.8 | How much to transform the original (0.0 = keep, 1.0 = ignore) |
| `mask_url` | string | null | For inpainting — URL/base64 of mask image |
| `controlnet_conditioning_scale` | float | 1.0 | ControlNet influence strength (if applicable) |

### Example Request (I2I)

```bash
curl -X POST https://fal.run/fal-ai/lcm \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "oil painting style, dramatic lighting",
    "image_url": "https://example.com/source.jpg",
    "strength": 0.75,
    "num_inference_steps": 4,
    "guidance_scale": 1.0
  }'
```

### Queue / Async Pattern

```python
import fal_client

# Submit
handle = fal_client.submit(
    "fal-ai/flux/dev",
    arguments={"prompt": "..."},
    webhook_url="https://your-server.com/webhook"
)

request_id = handle.request_id

# Poll status
status = fal_client.status("fal-ai/flux/dev", request_id, with_logs=True)

# Fetch result
result = fal_client.result("fal-ai/flux/dev", request_id)
```

---

## Available T2I Models

| Model ID | Description | Notes |
|----------|-------------|-------|
| `fal-ai/flux/dev` | FLUX.1 [dev] — 12B parameter, high quality | ~$0.025/image |
| `fal-ai/flux/schnell` | FLUX.1 [schnell] — ultra-fast, 4 steps | ~$0.003/image |
| `fal-ai/flux-pro` | FLUX.1 [pro] — proprietary, top quality | ~$0.05/image |
| `fal-ai/flux-pro/v1.1` | FLUX 1.1 Pro — improved prompt following | ~$0.04/image |
| `fal-ai/flux-pro/v1.1-ultra` | FLUX 1.1 Pro Ultra — up to 4MP output | ~$0.06/image |
| `fal-ai/flux-2-pro` | FLUX.2 [pro] — 32B, multi-reference editing | ~$0.03/MP |
| `fal-ai/flux-2-dev` | FLUX.2 [dev] — open-weight, 32B | ~$0.012/MP |
| `fal-ai/flux-2-flex` | FLUX.2 [flex] — developer-tunable | ~$0.012/MP |
| `fal-ai/stable-diffusion-xl` | SDXL 1.0 with LoRA support | Budget option |
| `fal-ai/stable-diffusion-v35-medium` | SD 3.5 Medium | Mid-range quality |
| `fal-ai/glm-image` | GLM-Image — strong text rendering | Autoregressive |
| `fal-ai/sana` | SANA — very fast diffusion | Efficient-Large-Model |
| `fal-ai/ideogram/v3` | Ideogram v3 — typography specialist | Licensed |

## Available I2I Models

| Model ID | Description |
|----------|-------------|
| `fal-ai/flux/dev/image-to-image` | FLUX.1 dev img2img |
| `fal-ai/flux-2-flex` | FLUX.2 Flex — multi-reference editing |
| `fal-ai/flux-fill/dev` | FLUX.1 Fill (inpainting/outpainting) |
| `fal-ai/lcm` | LCM — fast img2img + inpainting |
| `fal-ai/controlnet-*` | Various ControlNet models (canny, depth, pose…) |
| `fal-ai/glm-image/image-to-image` | GLM img2img — up to 4 reference images |

---

## Authentication Setup

```python
import os
os.environ["FAL_KEY"] = "your-key-here"

# OR configure directly
import fal_client
fal_client.api_key = "your-key-here"
```

```javascript
import { fal } from "@fal-ai/client";
fal.config({ credentials: "your-key-here" });
```

---

## Notes

- Signed output URLs expire; retrieve files promptly
- Rate limits vary by tier — check dashboard
- LoRA weights can be loaded at inference time for many models
- FLUX.2 models natively handle both T2I and I2I in the same architecture
