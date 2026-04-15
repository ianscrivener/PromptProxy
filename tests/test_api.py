import json
from pathlib import Path

import httpx
import pytest

from gateway.main import create_app
from gateway.models import CanonicalGenerateRequest, CanonicalImage, CanonicalResult
from gateway.plugins.base import BackendAdapter


class ApiSuccessAdapter(BackendAdapter):
    name = "fal"
    display_name = "FAL"

    async def health_check(self) -> bool:
        return True

    async def generate(self, _: CanonicalGenerateRequest) -> CanonicalResult:
        return CanonicalResult(images=[CanonicalImage(url="https://cdn.example.com/api.png")], seed_used=55)


class ApiBflAdapter(BackendAdapter):
    name = "bfl"
    display_name = "BFL"

    async def health_check(self) -> bool:
        return False

    async def generate(self, _: CanonicalGenerateRequest) -> CanonicalResult:
        return CanonicalResult(images=[])


def _write_runtime_files(tmp_path: Path) -> tuple[Path, Path]:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "gateway_host: 127.0.0.1",
                "gateway_port: 8000",
                "gateway_version: 0.1.0",
                "jsonl_path: logs/events.jsonl",
                "image_output_path: test_image_output",
                "sidecar_enabled: true",
                "static_image_base_url: http://127.0.0.1:8000/images",
                "fal_api_base_url: https://queue.fal.run",
            ]
        ),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text("FAL_KEY=test-key\n", encoding="utf-8")
    return config_path, env_path


@pytest.mark.asyncio
async def test_generate_endpoint_full_flow(tmp_path):
    async def image_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://cdn.example.com/api.png":
            return httpx.Response(200, content=b"api-image", headers={"Content-Type": "image/png"})
        return httpx.Response(404)

    config_path, env_path = _write_runtime_files(tmp_path)
    image_client = httpx.AsyncClient(transport=httpx.MockTransport(image_handler))
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        image_client=image_client,
    )
    api_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

    payload = {
        "backend": "fal",
        "model_ref": "fal-ai/flux/dev",
        "prompt": "lush rainforest",
        "aspect_ratio": "1:1",
    }
    response = await api_client.post("/v1/generate", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["images"][0]["url"].startswith("http://127.0.0.1:8000/images/")

    job_id = body["job_id"]
    get_response = await api_client.get(f"/v1/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["job_id"] == job_id

    image_files = list((tmp_path / "test_image_output").glob("*.png"))
    assert len(image_files) == 1
    sidecars = list((tmp_path / "test_image_output").glob("*.json"))
    assert len(sidecars) == 1
    sidecar_payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert sidecar_payload["job"]["job_id"] == job_id

    log_path = tmp_path / "logs" / "events.jsonl"
    assert log_path.exists()
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2

    await api_client.aclose()
    await image_client.aclose()


@pytest.mark.asyncio
async def test_get_unknown_job_returns_404(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/jobs/not-found")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_backends_endpoint_reports_fal(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/backends")
        assert response.status_code == 200
        payload = response.json()
        backend_map = {item["name"]: item for item in payload["backends"]}
        assert backend_map["fal"]["available"] is True
        assert backend_map["bfl"]["available"] is False
