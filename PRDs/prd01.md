# PRD: PromptProxy 01

**Project codename:** `PromptProxy`  
**Status:** Draft v0.2  
**Author:** Scriv  
**Date:** 2026-04-14  

---

## 1. Overview

**PromptProxy ** is a local Python inference gateway that presents a single unified HTTP API in front of multiple image generation backends — hosted APIs (FAL, Replicate, BFL, Alibaba, BytePlus) and local inference servers (DrawThings gRPC, and future local inference servers). It normalises inbound requests to a canonical job schema, dispatches to the appropriate backend adapter, optionally logs all inference parameters to one or more backends, optionally writes a sidecar JSON per rendered image, and returns results to the caller in a normalised response envelope.

A lightweight HTMX dashboard (served from the same process) provides live job monitoring, backend status, and log browsing.

The system is modular: the core handles routing, logging, sidecar writing, and the dashboard. Each upstream inference service is a self-contained plugin (Python module implementing a common adapter interface). Adding a new backend requires adding one file.

---

## 2. Goals & Non-Goals

### Goals
- Unified inbound HTTP API regardless of which backend executes the job
- Canonical job schema derived from the union of all major inference engine schemas
- Per-job logging to configurable backends (Postgres, JSONL, SQLite — any combination, multi-write)
- Per-job sidecar JSON written to a configurable path
- Backend adapter plugin system — one module per upstream service
- HTMX dashboard: job list, job detail, metrics for jobs, upstream jobs histograms, backend health etc
- Runs under PM2 on macOS
- gRPC support for DrawThings (via `grpcio`) as a first-class backend plugin
- Configurable field exclusion filter for log noise reduction

### Non-Goals
- Image byte capture or re-serving (caller gets URLs or base64 directly from upstream)
- Authentication/authorisation on the inbound API (localhost trust model, v1)
- Multi-user or remote deployment (v1)
- ComfyUI node-graph translation (treat as opaque blob if added later)
- Outbound webhook delivery (v1 — callers poll or await synchronously)

---

## 3. Architecture

```
Caller (agent / script / Claude skill / curl)
        │
        │  HTTP  POST /v1/generate
        ▼
┌─────────────────────────────────────────────────┐
│                  gen-gateway                     │
│                                                  │
│  FastAPI + uvicorn                               │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  Inbound API  /v1/generate              │    │
│  │  • Validate canonical request           │    │
│  │  • Assign job_id (UUID v4)              │    │
│  │  • Route to adapter by backend name     │    │
│  └──────────────┬──────────────────────────┘    │
│                 │                                │
│  ┌──────────────▼──────────────────────────┐    │
│  │  Job Lifecycle                          │    │
│  │  • Write log record (async, multi-sink) │    │
│  │  • Write sidecar JSON                   │    │
│  │  • Dispatch to backend adapter          │    │
│  │  • Normalise response                   │    │
│  │  • Update log record with result        │    │
│  └──────────────┬──────────────────────────┘    │
│                 │                                │
│  ┌──────────────▼──────────────────────────┐    │
│  │  Plugin Registry                        │    │
│  │  fal │ replicate │ bfl │ alibaba        │    │
│  │  byteplus │ drawthings │ openrouter     │    │
│  └──────────────┬──────────────────────────┘    │
│                 │                                │
│  ┌──────────────▼──────────────────────────┐    │
│  │  Log Sinks (async, fire-and-forget)     │    │
│  │  Postgres │ JSONL │ SQLite              │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  HTMX Dashboard  /dashboard             │    │
│  │  Job list │ Job detail │ Backend status │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
        │
        │  Per adapter: HTTP or gRPC
        ▼
  ┌─────────┐  ┌──────────┐  ┌──────┐  ┌────────────┐
  │   FAL   │  │Replicate │  │ BFL  │  │DrawThings  │
  │  HTTPS  │  │  HTTPS   │  │HTTPS │  │   gRPC     │
  └─────────┘  └──────────┘  └──────┘  └────────────┘
```

---

## 4. Canonical Job Schema

