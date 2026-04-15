import json

import httpx
import pytest

from gateway.models import CanonicalGenerateRequest
from gateway.plugins.base import BackendError
from gateway.plugins.bfl import BflAdapter


@pytest.mark.asyncio
async def test_bfl_adapter_posts_and_polls_until_ready():
    captured: dict[str, object] = {}
    calls = {"poll": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if request.method == "POST" and url == "https://api.bfl.ai/v1/flux-2-pro":
            captured["headers"] = dict(request.headers)
            captured["payload"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": "bfl-job-1",
                    "polling_url": "https://api.bfl.ai/v1/get_result?id=bfl-job-1",
                },
            )

        if request.method == "GET" and url == "https://api.bfl.ai/v1/get_result?id=bfl-job-1":
            calls["poll"] += 1
            if calls["poll"] == 1:
                return httpx.Response(200, json={"id": "bfl-job-1", "status": "Pending"})
            return httpx.Response(
                200,
                json={
                    "id": "bfl-job-1",
                    "status": "Ready",
                    "result": {"sample": "https://delivery-eu.bfl.ai/result.jpg"},
                },
            )

        return httpx.Response(404, json={"error": "unexpected request"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
        poll_interval_seconds=0,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="golden beach at dusk",
        width=1024,
        height=1024,
        output_format="png",
        i2i={
            "source_image": "https://example.com/source.png",
            "strength": 0.6,
        },
        backend_params={"safety_tolerance": 2},
    )

    result = await adapter.generate(request)
    await client.aclose()

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["x-key"] == "secret"

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["prompt"] == "golden beach at dusk"
    assert payload["width"] == 1024
    assert payload["height"] == 1024
    assert payload["output_format"] == "png"
    assert payload["image_prompt"] == "https://example.com/source.png"
    assert payload["image_prompt_strength"] == 0.6
    assert payload["safety_tolerance"] == 2

    assert calls["poll"] >= 2
    assert result.images[0].url == "https://delivery-eu.bfl.ai/result.jpg"


@pytest.mark.asyncio
async def test_bfl_adapter_requires_api_key():
    adapter = BflAdapter(
        api_key=None,
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)


@pytest.mark.asyncio
async def test_bfl_adapter_raises_when_submission_has_no_polling_url():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "bfl-job-1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
        poll_interval_seconds=0,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)

    await client.aclose()


@pytest.mark.asyncio
async def test_bfl_adapter_raises_on_failed_status():
    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if request.method == "POST" and url == "https://api.bfl.ai/v1/flux-2-pro":
            return httpx.Response(
                200,
                json={
                    "id": "bfl-job-1",
                    "polling_url": "https://api.bfl.ai/v1/get_result?id=bfl-job-1",
                },
            )

        if request.method == "GET" and url == "https://api.bfl.ai/v1/get_result?id=bfl-job-1":
            return httpx.Response(200, json={"status": "Error", "detail": "bad prompt"})

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
        poll_interval_seconds=0,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)

    await client.aclose()


@pytest.mark.asyncio
async def test_bfl_adapter_raises_when_ready_without_images():
    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if request.method == "POST" and url == "https://api.bfl.ai/v1/flux-2-pro":
            return httpx.Response(
                200,
                json={
                    "id": "bfl-job-1",
                    "polling_url": "https://api.bfl.ai/v1/get_result?id=bfl-job-1",
                },
            )

        if request.method == "GET" and url == "https://api.bfl.ai/v1/get_result?id=bfl-job-1":
            return httpx.Response(200, json={"status": "Ready", "result": {"seed": 12}})

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
        poll_interval_seconds=0,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)

    await client.aclose()


@pytest.mark.asyncio
async def test_bfl_adapter_raises_on_submit_http_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
        poll_interval_seconds=0,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)

    await client.aclose()


@pytest.mark.asyncio
async def test_bfl_adapter_raises_on_poll_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if request.method == "POST" and url == "https://api.bfl.ai/v1/flux-2-pro":
            return httpx.Response(
                200,
                json={
                    "id": "bfl-job-1",
                    "polling_url": "https://api.bfl.ai/v1/get_result?id=bfl-job-1",
                },
            )

        if request.method == "GET" and url == "https://api.bfl.ai/v1/get_result?id=bfl-job-1":
            return httpx.Response(500, text="internal")

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
        poll_interval_seconds=0,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)

    await client.aclose()


