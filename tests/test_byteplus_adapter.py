import json

import httpx
import pytest

from gateway.models import CanonicalGenerateRequest
import gateway.plugins.byteplus as byteplus_module
from gateway.plugins.base import BackendError
from gateway.plugins.byteplus import BytePlusAdapter


@pytest.mark.asyncio
async def test_byteplus_adapter_posts_payload_and_parses_url_response():
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "created": 1744600000,
                "data": [{"url": "https://ark-img.bytepluses.com/result.png"}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seedream-5-0-t2i-250624",
        prompt="night city skyline",
        num_images=2,
        guidance_scale=3.5,
        backend_params={"size": "2304x1728", "watermark": False},
    )

    result = await adapter.generate(request)
    await client.aclose()

    assert captured["url"] == "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
    assert captured["auth"] == "Bearer secret"

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "seedream-5-0-t2i-250624"
    assert payload["prompt"] == "night city skyline"
    assert payload["size"] == "2304x1728"
    assert payload["n"] == 2
    assert payload["guidance_scale"] == 3.5
    assert payload["watermark"] is False

    assert result.seed_used is None
    assert result.raw_request is not None
    assert result.raw_request["payload"] == payload
    assert result.images[0].url == "https://ark-img.bytepluses.com/result.png"


@pytest.mark.asyncio
async def test_byteplus_adapter_parses_b64_response():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "seed": 99,
                "data": [{"b64_json": "dGVzdA=="}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
        client=client,
    )
    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seedream-5-0-t2i-250624",
        prompt="coral reef",
    )

    result = await adapter.generate(request)
    await client.aclose()

    assert result.seed_used == 99
    assert result.images[0].url == "data:image/png;base64,dGVzdA=="


@pytest.mark.asyncio
async def test_byteplus_adapter_requires_api_key():
    adapter = BytePlusAdapter(
        api_key=None,
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )
    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seedream-5-0-t2i-250624",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)


@pytest.mark.asyncio
async def test_byteplus_adapter_raises_on_http_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
        client=client,
    )
    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seedream-5-0-t2i-250624",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)

    await client.aclose()


@pytest.mark.asyncio
async def test_byteplus_adapter_raises_when_no_images_present():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"created": 1744600000, "data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
        client=client,
    )
    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seedream-5-0-t2i-250624",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)

    await client.aclose()


def test_byteplus_adapter_build_payload_for_i2i_with_overrides():
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seededit-3-0-i2i-250628",
        prompt="make the background tropical",
        i2i={
            "source_image": "https://example.com/source.png",
            "strength": 0.7,
        },
        backend_params={
            "size": "1024x1024",
            "response_format": "b64_json",
            "watermark": False,
        },
    )

    payload = adapter._build_payload(request)

    assert payload["image"] == "https://example.com/source.png"
    assert payload["size"] == "1024x1024"
    assert payload["response_format"] == "b64_json"
    assert payload["watermark"] is False


def test_byteplus_adapter_build_payload_rejects_unsupported_features():
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )

    with pytest.raises(BackendError):
        adapter._build_payload(
            CanonicalGenerateRequest(
                backend="byteplus",
                model_ref="seedream-5-0-t2i-250624",
                prompt="test",
                loras=[{"name": "style-a.safetensors", "weight": 0.8}],
            )
        )

    with pytest.raises(BackendError):
        adapter._build_payload(
            CanonicalGenerateRequest(
                backend="byteplus",
                model_ref="seededit-3-0-i2i-250628",
                prompt="test",
                i2i={
                    "source_image": "https://example.com/source.png",
                    "mask": "https://example.com/mask.png",
                },
            )
        )


def test_byteplus_adapter_size_validation_when_explicitly_used():
    assert BytePlusAdapter._normalize_size("2k") == "2K"
    assert BytePlusAdapter._normalize_size("adaptive") == "adaptive"
    assert BytePlusAdapter._normalize_size("1600x2848") == "1600x2848"

    with pytest.raises(BackendError):
        BytePlusAdapter._normalize_size("512")


def test_byteplus_adapter_uses_adaptive_size_for_i2i_without_dimensions():
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seededit-3-0-i2i-250628",
        prompt="change background",
        i2i={"source_image": "https://example.com/source.png"},
    )

    payload = adapter._build_payload(request)
    assert payload["size"] == "adaptive"


def test_byteplus_adapter_validates_dimensions_with_model_series_argument():
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="ep-20260123162415-2wr9p",
        prompt="cinematic airport lounge",
        backend_params={
            "size": "3520x4704",
            "model_series": "seedream45",
            "watermark": False,
            "model": "seedream-5-0-t2i-250624",
        },
    )

    payload = adapter._build_payload(request)
    assert payload["model"] == "ep-20260123162415-2wr9p"
    assert payload["size"] == "3520x4704"
    assert payload["watermark"] is False
    assert "model_series" not in payload


def test_byteplus_adapter_snaps_unknown_dimensions_for_model_series():
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="ep-20260123162415-2wr9p",
        prompt="cinematic airport lounge",
        backend_params={"size": "1600x3000", "model_series": "seedream45"},
    )

    payload = adapter._build_payload(request)
    assert payload["size"] == "1600x2848"


def test_byteplus_adapter_allows_custom_size_without_model_series():
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="ep-20260123162415-2wr9p",
        prompt="cinematic airport lounge",
        backend_params={"size": "3520x4704"},
    )

    payload = adapter._build_payload(request)
    assert payload["size"] == "3520x4704"


def test_byteplus_adapter_snaps_landscape_orientation_to_nearest_allowed_size():
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="ep-20260123162415-2wr9p",
        prompt="cinematic airport lounge",
        backend_params={"size": "3000x1600", "model_series": "seedream45"},
    )

    payload = adapter._build_payload(request)
    assert payload["size"] == "2848x1600"


def test_byteplus_size_pair_helpers_support_new_json_pair_format():
    assert byteplus_module._extract_size_pair([3520, 4704]) == (3520, 4704)
    assert byteplus_module._extract_size_pair({"width": 3520, "height": 4704}) == (3520, 4704)
    assert byteplus_module._extract_size_pair([3520]) is None

    assert byteplus_module._canonical_size_pair(3520, 4704) == (3520, 4704)
    assert byteplus_module._canonical_size_pair(4704, 3520) == (3520, 4704)


def test_byteplus_adapter_treats_allowed_size_pairs_as_orientation_agnostic(monkeypatch):
    monkeypatch.setattr(
        byteplus_module,
        "_ALLOWED_SEEDREAM_SIZES",
        {"seedream45": {(3520, 4704)}},
    )

    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="ep-20260123162415-2wr9p",
        prompt="cinematic airport lounge",
        backend_params={"size": "4704x3520", "model_series": "seedream45"},
    )

    payload = adapter._build_payload(request)
    assert payload["size"] == "4704x3520"


@pytest.mark.asyncio
async def test_byteplus_adapter_parses_wrapped_body_response():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {},
                "body": {
                    "seed": 777,
                    "data": [{"url": "https://ark-img.bytepluses.com/wrapped.png"}],
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BytePlusAdapter(
        api_key="secret",
        api_base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        timeout_seconds=30,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="byteplus",
        model_ref="seedream-5-0-t2i-250624",
        prompt="wrapped response test",
    )

    result = await adapter.generate(request)
    await client.aclose()

    assert result.seed_used == 777
    assert result.images[0].url == "https://ark-img.bytepluses.com/wrapped.png"