Derived from the union of all eight API schemas in the project research docs. Split into three tiers.

### 4.1 Envelope (always present)

| Field | Type | Description |
|---|---|---|
| `job_id` | UUID v4 | Assigned by gateway at receipt |
| `proxy_timestamp` | ISO 8601 UTC | Request receipt time |
| `gateway_version` | string | Semver of gen-gateway |
| `backend` | string | Adapter name: `fal`, `replicate`, `bfl`, `alibaba`, `byteplus`, `drawthings`, `openrouter` |
| `model_ref` | string | Backend-specific model identifier (see §4.4) |
| `status` | enum | `pending` → `dispatched` → `succeeded` \| `failed` |
| `result` | object \| null | Normalised result (see §6) |
| `error` | string \| null | Error message if failed |

### 4.2 Common Generation Fields (optional, typed)

Present in most backends. Gateway passes these through to adapters; adapters translate to backend-native field names.

| Field | Type | Notes |
|---|---|---|
| `prompt` | string | **required** |
| `negative_prompt` | string | Absent: Gemini, Alibaba Wan, BFL |
| `width` | integer | Mutually exclusive with `aspect_ratio` |
| `height` | integer | Mutually exclusive with `aspect_ratio` |
| `aspect_ratio` | string | e.g. `"16:9"` — preferred for API-hosted models |
| `num_inference_steps` | integer | `steps` in DrawThings; absent in Gemini/Alibaba |
| `guidance_scale` | float | `cfg_scale` in DrawThings; absent in BFL/Gemini |
| `seed` | integer | Absent in Gemini, Alibaba |
| `num_images` | integer | `n` in Alibaba/BytePlus; absent in BFL/OpenRouter |
| `output_format` | string | `jpeg`, `png`, `webp` — normalised across backends |
| `loras` | array of `{name, weight}` | SD-style backends only |
| `i2i` | object | See §4.3 |

### 4.3 Image-to-Image Sub-Schema

| Field | Type | Notes |
|---|---|---|
| `i2i.source_image` | string | URL or base64 |
| `i2i.strength` | float | 0–1; `denoising_strength` in DrawThings |
| `i2i.mask` | string | URL or base64; for inpainting |

### 4.4 Backend Params (opaque passthrough)

```json
"backend_params": {
  "prompt_upsampling": true,
  "thinking_mode": false,
  "safety_tolerance": 2,
  "go_fast": true
}
```

Anything not in the common fields schema goes here. The adapter receives both the typed common fields and `backend_params` raw — it decides what to do with each. This means backend-specific features are always accessible without schema changes to the gateway.

### 4.4 Model Ref Convention

Each backend has its own model identifier format. `model_ref` stores it verbatim:

| Backend | Example `model_ref` |
|---|---|
| FAL | `fal-ai/flux/dev` |
| Replicate | `black-forest-labs/flux-1.1-pro` |
| BFL | `flux-2-pro` |
| Alibaba | `wan2.7-image-pro` |
| BytePlus | `seedream-5-0-t2i-250624` |
| DrawThings | `flux_qwen_srpo_v1.0_f16.ckpt` |
| OpenRouter | `black-forest-labs/flux.2-pro` |

---

## 5. Inbound API

### 5.1 Generate

```
POST /v1/generate
Content-Type: application/json
```

Request body is the canonical job schema (§4), minus envelope fields (those are assigned by the gateway).

Minimal example:
```json
{
  "backend": "fal",
  "model_ref": "fal-ai/flux/dev",
  "prompt": "Aerial photo of Wangi Wangi at sunset, Lake Macquarie",
  "aspect_ratio": "16:9",
  "output_format": "jpeg",
  "seed": 42
}
```

Full example with backend_params and I2I:
```json
{
  "backend": "replicate",
  "model_ref": "black-forest-labs/flux-1.1-pro",
  "prompt": "transform into watercolour style",
  "negative_prompt": "blurry, low quality",
  "seed": 1234,
  "output_format": "png",
  "i2i": {
    "source_image": "https://example.com/photo.jpg",
    "strength": 0.7
  },
  "backend_params": {
    "safety_tolerance": 3,
    "output_quality": 90
  }
}
```