def test_bfl_adapter_parse_json_object_errors():
    with pytest.raises(BackendError):
        BflAdapter._parse_json_object(httpx.Response(200, text="not-json"), context="BFL response")

    with pytest.raises(BackendError):
        BflAdapter._parse_json_object(httpx.Response(200, json=["not", "object"]), context="BFL response")


@pytest.mark.asyncio
async def test_bfl_adapter_accepts_final_payload_without_status():
    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if request.method == "POST" and url == "https://api.bfl.ai/v1/flux-2-pro":
            return httpx.Response(
                200,
                json={
                    "id": "bfl-job-1",
                    "polling_url": "https://api.bfl.ai/v1/get_result?id=bfl-job-1",
                },
            )

        if request.method == "GET" and url == "https://api.bfl.ai/v1/get_result?id=bfl-job-1":
            return httpx.Response(200, json={"result": {"sample": "https://delivery-eu.bfl.ai/result.jpg"}})

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
        poll_interval_seconds=0,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    result = await adapter.generate(request)
    await client.aclose()

    assert result.images[0].url == "https://delivery-eu.bfl.ai/result.jpg"


@pytest.mark.asyncio
async def test_bfl_adapter_times_out_when_poll_never_ready():
    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if request.method == "POST" and url == "https://api.bfl.ai/v1/flux-2-pro":
            return httpx.Response(
                200,
                json={
                    "id": "bfl-job-1",
                    "polling_url": "https://api.bfl.ai/v1/get_result?id=bfl-job-1",
                },
            )

        if request.method == "GET" and url == "https://api.bfl.ai/v1/get_result?id=bfl-job-1":
            return httpx.Response(200, json={"status": "Pending"})

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=0,
        poll_interval_seconds=0,
        client=client,
    )

    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    with pytest.raises(BackendError):
        await adapter.generate(request)

    await client.aclose()


def test_bfl_adapter_build_payload_model_specific_i2i_mappings():
    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
    )

    fill_job = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-pro-1.1-fill",
        prompt="fill it",
        i2i={"source_image": "img-a", "mask": "mask-a"},
    )
    fill_payload = adapter._build_payload(fill_job)
    assert fill_payload["image"] == "img-a"
    assert fill_payload["mask"] == "mask-a"

    kontext_job = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-kontext-pro",
        prompt="edit it",
        i2i={"source_image": "img-b", "strength": 0.8},
    )
    kontext_payload = adapter._build_payload(kontext_job)
    assert kontext_payload["input_image"] == "img-b"


def test_bfl_adapter_extract_helpers_support_multiple_shapes():
    seed_top = BflAdapter._extract_seed({"seed": 11}, fallback_seed=None)
    seed_nested = BflAdapter._extract_seed({"result": {"seed": 12}}, fallback_seed=None)
    assert seed_top == 11
    assert seed_nested == 12

    data = {
        "result": {
            "samples": [{"sample": "https://cdn.example.com/a.png", "width": 10, "height": 20, "format": "png"}],
            "images": [{"image_url": "https://cdn.example.com/b.png"}],
        },
        "images": [{"url": "https://cdn.example.com/c.png"}, 123],
        "output": {"images": ["https://cdn.example.com/d.png"]},
    }

    images = BflAdapter._extract_images(data)
    urls = {img.url for img in images}
    assert "https://cdn.example.com/a.png" in urls
    assert "https://cdn.example.com/b.png" in urls
    assert "https://cdn.example.com/c.png" in urls
    assert "https://cdn.example.com/d.png" in urls


@pytest.mark.asyncio
async def test_bfl_adapter_uses_managed_http_client_when_not_injected(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, follow_redirects: bool = True):
            self.follow_redirects = follow_redirects

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json, headers, timeout):
            return httpx.Response(
                200,
                json={"id": "x", "polling_url": "https://api.bfl.ai/v1/get_result?id=x"},
                request=httpx.Request("POST", url),
            )

        async def get(self, url, headers, timeout):
            return httpx.Response(
                200,
                json={"status": "Ready", "result": {"sample": "https://cdn.example.com/final.png"}},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr("gateway.plugins.bfl.httpx.AsyncClient", FakeAsyncClient)

    adapter = BflAdapter(
        api_key="secret",
        api_base_url="https://api.bfl.ai/v1",
        timeout_seconds=10,
    )
    request = CanonicalGenerateRequest(
        backend="bfl",
        model_ref="flux-2-pro",
        prompt="test",
    )

    result = await adapter.generate(request)
    assert result.images[0].url == "https://cdn.example.com/final.png"
