# Alibaba / DashScope — Image Inference API Reference

> Base URL (Singapore): `https://dashscope-intl.aliyuncs.com/api/v1`  
> Base URL (Beijing): `https://dashscope.aliyuncs.com/api/v1`  
> Auth: `Authorization: Bearer $DASHSCOPE_API_KEY`  
> SDK: `dashscope` (Python) / HTTP REST  
> Docs: `https://www.alibabacloud.com/help/en/model-studio`

---

## Architecture

Alibaba's image generation API lives inside **Model Studio** (also called DashScope). There are two main model families:

- **Wan 2.7** — flagship multimodal image generation and editing; supports 4K; "thinking mode"
- **Qwen-Image** — high-quality generation with strong text rendering; async task-based

Two call patterns:
- **HTTP synchronous** — single POST, result in response (Wan 2.7)
- **HTTP async (task)** — POST to submit, GET to retrieve result (Qwen-Image)

⚠️ Singapore and Beijing regions use **separate API keys** and **separate endpoints** — do not cross-use them.

---

## Wan 2.7 — Text-to-Image

### Endpoint

```
POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

### T2I Parameters

| Parameter | Location | Type | Default | Description |
|-----------|----------|------|---------|-------------|
| `model` | body | string | **required** | `"wan2.7-image-pro"` or `"wan2.7-image"` |
| `messages[].content[].text` | body | string | **required** | Prompt — up to 5,000 chars, Chinese or English |
| `parameters.size` | body | string | `"2K"` | Resolution: `"1K"`, `"2K"`, `"4K"` (pro only for 4K) |
| `parameters.n` | body | integer | 1 | Number of images to generate (1–4) |
| `parameters.watermark` | body | boolean | true | Alibaba watermark on output |
| `parameters.thinking_mode` | body | boolean | false | Enable extended reasoning for complex prompts |
| `parameters.enable_sequential` | body | boolean | false | Generate a thematic image set (use with n > 1) |

### T2I Request (curl)

```bash
curl -X POST \
  https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan2.7-image-pro",
    "input": {
      "messages": [{
        "role": "user",
        "content": [
          {"text": "Aerial view of Lake Macquarie at sunrise, NSW Australia, photorealistic, 4K"}
        ]
      }]
    },
    "parameters": {
      "size": "2K",
      "n": 1,
      "watermark": false,
      "thinking_mode": true
    }
  }'
```

### T2I Request (Python SDK)

```python
import dashscope
from dashscope import ImageSynthesis

response = ImageSynthesis.call(
    model="wan2.7-image-pro",
    prompt="A flower shop with beautiful wooden door and flowers on display",
    n=1,
    size="2K"
)

if response.status_code == 200:
    for result in response.output.results:
        print(result.url)
```

### T2I Response Schema

```json
{
  "output": {
    "choices": [{
      "message": {
        "role": "assistant",
        "content": [
          {"image": "https://dashscope-result.oss-cn-...signed-url.png"}
        ]
      },
      "finish_reason": "stop"
    }]
  },
  "usage": {"image_count": 1},
  "request_id": "abc-123"
}
```

---

## Wan 2.7 — Image-to-Image (Editing)

### Image Editing

Pass one or more images in `content` alongside the text instruction:

```bash
curl -X POST \
  https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan2.7-image-pro",
    "input": {
      "messages": [{
        "role": "user",
        "content": [
          {"image": "https://example.com/car.webp"},
          {"image": "https://example.com/graffiti.webp"},
          {"text": "Spray the graffiti from image 2 onto the car in image 1"}
        ]
      }]
    },
    "parameters": {
      "size": "2K",
      "n": 1,
      "watermark": false
    }
  }'