### 5.2 Job Status

```
GET /v1/jobs/{job_id}
```

Returns the full job record including status, all input params, and result/error.

### 5.3 Job List

```
GET /v1/jobs?backend=fal&status=succeeded&limit=50&offset=0
```

Filterable by backend, status, model_ref, date range.

### 5.4 Backend Health

```
GET /v1/backends
```

Returns registered adapters and their current reachability status.

---

## 6. Normalised Response

All adapters return a `CanonicalResult` regardless of backend:

```json
{
  "job_id": "3f2a1c7e-...",
  "status": "succeeded",
  "backend": "fal",
  "model_ref": "fal-ai/flux/dev",
  "images": [
    {
      "url": "https://fal.media/files/...",
      "width": 1366,
      "height": 768,
      "format": "jpeg"
    }
  ],
  "seed_used": 42,
  "duration_ms": 3420,
  "prompt": "Aerial photo of Wangi Wangi...",
  "gateway_version": "0.1.0",
  "proxy_timestamp": "2026-04-14T03:22:11.847Z"
}
```

For backends that return base64 (Gemini, DrawThings, OpenRouter): the adapter normalises to URL by writing the image to a local static file directory and returning a `localhost` URL. Configurable via `STATIC_IMAGE_PATH` and `STATIC_IMAGE_BASE_URL`.

---

## 7. Sidecar JSON

Written per job to `SIDECAR_PATH/{job_id}.json` on job completion (success or failure). Contains the full canonical job record including result. This is the primary artefact for Satchel ingestion.

Correlation with DrawThings-saved images: callers should name their output file `{job_id}.png`. The gateway does not enforce this but documents it as the convention. Satchel matches on filename stem.

---

## 8. Logging Backends

Identical to dt-proxy PRD §8 — multi-write, fire-and-forget async, failed sinks don't block others. Log record schema mirrors canonical job schema; `loras`, `i2i`, and `backend_params` stored as JSONB (Postgres) or JSON string (SQLite/JSONL).

One addition: the log record is written **twice** — once at dispatch (status: `pending`, params captured) and updated on completion (status: `succeeded`/`failed`, result/error appended). This means params are always persisted even if the backend call hangs or crashes.

| Variable | Default | Description |
|---|---|---|
| `LOG_BACKENDS` | `jsonl` | Comma-separated: `jsonl`, `sqlite`, `postgres` |
| `LOG_EXCLUDE_FIELDS` | *(empty)* | Comma-separated field names to omit from all log writes |
| `JSONL_PATH` | `~/gen-gateway.jsonl` | |
| `SQLITE_PATH` | `~/gen-gateway.db` | |
| `DATABASE_URL` | *(unset)* | Postgres connection string |

---

## 9. Plugin Architecture

### 9.1 Adapter Interface

Every backend plugin implements this ABC:

```python
from abc import ABC, abstractmethod
from gateway.models import CanonicalJob, CanonicalResult

class BackendAdapter(ABC):

    name: str                    # matches "backend" field in requests
    display_name: str            # human-readable, shown in dashboard
    supports_i2i: bool = False
    supports_loras: bool = False

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the backend is reachable."""

    @abstractmethod
    async def generate(self, job: CanonicalJob) -> CanonicalResult:
        """Translate, dispatch, and normalise. Raise BackendError on failure."""
```

Adapters handle their own async patterns internally — polling loops for BFL/Replicate/Alibaba are encapsulated in the adapter, not visible to the core.

### 9.2 Plugin Registration

Adapters are registered in `gateway/plugins/__init__.py`. The plugin registry is a simple dict `{name: AdapterClass}`. The core resolves the adapter at request time by `job.backend`.

### 9.3 Build Order

Plugins will be built in this sequence, each one proving out the architecture before adding complexity:

