import json

import httpx
import pytest

from gateway.models import CanonicalGenerateRequest
from gateway.plugins.base import BackendError
from gateway.plugins.fal import FalAdapter


@pytest.mark.asyncio
async def test_fal_adapter_translates_request_and_parses_response():
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "images": [{"url": "https://cdn.example.com/result.png", "width": 1024, "height": 1024}],
                "seed": 123,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = FalAdapter(
        api_key="secret",
        api_base_url="https://queue.fal.run",
        timeout_seconds=30,
        client=client,
    )
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="a lighthouse",
        aspect_ratio="16:9",
        i2i={
            "source_image": "https://example.com/source.png",
            "strength": 0.7,
            "mask": "https://example.com/mask.png",
        },
        backend_params={"safety_tolerance": 2},
    )

    result = await adapter.generate(request)
    await client.aclose()

    assert captured["url"] == "https://queue.fal.run/fal-ai/flux/dev"
    assert captured["auth"] == "Key secret"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["prompt"] == "a lighthouse"
    assert payload["aspect_ratio"] == "16:9"
    assert payload["image_url"] == "https://example.com/source.png"
    assert payload["strength"] == 0.7
    assert payload["mask_url"] == "https://example.com/mask.png"
    assert "i2i" not in payload
    assert payload["safety_tolerance"] == 2
    assert result.seed_used == 123
    assert result.images[0].url == "https://cdn.example.com/result.png"


@pytest.mark.asyncio
async def test_fal_adapter_parses_nested_image_response():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"images": ["https://cdn.example.com/a.webp"], "seed": 44}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = FalAdapter(
        api_key="secret",
        api_base_url="https://queue.fal.run",
        timeout_seconds=30,
        client=client,
    )
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="stormy sea",
    )

    result = await adapter.generate(request)
    await client.aclose()

    assert result.seed_used == 44
    assert result.images[0].url == "https://cdn.example.com/a.webp"


@pytest.mark.asyncio
async def test_fal_adapter_requires_api_key():
    adapter = FalAdapter(
        api_key=None,
        api_base_url="https://queue.fal.run",
        timeout_seconds=30,
    )
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)


@pytest.mark.asyncio
async def test_fal_adapter_raises_on_http_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = FalAdapter(
        api_key="secret",
        api_base_url="https://queue.fal.run",
        timeout_seconds=30,
        client=client,
    )
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)
    await client.aclose()


@pytest.mark.asyncio
async def test_fal_adapter_raises_when_no_images_present():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = FalAdapter(
        api_key="secret",
        api_base_url="https://queue.fal.run",
        timeout_seconds=30,
        client=client,
    )
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)
    await client.aclose()


@pytest.mark.asyncio
async def test_fal_adapter_resolves_async_submission_with_polling():
    calls = {"status": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if url == "https://queue.fal.run/fal-ai/flux/dev":
            return httpx.Response(
                200,
                json={
                    "status": "IN_QUEUE",
                    "request_id": "req-1",
                    "response_url": "https://queue.fal.run/fal-ai/flux/requests/req-1",
                    "status_url": "https://queue.fal.run/fal-ai/flux/requests/req-1/status",
                },
            )

        if url == "https://queue.fal.run/fal-ai/flux/requests/req-1/status":
            calls["status"] += 1
            if calls["status"] == 1:
                return httpx.Response(200, json={"status": "IN_PROGRESS"})
            return httpx.Response(200, json={"status": "COMPLETED"})

        if url == "https://queue.fal.run/fal-ai/flux/requests/req-1":
            return httpx.Response(
                200,
                json={
                    "images": [{"url": "https://cdn.example.com/final.png"}],
                    "seed": 77,
                },
            )

        return httpx.Response(404, json={"error": "unexpected url"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = FalAdapter(
        api_key="secret",
        api_base_url="https://queue.fal.run",
        timeout_seconds=10,
        client=client,
    )
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="test async",
    )

    result = await adapter.generate(request)
    await client.aclose()

    assert result.images[0].url == "https://cdn.example.com/final.png"
    assert result.seed_used == 77
    assert calls["status"] >= 2
