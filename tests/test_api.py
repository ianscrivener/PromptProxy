import json
from pathlib import Path

import httpx
import pytest
import yaml

from gateway.main import create_app
from gateway.models import CanonicalGenerateRequest, CanonicalImage, CanonicalResult
from gateway.plugins.base import BackendAdapter


class ApiSuccessAdapter(BackendAdapter):
    name = "fal"
    display_name = "FAL"
    supported_models = (
        "fal-ai/flux/dev",
        "fal-ai/flux/schnell",
    )

    async def health_check(self) -> bool:
        return True

    async def generate(self, _: CanonicalGenerateRequest) -> CanonicalResult:
        return CanonicalResult(images=[CanonicalImage(url="https://cdn.example.com/api.png")], seed_used=55)


class ApiBflAdapter(BackendAdapter):
    name = "bfl"
    display_name = "BFL"
    supported_models = (
        "flux-2-flex",
        "flux-2-pro",
        "flux-2-max",
        "flux-2-klein-4b",
        "flux-2-klein-9b",
    )

    async def health_check(self) -> bool:
        return False

    async def generate(self, _: CanonicalGenerateRequest) -> CanonicalResult:
        return CanonicalResult(images=[])


class ApiDrawThingsAdapter(BackendAdapter):
    name = "drawthings"
    display_name = "DrawThings"
    supported_models = ("jibmix_zit_v1.0_fp16_f16.ckpt",)

    async def health_check(self) -> bool:
        return True

    async def generate(self, _: CanonicalGenerateRequest) -> CanonicalResult:
        return CanonicalResult(images=[])

    async def list_models(self) -> list[dict[str, str | None]]:
        return [
            {
                "model_ref": "jibmix_zit_v1.0_fp16_f16.ckpt",
                "display_name": "JIBMix ZIT v1",
            }
        ]


class ApiBytePlusAdapter(BackendAdapter):
    name = "byteplus"
    display_name = "BytePlus"
    supported_models = (
        "seedream-5-0-t2i-250624",
        "seededit-3-0-i2i-250628",
    )

    async def health_check(self) -> bool:
        return True

    async def generate(self, _: CanonicalGenerateRequest) -> CanonicalResult:
        return CanonicalResult(images=[])


def _write_runtime_files(tmp_path: Path) -> tuple[Path, Path]:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "gateway_host: 127.0.0.1",
                "gateway_port: 9999",
                "gateway_version: 0.1.0",
                "jsonl_path: logs/events.jsonl",
                "image_output_path: test_image_output",
                "sidecar_enabled: true",
                "static_image_base_url: http://127.0.0.1:9999/images",
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
        drawthings_adapter=ApiDrawThingsAdapter(),
        image_client=image_client,
    )
    api_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

    payload = {
        "backend": "fal",
        "model_ref": "fal-ai/flux/dev",
        "prompt": "A detailed photo of a beautiful Swedish 24yo blonde women in a small strappy red crop top smiling taking a phone selfie doing the peace sign with her fingers, she is in an apocalyptic city wasteland and. a nuclear mushroom cloud explosion is rising in the background , 35mm photograph, film, cinematic.",
        "aspect_ratio": "1:1",
    }
    response = await api_client.post("/v1/generate", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["images"][0]["url"].startswith("http://127.0.0.1:9999/images/")

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
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/jobs/not-found")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_providers_endpoint_reports_fal(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/providers")
        assert response.status_code == 200
        payload = response.json()
        provider_map = {item["name"]: item for item in payload["providers"]}
        assert provider_map["fal"]["available"] is True
        assert provider_map["bfl"]["available"] is False
        assert provider_map["drawthings"]["available"] is True


@pytest.mark.asyncio
async def test_provider_models_endpoint_reports_fal_models(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/providers/fal/models")
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"]["name"] == "fal"
        model_refs = [item["model_ref"] for item in payload["models"]]
        assert "fal-ai/flux/dev" in model_refs


@pytest.mark.asyncio
async def test_provider_models_endpoint_reports_bfl_models(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/providers/bfl/models")
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"]["name"] == "bfl"
        model_refs = [item["model_ref"] for item in payload["models"]]
        assert model_refs == [
            "flux-2-flex",
            "flux-2-pro",
            "flux-2-max",
            "flux-2-klein-4b",
            "flux-2-klein-9b",
        ]


@pytest.mark.asyncio
async def test_provider_models_endpoint_reports_drawthings_models(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/providers/drawthings/models")
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"]["name"] == "drawthings"
        assert payload["models"][0]["model_ref"] == "jibmix_zit_v1.0_fp16_f16.ckpt"
        assert payload["models"][0]["display_name"] == "JIBMix ZIT v1"


@pytest.mark.asyncio
async def test_provider_models_endpoint_reports_byteplus_models(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
        byteplus_adapter=ApiBytePlusAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/providers/byteplus/models")
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"]["name"] == "byteplus"
        model_refs = [item["model_ref"] for item in payload["models"]]
        assert model_refs == ["seedream-5-0-t2i-250624", "seededit-3-0-i2i-250628"]


@pytest.mark.asyncio
async def test_provider_models_endpoint_uses_fal_models_json(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    (tmp_path / "fal_models.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "endpoint_id": "fal-ai/nano-banana-2/edit",
                        "metadata": {
                            "display_name": "Nano Banana 2",
                            "group": {
                                "key": "nano-banana-2",
                                "label": "Image Editing",
                            },
                        },
                    },
                    {
                        "endpoint_id": "fal-ai/flux/dev",
                        "metadata": {
                            "display_name": "FLUX.1 Dev",
                            "group": {
                                "key": "flux",
                                "label": "Text to Image",
                            },
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/providers/fal/models")
        assert response.status_code == 200
        payload = response.json()
        assert payload["models"][0]["model_ref"] == "fal-ai/nano-banana-2/edit"
        assert payload["models"][0]["display_name"] == "Nano Banana 2"
        assert payload["models"][0]["group_key"] == "nano-banana-2"
        assert payload["models"][0]["group_label"] == "Image Editing"


@pytest.mark.asyncio
async def test_provider_models_endpoint_unknown_provider_404(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/v1/providers/nope/models")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_swagger_docs_page_available(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/docs/swagger")
        assert response.status_code == 200
        assert "Swagger UI" in response.text


@pytest.mark.asyncio
async def test_openapi_yaml_available(tmp_path):
    config_path, env_path = _write_runtime_files(tmp_path)
    app = create_app(
        config_path=config_path,
        env_file=env_path,
        fal_adapter=ApiSuccessAdapter(),
        bfl_adapter=ApiBflAdapter(),
        drawthings_adapter=ApiDrawThingsAdapter(),
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api_client:
        response = await api_client.get("/openapi.yaml")
        assert response.status_code == 200
        assert "yaml" in response.headers["content-type"]
        payload = yaml.safe_load(response.text)
        assert "/v1/generate" in payload["paths"]
        assert "/v1/providers" in payload["paths"]
        assert "/v1/providers/{provider_name}/models" in payload["paths"]