| Phase | Plugin | Why |
|---|---|---|
| 1 | **FAL** | Simplest auth, sync mode available, clean response schema. Proves core + logging + sidecar. |
| 2 | **Replicate** | Introduces async polling pattern. Proves adapter encapsulation of async. |
| 3 | **BFL** | Second polling pattern (different shape). Proves polling is generalised. |
| 4 | **Alibaba** | Introduces multimodal request shape (messages array). |
| 5 | **BytePlus** | OpenAI-compat — near-trivial after FAL. |
| 6 | **DrawThings** | Introduces gRPC transport. Proves plugin interface works across transport types. |
| 7 | **OpenRouter** | Oddball chat-completions shape. Last because most divergent. |
| 8 | **Gemini** | Direct API, inline base64 images — needs static file serving. |

---

## 10. HTMX Dashboard

Served at `/dashboard` from the same FastAPI process. No JS build step — HTMX via CDN, server-rendered Jinja2 fragments. Tailwind CSS via CDN for styling.

### Pages

**Job List** (`/dashboard/jobs`)
- Reverse-chronological table: job_id (truncated), timestamp, backend, model_ref, status, duration
- Filter controls: backend dropdown, status, date range
- HTMX infinite scroll or pagination
- Click row → Job Detail (HTMX swap)

**Job Detail** (`/dashboard/jobs/{job_id}`)
- Full param display: prompt, all common fields, backend_params as pretty JSON
- Result images (thumbnail if URL; inline if base64-served locally)
- Sidecar JSON download link
- Copy `job_id` button (for Satchel correlation)

**Backend Status** (`/dashboard/backends`)
- Card per registered adapter: name, reachable (live-polling via HTMX), last job timestamp
- Manual health-check trigger button per backend

### Non-goals for dashboard
- Auth (localhost only)
- Image editing or prompt submission (read-only, v1)
- Realtime streaming (HTMX polling is sufficient)

---

## 11. Configuration Reference

**Secrets only** (`.env` via `python-dotenv`):
- `FAL_KEY` — FAL API key (required for FAL plugin)
- `REPLICATE_API_TOKEN` — Replicate token (required for Replicate plugin)
- `BFL_API_KEY` — BFL key (required for BFL plugin)
- `DASHSCOPE_API_KEY` — DashScope key (required for Alibaba plugin)
- `ARK_API_KEY` — BytePlus key (required for BytePlus plugin)
- `OPENROUTER_API_KEY` — OpenRouter key (required for OpenRouter plugin)
- `GEMINI_API_KEY` — Gemini key (required for Gemini plugin)
- `DATABASE_URL` — Postgres DSN (required if Postgres logging enabled)

Backend API keys are only required if that plugin is active. Missing keys cause the plugin to register as `unavailable` in the health endpoint rather than crashing the gateway.

**Configuration** (`config.yaml`):

| Variable | Default | Description |
|---|---|---|
| `gateway_port` | `8000` | Inbound HTTP listen port |
| `gateway_host` | `127.0.0.1` | Bind address |
| `gateway_version` | *(from package)* | Override version string in records |
| `log_backends` | `jsonl` | Comma-separated log sinks: `jsonl`, `sqlite`, `postgres` |
| `log_exclude_fields` | *(empty)* | Comma-separated field names to omit from all log writes |
| `jsonl_path` | `~/gen-gateway.jsonl` | JSONL log file path |
| `sqlite_path` | `~/gen-gateway.db` | SQLite database path |
| `sidecar_enabled` | `true` | Enable/disable sidecar JSON writes |
| `sidecar_path` | *(required if enabled)* | Directory for sidecar JSON files |
| `static_image_path` | `~/gen-gateway/images` | Local image storage for base64 responses |
| `static_image_base_url` | `http://localhost:8000/images` | URL prefix for locally stored images |
| `drawthings_host` | `localhost:7859` | DrawThings gRPC address |

---

## 12. Python Stack

| Component | Library |
|---|---|
| HTTP framework | `fastapi` |
| ASGI server | `uvicorn` |
| Async HTTP client | `httpx` |
| gRPC (DrawThings) | `grpcio`, `grpcio-reflection`, `grpcio-tools` |
| Postgres | `asyncpg` |
| SQLite | stdlib `sqlite3` |
| Templating (dashboard) | `jinja2` |
| Env/config | `pydantic-settings` |
| Validation | `pydantic` v2 |
| UUID | stdlib `uuid` |
| Packaging | `uv` + `pyproject.toml` |
| Process manager | PM2 |

