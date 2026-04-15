# Google Gemini / Nano Banana — Image Inference API Reference

> Base URL (Gemini API): `https://generativelanguage.googleapis.com/v1beta`  
> Auth: `?key=YOUR_GEMINI_API_KEY` (query param) or `Authorization: Bearer <token>` (Vertex AI)  
> SDK: `google-genai` (Python/JS) | `@google/generative-ai`  
> Docs: `https://ai.google.dev/gemini-api/docs/image-generation`

---

## What is "Nano Banana"?

"Nano Banana" is Google's internal nickname for Gemini's native image generation capability. Three tiers exist:

| Nickname | Model ID | Description |
|----------|----------|-------------|
| **Nano Banana** | `gemini-2.5-flash-image` | Speed-optimised; low latency; SynthID watermark |
| **Nano Banana 2** | `gemini-3.1-flash-image-preview` | Pro-level quality at Flash speed; search grounding |
| **Nano Banana Pro** | `gemini-3-pro-image-preview` | Highest quality; 4K; thinking/reasoning; 14-image references |

All three models:
- Handle both T2I and I2I in the same API call
- Return images as **inline base64 data** (not URLs)
- Support multi-turn conversational editing
- Apply SynthID invisible watermarks to all generated images

---

## Architecture

Gemini image generation uses the **`generate_content`** endpoint — the same one used for text and vision tasks. The response contains a mix of `text` and `inline_data` (image) parts.

Two access routes:
1. **Gemini API** (Google AI Studio) — API key, direct HTTP or SDK
2. **Vertex AI** — Google Cloud credentials; enterprise deployment

---

## Text-to-Image (T2I)

### Endpoint

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=API_KEY
```

### T2I Parameters

| Parameter | Location | Type | Description |
|-----------|----------|------|-------------|
| `model` | path | string | **required** — model ID |
| `contents[].parts[].text` | body | string | **required** — prompt text |
| `generationConfig.responseModalities` | body | array | **required** — `["IMAGE"]` or `["TEXT", "IMAGE"]` |
| `generationConfig.imagenConfig.aspectRatio` | body | string | `"1:1"`, `"16:9"`, `"9:16"`, `"4:3"`, `"3:4"`, `"3:2"`, `"2:3"` |
| `generationConfig.imagenConfig.outputOptions.imageFormat` | body | string | `"PNG"` or `"JPEG"` |
| `safetySettings` | body | array | Content safety configuration |

### T2I Request (curl)

```bash
curl -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{
        "text": "Aerial view of Lake Macquarie at golden hour, NSW Australia, photorealistic, dramatic clouds"
      }]
    }],
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"],
      "imagenConfig": {
        "aspectRatio": "16:9"
      }
    }
  }'
```

### T2I Request (Python SDK)

```python
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client(api_key="YOUR_GEMINI_API_KEY")

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents="A vibrant coral reef, underwater photography, photorealistic",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"]
    )
)

for part in response.candidates[0].content.parts:
    if part.text:
        print(part.text)
    elif part.inline_data:
        img = Image.open(BytesIO(part.inline_data.data))
        img.save("output.png")
```

### T2I Request (JavaScript SDK)

```javascript
import { GoogleGenerativeAI } from "@google/generative-ai";
import * as fs from "fs";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash-image" });

const result = await model.generateContent({
    contents: [{ role: "user", parts: [{ text: "A sailing yacht at sunset" }] }],
    generationConfig: { responseModalities: ["TEXT", "IMAGE"] }
});

for (const part of result.response.candidates[0].content.parts) {
    if (part.inlineData) {
        const imgBuffer = Buffer.from(part.inlineData.data, "base64");
        fs.writeFileSync("output.png", imgBuffer);
    }
}
```

### T2I Response Schema

```json
{
  "candidates": [{
    "content": {
      "parts": [
        {
          "text": "Here is the generated image..."
        },
        {
          "inlineData": {
            "mimeType": "image/png",
            "data": "iVBORw0KGgo..."
          }
        }
      ],
      "role": "model"
    }
  }],
  "usageMetadata": {
    "promptTokenCount": 12,
    "candidatesTokenCount": 1290,
    "totalTokenCount": 1302
  }
}
```

---

## Image-to-Image (I2I)

Include the source image as an `inline_data` or `file_data` part in the contents array, alongside the text instruction.

### I2I Request (Python)

```python
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client(api_key="YOUR_GEMINI_API_KEY")

# Load source image
source = Image.open("source.jpg")

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[
        "Transform this photograph into a watercolour painting style",
        source   # PIL Image is accepted directly
    ],
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"]
    )
)

