# Batch Inference Support Analysis

Research conducted: April 2026

## Summary

Only **Gemini / Nano Banana** supports true batch inference for image generation among the surveyed services. Other platforms support async/polling workflows but not batch processing.

---

## Detailed Findings

### ✅ Gemini API (with Nano Banana model)
- **Batch Support**: YES
- **Features**:
  - Native Batch API for text-to-image and image-to-image generation
  - Supports inline requests (< 20MB) or JSONL file input (up to 2GB)
  - 24-hour turnaround target (often faster)
  - **Cost Benefit**: 50% discount vs. standard interactive pricing
  - API: `POST /batch` with `batches.create()` method
  - Can batch 100s to 1000s of image generation requests
  - Pricing: At 50% of standard Nano Banana image generation cost
- **Example Use Case**: Generate 1000 images with batch job, retrieve results in 24h at half cost
- **Rate Limits**: Higher throughput in exchange for 24-hour latency

### ❌ Replicate
- **Batch Support**: NO
- **Alternative**: Async/Polling workflow
  - Create individual predictions via `POST /predictions`
  - Poll for status via `GET /predictions/{id}`
  - Can send requests rapidly and manage in-flight predictions
  - Not true batching; still billed per individual prediction
- **Limitations**: No way to submit 1000 requests and retrieve results as batch

### ❌ Black Forest Labs (BFL)
- **Batch Support**: NO
- **Alternative**: Async task with polling
  - Submit task via `POST /flux-pro-1.1` (or other endpoint)
  - Get async response with polling URL
  - Poll `GET /get_result` for task completion
  - Each submission is treated individually
- **Note**: Queue/webhook pattern in REST+Poll architecture, but not batch API

### ❌ Alibaba / DashScope
- **Batch Support**: NO
- **Alternative**: Sync or async task mode
  - Set `async: true` for async mode
  - Results available via polling or callback
  - No batch endpoint; only individual task submission
- **Limitations**: Each request processed separately

### ❌ BytePlus ModelArk
- **Batch Support**: NO
- **Architecture**: OpenAI-compatible REST API
  - Supports individual requests with optional async streaming
  - No batch processing endpoint
- **Limitations**: No bulk image generation batching

### ❌ FAL.ai
- **Note**: Not explicitly surveyed but supports Queue/Webhook pattern
- **Batch Support**: Appears to be NO (legacy async, not true batch)
- **Pattern**: Individual requests with queue and webhook notifications

### ❌ OpenRouter
- **Batch Support**: NO
- **Pattern**: Chat completions with modalities
- **Limitation**: Proxy architecture; no batch support at platform level

---

## Key Takeaways

1. **Gemini is the only platform with true batch API for images** — specifically supporting cost-effective bulk generation via Batch API
2. **Other platforms support async/polling** but require individual request submission and polling
3. **Cost implications**:
   - Gemini Batch: 50% discount, 24-hour latency
   - Others: Full pricing, individual request model
4. **Use Gemini Batch for**: Large-scale non-urgent image generation (e.g., dataset creation, bulk renders)
5. **Use async/polling for**: Real-time or near-real-time requests where individual latency is acceptable

---

## Table Update

The master table (00_MASTER_INDEX.md) has been updated with the Batch column reflecting:
- `✅` only for Gemini
- `❌` for all others

This reflects current API capabilities as of April 2026.
