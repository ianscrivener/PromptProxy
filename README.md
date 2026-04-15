# PromptProxy

PromptProxy is a local FastAPI inference gateway with a canonical API.

Current implementation scope:
- FAL and BFL upstream backends
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

Set `FAL_KEY` and/or `BFL_API_KEY` in `.env`, then run:

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