Python 3.11+ required.

---

## 13. PM2 Configuration

```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: "gen-gateway",
    script: ".venv/bin/uvicorn",
    args: "gateway.main:app --host 127.0.0.1 --port 8000",
    cwd: "/path/to/gen-gateway",
    env_file: ".env",
    watch: false,
    autorestart: true,
    max_restarts: 10,
    restart_delay: 2000,
    out_file: "~/Library/Logs/gen-gateway/out.log",
    error_file: "~/Library/Logs/gen-gateway/err.log",
    log_date_format: "YYYY-MM-DD HH:mm:ss"
  }]
}
```

Start: `pm2 start ecosystem.config.js`  
Save to startup: `pm2 save && pm2 startup`

---

## 14. Directory Structure

```
gen-gateway/
├── pyproject.toml
├── ecosystem.config.js
├── .env.example
├── .gitignore
├── README.md
├── proto/
│   └── drawthings.proto            # fallback static proto
├── gateway/
│   ├── main.py                     # FastAPI app, route registration
│   ├── models.py                   # CanonicalJob, CanonicalResult, pydantic schemas
│   ├── config.py                   # pydantic-settings config
│   ├── router.py                   # /v1/ API routes
│   ├── job_lifecycle.py            # assign UUID, log, sidecar, dispatch, update
│   ├── sidecar.py                  # sidecar JSON writer
│   ├── registry.py                 # plugin registry
│   ├── dashboard/
│   │   ├── routes.py               # /dashboard/ routes
│   │   └── templates/
│   │       ├── base.html
│   │       ├── job_list.html
│   │       ├── job_detail.html
│   │       └── backends.html
│   ├── sinks/
│   │   ├── __init__.py
│   │   ├── base.py                 # LogSink ABC
│   │   ├── jsonl.py
│   │   ├── sqlite.py
│   │   └── postgres.py
│   └── plugins/
│       ├── __init__.py             # registry population
│       ├── base.py                 # BackendAdapter ABC
│       ├── fal.py                  # Phase 1
│       ├── replicate.py            # Phase 2
│       ├── bfl.py                  # Phase 3
│       ├── alibaba.py              # Phase 4
│       ├── byteplus.py             # Phase 5
│       ├── drawthings.py           # Phase 6 — gRPC
│       ├── openrouter.py           # Phase 7
│       └── gemini.py               # Phase 8
└── tests/
    ├── test_canonical_schema.py
    ├── test_job_lifecycle.py
    ├── test_sidecar.py
    ├── test_sinks.py
    └── plugins/
        ├── test_fal.py
        └── test_replicate.py
```

---

## 15. Open Questions

| # | Question | Status |
|---|---|---|
| 1 | Does DrawThings expose gRPC server reflection? Verify against live instance before Phase 6. | Open |
| 2 | For base64-response backends (Gemini, DrawThings, OpenRouter): serve from gateway's static dir, or write to `STATIC_IMAGE_PATH` and expect Satchel to watch that dir? | write to `STATIC_IMAGE_PATH` |
| 3 | Should the dashboard be read-only v1, or include a prompt submission form early? | Read only |
| 4 | PM2 startup on macOS — use `pm2 startup` launchd integration or a separate LaunchAgent wrapping PM2? | Decision pending |
| 5 | Sidecar written on dispatch or on completion? (On dispatch: params always captured. On completion: result included.) Recommendation: write on dispatch, update on completion. | write on dispatch, update on completion |

---

## 16. Out of Scope (Future)

- Streaming responses (FLUX Kontext, Gemini stream mode)
- Webhook delivery to callers
- Prompt template library
- Cost tracking / budget alerts per backend
- ComfyUI node-graph adapter
- Remote/networked deployment with auth
- A1111-compatible inbound API (accept A1111-format requests, translate to canonical)
