# Draw Things — Image Inference API Reference

> Base URL: `http://localhost:7860` (default HTTP) | `localhost:7888` (gRPC)  
> Auth: None by default; optional "Shared Secret" for gRPC  
> Pattern: SD-API-compatible HTTP REST + gRPC (protobuf)  
> Platform: macOS / iOS (Apple Silicon); Linux (CUDA via gRPCServerCLI)  
> Docs: `https://wiki.drawthings.ai` | `https://docs.drawthings.ai`

---

## Architecture

Draw Things is a **local inference app** — no cloud required. It exposes two server modes:

1. **HTTP API** — Stable Diffusion–compatible REST at port 7860 (same schema as A1111/SD WebUI)
2. **gRPC API** — high-performance protobuf protocol at port 7888 (or custom); used for device-to-device offloading and the official ComfyUI extension

Both modes are enabled in **Settings → API Server** inside the app.

A **Cloud Compute** tier is also available for users without local GPU:
- **Free (Community)** — 15,000–30,000 compute units/session
- **Draw Things+** ($8.99/mo) — 40,000–100,000 compute units/session

---

## HTTP API (SD-Compatible)

The HTTP API mirrors the Automatic1111 / SD WebUI schema, making it compatible with many existing tools and scripts.

### Text-to-Image Endpoint

```
POST http://localhost:7860/sdapi/v1/txt2img
```

### T2I Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Positive prompt — what to generate |
| `negative_prompt` | string | `""` | What to avoid in the output |
| `seed` | integer | `-1` | `-1` = random; fixed integer for reproducibility |
| `steps` | integer | `20` | Inference steps (4 for turbo models; 20–30 typical) |
| `cfg_scale` | float | `7.5` | CFG / Text Guidance — prompt adherence (1–50) |
| `width` | integer | `512` | Output width in pixels |
| `height` | integer | `512` | Output height in pixels |
| `batch_count` | integer | `1` | Number of images to generate |
| `batch_size` | integer | `1` | Images per batch (memory-dependent) |
| `sampler_name` | string | `"Euler"` | Sampler: `"Euler"`, `"DPM++ 2M"`, `"DDIM"`, etc. |
| `enable_hr` | boolean | false | High-Resolution Fix (two-pass upscaling) |
| `hr_scale` | float | `2.0` | Upscale factor for HR fix |
| `hr_upscaler` | string | model default | Upscaler model |
| `denoising_strength` | float | `0.7` | For HR fix — how much to change at second pass |

### T2I Request (curl)

```bash
curl -X POST http://localhost:7860/sdapi/v1/txt2img \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Aerial view of Lake Macquarie at golden hour, NSW Australia, photorealistic",
    "negative_prompt": "blurry, low quality, overexposed",
    "seed": -1,
    "steps": 20,
    "cfg_scale": 7,
    "width": 1024,
    "height": 768,
    "batch_count": 1
  }'
```

### T2I Request (Python)

```python
import requests, base64, json

url = "http://localhost:7860/sdapi/v1/txt2img"

payload = {
    "prompt": "oil painting of a sailing boat at sunset",
    "negative_prompt": "blurry, cartoon, low quality",
    "seed": 42,
    "steps": 25,
    "cfg_scale": 7.5,
    "width": 1024,
    "height": 1024,
    "batch_count": 1
}

response = requests.post(url, json=payload)
data = response.json()

# Decode base64 image
img_data = base64.b64decode(data["images"][0])
with open("output.png", "wb") as f:
    f.write(img_data)
```

### T2I Response Schema

```json
{
  "images": ["<base64-encoded-png>"],
  "parameters": {
    "prompt": "...",
    "seed": 1234,
    "steps": 20,
    "cfg_scale": 7.5,
    "width": 1024,
    "height": 1024
  },
  "info": "{\"seed\": 1234, \"all_seeds\": [1234], ...}"
}
```

---

## HTTP API — Image-to-Image

### I2I Endpoint

```
POST http://localhost:7860/sdapi/v1/img2img
```

### I2I Parameters (additions to T2I)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `init_images` | array | **required** | Array of base64-encoded source images |
| `denoising_strength` | float | `0.75` | Transform strength — 0.0 = no change, 1.0 = full regeneration |
| `mask` | string | null | Base64 mask image for inpainting (white = edit area) |
| `mask_blur` | integer | `4` | Blur radius for inpainting mask edges |
| `inpainting_fill` | integer | `1` | Fill mode: 0=fill, 1=original, 2=latent noise, 3=latent nothing |
| `inpaint_full_res` | boolean | true | Process only the masked region at full resolution |
| `prompt` | string | **required** | Transformation description |
| `negative_prompt` | string | `""` | What to avoid |
| `seed` | integer | `-1` | Reproducibility |
| `steps` | integer | `20` | Inference steps |
| `cfg_scale` | float | `7.5` | Prompt guidance strength |
| `width` | integer | source width | Output width (defaults to input size) |
| `height` | integer | source height | Output height |

