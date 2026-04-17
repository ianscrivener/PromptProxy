# PromptProxy

PromptProxy is a local FastAPI inference gateway with a canonical API.

Current implementation scope:
- FAL, BFL, DrawThings, and BytePlus upstream backends
- JSONL logging only
- Image download into `test_image_output`
- JSON sidecar per saved image

## Quick start

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
cp .env.example .env
```

Set `FAL_KEY`, `BFL_API_KEY`, and/or `BYTEPLUS_ARK_API_KEY` (or `ARK_API_KEY`) in `.env`, then run:

```bash
pm2 start ecosystem.config.yml --only promptproxy
pm2 save
```

Gateway is managed by PM2 on `127.0.0.1:9999`.

If you need a one-off manual run (without PM2):

```bash
source .venv/bin/activate
uv run uvicorn gateway.main:app --host 127.0.0.1 --port 9999
```

## Tests

```bash
source .venv/bin/activate
uv run pytest
```

## Quick I2I curl test

Start the gateway, then run:

```bash
scripts/test_fal_i2i_curl.sh https://example.com/source.jpg
```

Or use a local source image file:

```bash
scripts/test_fal_i2i_curl.sh ./source.png
```

## Quick BFL T2I curl test

Start the gateway, then run:

```bash
scripts/test_bfl_t2i_curl.sh
```

## PM2 Development Workflow (Port 9999)

Use the committed PM2 ecosystem file:

```bash
pm2 start ecosystem.config.yml --only promptproxy
pm2 save
```

During development, restart via PM2 after changes:

```bash
pm2 restart promptproxy
```

Useful checks:

```bash
pm2 list
curl -sS http://127.0.0.1:9999/v1/providers
curl -sS http://127.0.0.1:9999/v1/providers/fal/models
curl -sS http://127.0.0.1:9999/v1/providers/bfl/models
curl -sS http://127.0.0.1:9999/v1/providers/drawthings/models
curl -sS http://127.0.0.1:9999/v1/providers/byteplus/models
```

`/v1/providers/fal/models` reads from `fal_models.json` in the project root when present.

`/v1/providers/drawthings/models` reads from the local DrawThings gRPC server (`Echo.override.models`) when available.

`/v1/providers/byteplus/models` returns the built-in Seedream/SeedEdit model list exposed by the adapter.

## Quick DrawThings T2I curl test

DrawThings app must be running locally with API Server enabled.

```bash
curl -sS -X POST http://127.0.0.1:9999/v1/generate \
	-H 'Content-Type: application/json' \
	-d '{
		"backend": "drawthings",
		"model_ref": "jibmix_zit_v1.0_fp16_f16.ckpt",
		"prompt": "cinematic photo of a mountain lake at sunrise",
		"width": 1024,
		"height": 1024,
		"backend_params": {
			"sampler": "DPMPP2MTrailing",
			"steps": 8,
			"guidance_scale": 1.5
		}
	}'
```

## Quick BytePlus T2I curl test

Start the gateway, then run:

```bash
scripts/test_byteplus_t2i_curl.sh
```

## BytePlus Behavior in PromptProxy

PromptProxy calls the BytePlus image endpoint directly (`/api/v3/images/generations`) using JSON over HTTP.

For Seedream text-to-image requests:

- The upstream API uses `size` only.
- PromptProxy BytePlus pathway now uses `backend_params.size` for custom sizes (for example `1600x2848`).
- Allowed dimensions are loaded from `seedream-allowed-sizes.json` by `model_series` (`seedream50`, `seedream45`, `seedream40`).
- If requested dimensions are not an exact allowed pair, PromptProxy snaps to the nearest allowed pair.
- Orientation is preserved when snapping (portrait stays portrait, landscape stays landscape).

Examples:

- `1600x3000` with `seedream45` resolves to `1600x2848`.
- `3000x1600` with `seedream45` resolves to `2848x1600`.
- `1100x1000` with `seedream40` resolves to `1024x1024`.

`scripts/test_byteplus_t2i_curl.sh` supports overriding `MODEL_REF`, `MODEL_SERIES`, `SIZE`, and `BYTEPLUS_PROMPT` for quick validation.

## API Docs

When the gateway is running, use:

- Swagger UI: http://127.0.0.1:9999/docs/swagger
- OpenAPI JSON: http://127.0.0.1:9999/openapi.json
- OpenAPI YAML: http://127.0.0.1:9999/openapi.yaml