for part in response.candidates[0].content.parts:
    if part.inline_data:
        img = Image.open(BytesIO(part.inline_data.data))
        img.save("edited.png")
```

### I2I Request (curl with base64)

```bash
# Encode image
IMG_B64=$(base64 -i source.jpg)

curl -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"contents\": [{
      \"parts\": [
        {
          \"inlineData\": {
            \"mimeType\": \"image/jpeg\",
            \"data\": \"$IMG_B64\"
          }
        },
        {
          \"text\": \"Make the sky more dramatic with storm clouds\"
        }
      ]
    }],
    \"generationConfig\": {
      \"responseModalities\": [\"TEXT\", \"IMAGE\"]
    }
  }"
```

### Multi-Turn Conversational Editing

```python
chat = client.chats.create(
    model="gemini-2.5-flash-image",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"]
    )
)

# Turn 1 — generate
response1 = chat.send_message("Generate a photo of a mountain lake at dawn")
# Extract image from response...

# Turn 2 — edit
response2 = chat.send_message("Add a wooden cabin on the left shore")

# Turn 3 — further refine
response3 = chat.send_message("Make it winter, add snow on the peaks")
```

---

## Multi-Image Input (Nano Banana Pro)

Nano Banana Pro (`gemini-3-pro-image-preview`) supports up to **14 input images** for complex composition and identity-consistent generation.

```python
response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=[
        person_image_1,       # PIL Image
        outfit_image_2,       # PIL Image
        background_image_3,   # PIL Image
        "Place the person from image 1, wearing the outfit from image 2, in the setting of image 3"
    ],
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"]
    )
)
```

---

## Models in Detail

### Nano Banana — `gemini-2.5-flash-image`

| Property | Value |
|----------|-------|
| Speed | Fast — optimised for high-volume, low-latency |
| Max input images | 1 (with text) |
| Output resolution | Up to ~1K |
| Multi-turn editing | ✅ |
| Thinking mode | ❌ |
| Search grounding | ❌ |
| Pricing | ~$0.039/image (1290 output tokens × $30/M) |

### Nano Banana 2 — `gemini-3.1-flash-image-preview`

| Property | Value |
|----------|-------|
| Speed | Fast (Flash-tier) |
| Max input images | Multiple |
| Output resolution | Up to 2K |
| Multi-turn editing | ✅ |
| Thinking mode | Limited |
| Search grounding | ✅ |
| Pricing | Check AI Studio |

### Nano Banana Pro — `gemini-3-pro-image-preview`

| Property | Value |
|----------|-------|
| Speed | Slower (Pro-tier thinking) |
| Max input images | 14 |
| Max subjects (identity) | 5 |
| Output resolution | Up to 4K |
| Multi-turn editing | ✅ |
| Thinking mode | ✅ |
| Search grounding | ✅ |
| Text rendering | Exceptional — multilingual, long passages |
| Pricing | Premium; check AI Studio |

---

## Aspect Ratio Reference

| Ratio | Use Case |
|-------|----------|
| `"1:1"` | Square — social media |
| `"16:9"` | Widescreen landscape |
| `"9:16"` | Portrait / Stories |
| `"4:3"` | Standard photo landscape |
| `"3:4"` | Standard photo portrait |
| `"3:2"` | DSLR landscape |
| `"2:3"` | DSLR portrait |
| `"21:9"` | Ultrawide / cinematic |

---

## Vertex AI Access

For enterprise / Google Cloud deployment, use Vertex AI:

```python
import vertexai
from vertexai.generative_models import GenerativeModel, Part

vertexai.init(project="your-gcp-project", location="us-central1")

model = GenerativeModel("gemini-2.5-flash-image")
response = model.generate_content(
    ["Generate an image of a coral reef"],
    generation_config={"response_modalities": ["IMAGE", "TEXT"]}
)
```

---

## Notes

- All output images include an **invisible SynthID watermark** — cannot be removed
- Gemini does not use the OpenAI-style `/images/generations` endpoint — use `generate_content`
- Images are returned as **inline base64 data** (not URLs) — extract and save locally
- `responseModalities: ["IMAGE"]` generates image only; `["TEXT", "IMAGE"]` lets the model also explain what it generated
- Nano Banana Pro uses extended thinking before generating — improves complex prompt following and text rendering at the cost of latency
- The `generate_content` endpoint is unified for text, vision, and image generation — same API for all modalities
- AI Studio playground: `aistudio.google.com` — useful for prompt testing before committing to code
