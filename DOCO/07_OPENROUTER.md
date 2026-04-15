# OpenRouter — Image Inference API Reference

> Base URL: `https://openrouter.ai/api/v1`  
> Auth: `Authorization: Bearer $OPENROUTER_API_KEY`  
> Pattern: **Chat completions** with `modalities` parameter (not a dedicated images endpoint)  
> Docs: `https://openrouter.ai/docs/guides/overview/multimodal/image-generation`

---

## Architecture

OpenRouter is a **unified API gateway** routing to hundreds of models. Image generation is handled through the standard **chat completions** endpoint with a `modalities` parameter specifying image output — not the OpenAI-style `/images/generations` endpoint.

Generated images are returned as **base64-encoded data URLs** inside the assistant message's content array.

To find image-capable models:
- Visit `openrouter.ai/collections/image-models`
- Filter models by `output_modalities=image` via the Models API
- Look for `"image"` in a model's `output_modalities` field

---

## Text-to-Image (T2I)

### Endpoint

```
POST https://openrouter.ai/api/v1/chat/completions
```

### T2I Request Body

```json
{
  "model": "google/gemini-2.5-flash-image",
  "messages": [
    {
      "role": "user",
      "content": "Generate an image of Lake Macquarie at sunrise, NSW Australia, photorealistic"
    }
  ],
  "modalities": ["image", "text"],
  "image_config": {
    "aspect_ratio": "16:9",
    "image_size": "2K"
  }
}
```

### Core T2I Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | string | **required** — model identifier (e.g., `"google/gemini-2.5-flash-image"`) |
| `messages` | array | **required** — chat messages; prompt goes in user content |
| `modalities` | array | **required** — `["image"]` for image-only; `["image", "text"]` for both |
| `image_config.aspect_ratio` | string | Aspect ratio: `"1:1"`, `"16:9"`, `"9:16"`, `"4:3"`, `"3:2"`, etc. |
| `image_config.image_size` | string | Resolution: `"0.5K"`, `"1K"`, `"2K"`, `"4K"` (model-dependent) |
| `image_config.font_inputs` | array | Custom font rendering (Sourceful models only) |

### T2I Request (curl)

```bash
curl -X POST https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "HTTP-Referer: https://yourapp.com" \
  -H "X-Title: Your App Name" \
  -d '{
    "model": "google/gemini-2.5-flash-image",
    "messages": [{
      "role": "user",
      "content": "A sailing yacht on Lake Macquarie at golden hour, dramatic sky, photorealistic"
    }],
    "modalities": ["image", "text"],
    "image_config": {
      "aspect_ratio": "16:9",
      "image_size": "2K"
    }
  }'
```

### T2I Request (Python — OpenAI-compatible)

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-openrouter-key",
    base_url="https://openrouter.ai/api/v1"
)

response = client.chat.completions.create(
    model="google/gemini-2.5-flash-image",
    messages=[{
        "role": "user",
        "content": "A dramatic sunset over the ocean, oil painting style"
    }],
    extra_body={
        "modalities": ["image", "text"],
        "image_config": {
            "aspect_ratio": "16:9",
            "image_size": "2K"
        }
    }
)

# Images are in the message content
for part in response.choices[0].message.content:
    if part.type == "image_url":
        # part.image_url.url is a base64 data URL
        img_data = part.image_url.url
```

### T2I Response Schema

```json
{
  "id": "gen-...",
  "model": "google/gemini-2.5-flash-image",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": [
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgo..."
          }
        },
        {
          "type": "text",
          "text": "Here is the generated image of..."
        }
      ]
    }
  }],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 1290,
    "total_tokens": 1310
  }
}
```

---

## Image-to-Image (I2I)

For I2I, include the source image in the user message content as an image URL or base64. The model interprets the image and applies the text instruction.

### I2I Request Body

```json
{
  "model": "google/gemini-2.5-flash-image",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/source-image.jpg"
          }
        },
        {
          "type": "text",
          "text": "Transform this into a watercolour painting style"
        }
      ]
    }
  ],
  "modalities": ["image", "text"],
  "image_config": {
    "aspect_ratio": "16:9"
  }
}
```

### I2I Request (Python)

```python
import base64

