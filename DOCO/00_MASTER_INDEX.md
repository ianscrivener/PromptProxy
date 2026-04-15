# Image Inference Engine API Master Index

> Compiled April 2026 — covers text-to-image (T2I) and image-to-image (I2I) endpoints.

---

## Service Overview

| # | Service | Base URL | Auth Header | T2I | I2I | Sync | Async | Batch | Webhook | Pattern |
|---|---------|----------|-------------|-----|-----|-------|-------|-------|---------|---------|
| 1 | **FAL.ai** | `https://fal.run` | `Authorization: Key <key>` | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | REST + Queue/Webhook |
| 2 | **Replicate** | `https://api.replicate.com/v1` | `Authorization: Bearer <token>` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | REST + Polling (async/sync) |
| 3 | **Black Forest Labs (BFL)** | `https://api.bfl.ai/v1` | `x-key: <key>` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | REST + Poll via `polling_url` |
| 4 | **Alibaba / DashScope** | `https://dashscope-intl.aliyuncs.com/api/v1` | `Authorization: Bearer <key>` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | REST sync or async task |
| 5 | **BytePlus ModelArk** | `https://ark.ap-southeast.bytepluses.com/api/v3` | `Authorization: Bearer <key>` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | OpenAI-compatible REST |
| 6 | **Draw Things** | `http://localhost:7860` (local) | None / Shared Secret | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | SD-API-compatible HTTP + gRPC |
| 7 | **OpenRouter** | `https://openrouter.ai/api/v1` | `Authorization: Bearer <key>` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | Chat completions with `modalities` |
| 8 | **Gemini / Nano Banana** | `https://generativelanguage.googleapis.com` | `Authorization: Bearer <key>` | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | Gemini SDK or REST generate_content |

Also: MLX-VLM, ComfyUI, MFlux

---

## Document Index

| File | Service | Contents |
|------|---------|----------|
| `01_FAL.md` | FAL.ai | T2I & I2I endpoints, parameters, models |
| `02_REPLICATE.md` | Replicate | T2I & I2I endpoints, parameters, models |
| `03_BFL.md` | Black Forest Labs | T2I & I2I endpoints, parameters, models |
| `04_ALIBABA.md` | Alibaba / DashScope | T2I & I2I endpoints, parameters, models |
| `05_BYTEPLUS.md` | BytePlus ModelArk | T2I & I2I endpoints, parameters, models |
| `06_DRAW_THINGS.md` | Draw Things | T2I & I2I endpoints, parameters, models |
| `07_OPENROUTER.md` | OpenRouter | T2I & I2I endpoints, parameters, models |
| `08_GEMINI_NANOBANANA.md` | Google Gemini / Nano Banana | T2I & I2I endpoints, parameters, models |

---

## Quick Comparison: Key Parameters

| Parameter | FAL | Replicate | BFL | Alibaba | BytePlus | Draw Things | OpenRouter | Gemini |
|-----------|-----|-----------|-----|---------|----------|-------------|------------|--------|
| `prompt` | ✅ | `input.prompt` | ✅ | `text` (in content) | ✅ | ✅ | in `messages` | in `contents` |
| `negative_prompt` | ✅ | model-dependent | ❌ | ❌ | model-dep | ✅ | model-dep | ❌ |
| `width/height` | ✅ or `image_size` | model-dependent | ✅ | `size` enum | `size` | ✅ | `image_config.image_size` | aspect_ratio |
| `num_inference_steps` | ✅ | model-dependent | ✅ (some) | ❌ | model-dep | `steps` | model-dep | ❌ |
| `guidance_scale` | ✅ | model-dependent | ❌ | ❌ | `guidance_scale` | `cfg_scale` | model-dep | ❌ |
| `seed` | ✅ | model-dependent | ✅ | ❌ | ✅ | ✅ | model-dep | ❌ |
| `strength` (I2I) | ✅ | model-dependent | N/A | N/A | N/A | `denoising_strength` | model-dep | N/A |
| `output_format` | `jpeg/png/webp` | model-dependent | `jpeg/png` | `png` | `url/b64` | inferred | `b64_json/url` | inline data |
| `num_images` | ✅ | model-dep | ❌ | `n` | `n` | `batch_count` | ❌ | ❌ |

---

## Pricing Model Comparison (approx., Apr 2026)

| Service | Pricing Model | Ballpark T2I cost |
|---------|--------------|-------------------|
| FAL.ai | Per output image (model-specific) | $0.003–$0.03/image |
| Replicate | Per output image (official models) | $0.003–$0.08/image |
| BFL | Per megapixel | ~$0.012–$0.03/MP |
| Alibaba | Per image | ~$0.01–$0.04/image |
| BytePlus | Per image | ~$0.03–$0.045/image |
| Draw Things | Free (local) / Cloud credits | Free local |
| OpenRouter | Passes through model pricing | Varies |
| Gemini (API) | Per 1M output tokens (~1290/image) | ~$0.039/image |

---

*See individual service documents for full parameter tables, model lists, and code examples.*
