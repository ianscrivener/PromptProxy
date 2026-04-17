import json
from pathlib import Path

import httpx
import pytest

from gateway.config import AppConfig
from gateway.job_service import JobService
from gateway.models import CanonicalGenerateRequest, CanonicalImage, CanonicalResult
from gateway.plugins.base import BackendAdapter, BackendError
from gateway.registry import AdapterRegistry
from gateway.sinks.jsonl import JsonlSink


class SuccessAdapter(BackendAdapter):
    name = "fal"
    display_name = "FAL"

    async def health_check(self) -> bool:
        return True

    async def generate(self, _: CanonicalGenerateRequest) -> CanonicalResult:
        return CanonicalResult(
            images=[CanonicalImage(url="https://cdn.example.com/img.png")],
            seed_used=101,
        )


class FailureAdapter(BackendAdapter):
    name = "fal"
    display_name = "FAL"

    async def health_check(self) -> bool:
        return True

    async def generate(self, _: CanonicalGenerateRequest) -> CanonicalResult:
        raise BackendError("upstream failed")


def _config() -> AppConfig:
    return AppConfig(
        jsonl_path="logs/events.jsonl",
        image_output_path="test_image_output",
        static_image_base_url="http://127.0.0.1:8000/images",
    )


@pytest.mark.asyncio
async def test_job_service_success_persists_image_and_sidecar(tmp_path):
    async def image_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://cdn.example.com/img.png":
            return httpx.Response(200, content=b"fake-image", headers={"Content-Type": "image/png"})
        return httpx.Response(404)

    image_client = httpx.AsyncClient(transport=httpx.MockTransport(image_handler))
    service = JobService(
        registry=AdapterRegistry([SuccessAdapter()]),
        sink=JsonlSink(tmp_path / "logs" / "events.jsonl"),
        config=_config(),
        project_root=tmp_path,
        image_client=image_client,
    )
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="sunset over water",
        aspect_ratio="16:9",
    )

    job = await service.submit(request)
    await image_client.aclose()

    assert job.status == "succeeded"
    assert job.result is not None
    assert len(job.result.images) == 1

    image = job.result.images[0]
    assert image.url.startswith("http://127.0.0.1:8000/images/")
    assert image.local_path is not None
    local_path = Path(image.local_path)
    assert local_path.exists()
    assert local_path.parent == (tmp_path / "test_image_output")

    sidecar_path = local_path.with_suffix(".json")
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["job"]["job_id"] == job.job_id
    assert sidecar["image_file"] == local_path.name
    assert sidecar["upstream_request"] is None

    log_lines = (tmp_path / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 2
    assert json.loads(log_lines[0])["event"] == "dispatch"
    completion = json.loads(log_lines[1])
    assert completion["event"] == "completion"
    assert completion["status"] == "succeeded"


@pytest.mark.asyncio
async def test_job_service_failure_logs_error_and_no_sidecar(tmp_path):
    service = JobService(
        registry=AdapterRegistry([FailureAdapter()]),
        sink=JsonlSink(tmp_path / "logs" / "events.jsonl"),
        config=_config(),
        project_root=tmp_path,
    )
    request = CanonicalGenerateRequest(
        backend="fal",
        model_ref="fal-ai/flux/dev",
        prompt="rainy city",
    )

    job = await service.submit(request)

    assert job.status == "failed"
    assert job.error is not None
    assert job.result is None

    output_dir = tmp_path / "test_image_output"
    json_sidecars = list(output_dir.glob("*.json")) if output_dir.exists() else []
    assert json_sidecars == []

    log_lines = (tmp_path / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 2
    completion = json.loads(log_lines[1])
    assert completion["event"] == "completion"
    assert completion["status"] == "failed"
