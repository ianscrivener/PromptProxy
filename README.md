# PromptProxy

PromptProxy is a local FastAPI inference gateway with a canonical API.

Current implementation scope:
- FAL upstream only
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

Set `FAL_KEY` in `.env`, then run:

```bash
source .venv/bin/activate
uv run uvicorn gateway.main:app --host 127.0.0.1 --port 8000
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