```

### I2I Parameters (in addition to T2I)

| Parameter | Type | Description |
|-----------|------|-------------|
| `content[].image` | string | URL or `data:image/jpeg;base64,...` of input image |
| `parameters.bbox_list` | array | Bounding boxes for interactive editing. Per-image list of `[x1,y1,x2,y2]` coords |
| `parameters.enable_sequential` | boolean | Image set output (consistent subject across images) |

#### Image Input Limits

- Formats: JPEG, JPG, PNG (no alpha), BMP, WEBP
- Resolution: 240–8000px per side; aspect ratio 1:8 to 8:1
- Max file size: 20 MB
- Max images per request: 9

### Interactive Editing (Bounding Box)

```json
"parameters": {
  "bbox_list": [
    [],                          // image 1: no edit region
    [[989, 515, 1138, 681]],    // image 2: one bounding box
    [[10, 10, 50, 50]]          // image 3: one bounding box
  ]
}
```

---

## Qwen-Image — Text-to-Image (Async)

Qwen-Image uses an **async task** pattern.

### Models

| Model | Description |
|-------|-------------|
| `qwen-image` | Standard quality — balanced |
| `qwen-image-plus` | More cost-effective plus tier |
| `qwen-image-plus-2026-01-09` | Distilled/accelerated plus |
| `qwen-image-max` | Maximum quality — best realism |
| `qwen-image-max-2025-12-30` | Pinned max snapshot |
| `qwen-image-edit` | Image editing / I2I / inpainting |

### Qwen T2I Endpoint (Submit Task)

```
POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis
```

```bash
curl -X POST \
  https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-DashScope-Async: enable" \
  -d '{
    "model": "qwen-image-max",
    "input": {"prompt": "A photorealistic mountain landscape at dawn"},
    "parameters": {
      "size": "1024*1024",
      "n": 1,
      "prompt_extend": true
    }
  }'
```

### Qwen T2I Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Image description |
| `size` | string | `"1024*1024"` | `"512*512"`, `"768*768"`, `"1024*1024"`, `"1024*768"`, etc. |
| `n` | integer | 1 | Number of images (1–4) |
| `prompt_extend` | boolean | false | Auto-expand prompt |
| `negative_prompt` | string | null | Elements to exclude |
| `seed` | integer | null | Reproducibility |

### Qwen T2I — Poll for Result

```
GET https://dashscope-intl.aliyuncs.com/api/v1/tasks/{task_id}
```

```python
import dashscope, time

# Submit
rsp = dashscope.ImageSynthesis.async_call(
    model="qwen-image-max",
    prompt="A vibrant coral reef, underwater photography",
    n=1,
    size="1024*1024"
)
task_id = rsp.output.task_id

# Poll
while True:
    status_rsp = dashscope.ImageSynthesis.fetch(rsp)
    if status_rsp.output.task_status == "SUCCEEDED":
        for result in status_rsp.output.results:
            print(result.url)
        break
    elif status_rsp.output.task_status == "FAILED":
        raise Exception(status_rsp)
    time.sleep(2)
```

### Qwen Image Edit (I2I)

```
POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | **required** — edit instruction |
| `base_image_url` | string | **required** — source image URL |
| `mask_image_url` | string | Mask for inpainting (white = edit area) |
| `size` | string | Output size |
| `n` | integer | Number of outputs |

---

## Wan 2.7 — Size Reference

### wan2.7-image-pro

| Size Key | Max Pixels | Notes |
|----------|-----------|-------|
| `"1K"` | ~720p equivalent | Fast |
| `"2K"` (default) | ~1440p equivalent | Recommended |
| `"4K"` | ~4K equivalent | T2I only; slower |

Custom dimensions also accepted as `"WxH"` string (must stay within resolution limits).

### wan2.7-image

| Size Key | Notes |
|----------|-------|
| `"1K"` | Standard |
| `"2K"` | Default |

---

## Model Comparison

| Model | Best For | Max Resolution | Thinking Mode |
|-------|----------|---------------|---------------|
| wan2.7-image-pro | All-round production quality | 4K (T2I) | ✅ |
| wan2.7-image | Fast generation, lower cost | 2K | ✅ |
| qwen-image-max | Photorealism, text rendering | 1024px | ❌ |
| qwen-image-plus | Cost-effective quality | 1024px | ❌ |
| qwen-image-edit | I2I editing, inpainting | 1024px | ❌ |

---

## Notes

- Singapore (`dashscope-intl`) and Beijing (`dashscope`) are completely independent — separate keys
- Output images are stored in Alibaba OSS; URLs are temporary public signed links
- `thinking_mode: true` adds reasoning before generation — improves complex scenes but increases latency
- `enable_sequential: true` generates a thematically consistent image set (same subject across frames)
- Interactive editing with `bbox_list` places an element from one image into a selected region of another
- Chinese-language prompts are natively supported across all models