with open("source.jpg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="black-forest-labs/flux.2-pro",
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
            },
            {
                "type": "text",
                "text": "Make the sky more dramatic with storm clouds"
            }
        ]
    }],
    extra_body={
        "modalities": ["image", "text"]
    }
)
```

### I2I via Multi-Turn (Conversational Editing)

Gemini models support multi-turn editing — maintain conversation history:

```python
messages = [
    {"role": "user", "content": "Generate a photo of a mountain lake"},
    # ... assistant response with generated image ...
    {"role": "assistant", "content": [{"type": "image_url", "image_url": {"url": "data:..."}}]},
    {"role": "user", "content": "Now add a wooden cabin on the left shore"}
]

response = client.chat.completions.create(
    model="google/gemini-2.5-flash-image",
    messages=messages,
    extra_body={"modalities": ["image", "text"]}
)
```

---

## `image_config` — Aspect Ratio & Size Reference

### Aspect Ratios

| Value | Notes |
|-------|-------|
| `"1:1"` | Square — default |
| `"16:9"` | Landscape widescreen |
| `"9:16"` | Portrait (social/mobile) |
| `"4:3"` | Standard landscape |
| `"3:4"` | Standard portrait |
| `"3:2"` | Photography landscape |
| `"2:3"` | Photography portrait |
| `"21:9"` | Ultra-wide |

### Image Sizes

| Value | Notes |
|-------|-------|
| `"0.5K"` | Low-res (Gemini 3.1 Flash only) |
| `"1K"` | ~1024px |
| `"2K"` | ~2048px |
| `"4K"` | ~4096px (Nano Banana Pro only) |

---

## Available Image Generation Models

### Google Gemini (Nano Banana)

| Model ID | Name | Notes |
|----------|------|-------|
| `google/gemini-2.5-flash-image` | Nano Banana | Fast, cost-efficient |
| `google/gemini-3.1-flash-image-preview` | Nano Banana 2 | Pro-level quality at Flash speed |
| `google/gemini-3-pro-image-preview` | Nano Banana Pro | Highest quality; 4K; thinking mode |

### FLUX (Black Forest Labs)

| Model ID | Notes |
|----------|-------|
| `black-forest-labs/flux.2-pro` | FLUX.2 Pro via OpenRouter |
| `black-forest-labs/flux.2-flex` | FLUX.2 Flex |
| `black-forest-labs/flux-1.1-pro` | FLUX 1.1 Pro |
| `black-forest-labs/flux-kontext-pro` | In-context editing |
| `black-forest-labs/flux-kontext-max` | Max quality editing |

### OpenAI (GPT Image)

| Model ID | Notes |
|----------|-------|
| `openai/gpt-5-image` | GPT-5 + GPT Image 1 |
| `openai/gpt-5-image-mini` | Efficient GPT-5 image |

### ByteDance Seedream

| Model ID | Notes |
|----------|-------|
| `bytedance/seedream-4-5` | Seedream 4.5 — $0.04/image |
| `bytedance/seedream-4-0` | Seedream 4.0 |

### Sourceful Riverflow

| Model ID | Notes |
|----------|-------|
| `sourceful/riverflow-v2-pro` | SOTA; supports custom font rendering |
| `sourceful/riverflow-v2-fast` | Faster variant |

---

## Model Discovery (API)

```bash
# Find all image-output models
curl https://openrouter.ai/api/v1/models?output_modalities=image \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data[].id'
```

---

## Optional Request Headers

| Header | Description |
|--------|-------------|
| `HTTP-Referer` | Your app URL — appears in OpenRouter leaderboard |
| `X-Title` | Your app name — appears in OpenRouter leaderboard |

---

## Notes

- OpenRouter does **not** use `/v1/images/generations` — always use `/v1/chat/completions`
- Images are returned as **base64 data URLs** in the response, not remote URLs
- `modalities: ["image"]` generates image only; `["image", "text"]` allows the model to also return text explanation
- Some models (FLUX.2, GPT-5 Image) are image-in, image-out; others (Gemini) support full multimodal multi-turn conversations
- Model pricing passes through to the underlying provider; check `openrouter.ai/models` for current per-image costs
- `font_inputs` (Sourceful models) allows rendering custom text with specified fonts into the generated image