### I2I Request (Python)

```python
import requests, base64

# Load source image
with open("source.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

payload = {
    "init_images": [img_b64],
    "prompt": "transform into watercolour painting style, vivid colours",
    "negative_prompt": "blurry, low quality",
    "denoising_strength": 0.65,
    "steps": 20,
    "cfg_scale": 10,
    "seed": -1
}

response = requests.post("http://localhost:7860/sdapi/v1/img2img", json=payload)
data = response.json()

img_data = base64.b64decode(data["images"][0])
with open("output.png", "wb") as f:
    f.write(img_data)
```

---

## gRPC API

The gRPC server runs at port `7888` by default. Used for:
- ComfyUI integration (`draw-things-comfyui` extension)
- Device-to-device offloading (run models on Mac, control from another device)
- CLI generation (`gRPCServerCLI` binary)

### Key gRPC Parameters (via protobuf)

| Field | Description |
|-------|-------------|
| `prompt` | Positive prompt |
| `negativePrompt` | Negative prompt |
| `steps` | Inference steps |
| `guidanceScale` | CFG scale |
| `seed` | Seed (-1 = random) |
| `width` | Output width |
| `height` | Output height |
| `strength` | Denoising strength for I2I |
| `model` | Model filename to load |
| `sampler` | Sampler name |
| `batchCount` | Images to generate |

### gRPC Server Setup

```bash
# Start gRPC server from CLI (Linux/Mac)
docker run --gpus all \
  -p 7888:7888 \
  drawthingsai/draw-things-grpc-server-cli:latest \
  --host 0.0.0.0 --port 7888

# Or via Homebrew CLI (macOS)
brew install --HEAD drawthingsai/draw-things/draw-things-cli
draw-things-cli generate \
  --model flux_2_klein_4b_q6p.ckpt \
  --prompt "a red cube on a table" \
  --width 1024 --height 1024 \
  --steps 20
```

### Authentication (Shared Secret)

Enable in app **Settings → API Server → Shared Secret**. Pass in requests:

```
grpc-metadata-x-shared-secret: your-secret-here
```

---

## Available Models (as of April 2026)

Model files live in `~/Library/Containers/com.liuliu.draw-things/Data/Documents/Models` (macOS) or a custom `--models-dir` path.

### FLUX Family (T2I + I2I)

| Model | Notes |
|-------|-------|
| FLUX.1 [dev] (Q8, 12GB) | High quality, non-commercial |
| FLUX.1 [schnell] (Q8, 12GB) | 4-step fast |
| FLUX.2 [dev] (32B) | Flagship; requires large VRAM |
| FLUX.2 [klein] 4B | Compact, fast |
| FLUX.2 [klein] 9B KV | Larger compact variant |
| FLUX.1 Fill [dev] | Inpainting / outpainting |
| FLUX.1 Depth / Canny | ControlNet conditioning |
| FLUX.1 Redux | Image variation |
| FLUX.1 Kontext [dev] | In-context editing |

### Stable Diffusion Family

| Model | Notes |
|-------|-------|
| SD 1.5 (various LoRAs) | Classic; broad community support |
| SDXL 1.0 | High resolution; 2-pass refiner |
| SD 3.5 Large / Turbo | Latest SD architecture |

### Other Official Models

| Model | Notes |
|-------|-------|
| Wan 2.1 / 2.2 T2I | Alibaba; strong quality |
| Wan 2.2 14B | Video capable (T2V) |
| Qwen Image 1.0 | 20GB; excellent text rendering |
| Qwen Image 1.0 (6-bit, 16GB) | Quantised variant |
| HiDream | High-fidelity image |
| Chroma | Artistic style model |
| LTX-2 / LTX-2.3 | Video generation |

---

## Settings Controlled In-App (not via API)

Unlike cloud APIs, many Draw Things settings are configured in the app UI rather than request parameters. These persist between API calls:

- **Model** — currently loaded checkpoint
- **Sampler** — DPM++, Euler, DDIM, etc.
- **VAE** — variational autoencoder
- **LoRA** — loaded LoRA weights and strengths
- **ControlNet** — control modules (pose, depth, canny…)
- **Refiner Model** — secondary model for SDXL two-pass
- **Tiled Diffusion / Decoding** — memory management
- **High-Res Fix** — upscale settings

---

## Notes

- The HTTP server is SD-API-compatible — tools like sd-scripts, A1111 extensions, and many Python wrappers work out of the box
- Draw Things returns images as **base64-encoded PNG** in the HTTP API (not URLs)
- `denoising_strength` maps to the **Strength** slider in the UI for I2I
- `cfg_scale` corresponds to **Text Guidance** in the app glossary
- For FLUX models, `cfg_scale` should be set to `1` (they use distilled guidance)
- The gRPCServerCLI can run headless on Linux with NVIDIA RTX 20xx–H100 cards
- **Bridge Mode** (v1.20251007+) allows the in-app HTTP server to forward to a remote gRPC compute node
