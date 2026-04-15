from __future__ import annotations

from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from gateway.config import load_runtime_config, resolve_path
from gateway.job_service import JobService
from gateway.models import CanonicalGenerateRequest, JobRecord
from gateway.plugins.base import BackendAdapter
from gateway.plugins.bfl import BflAdapter
from gateway.plugins.fal import FalAdapter
from gateway.registry import AdapterRegistry
from gateway.sinks.jsonl import JsonlSink


def create_app(
    config_path: str | Path | None = None,
    env_file: str | Path | None = ".env",
    fal_adapter: BackendAdapter | None = None,
    bfl_adapter: BackendAdapter | None = None,
    image_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    runtime = load_runtime_config(config_path=config_path, env_file=env_file)
    app_config = runtime.app

    fal = fal_adapter or FalAdapter(
        api_key=runtime.secrets.fal_key,
        api_base_url=app_config.fal_api_base_url,
        timeout_seconds=app_config.request_timeout_seconds,
    )
    bfl = bfl_adapter or BflAdapter(
        api_key=runtime.secrets.bfl_key,
        api_base_url=app_config.bfl_api_base_url,
        timeout_seconds=app_config.request_timeout_seconds,
        poll_interval_seconds=app_config.bfl_poll_interval_seconds,
    )
    registry = AdapterRegistry([fal, bfl])
    jsonl_path = resolve_path(app_config.jsonl_path, runtime.project_root)
    sink = JsonlSink(jsonl_path)
    service = JobService(
        registry=registry,
        sink=sink,
        config=app_config,
        project_root=runtime.project_root,
        image_client=image_client,
    )

    app = FastAPI(title="PromptProxy", version=app_config.gateway_version)
    app.state.service = service

    image_dir = resolve_path(app_config.image_output_path, runtime.project_root)
    image_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/images", StaticFiles(directory=str(image_dir)), name="images")

    @app.post("/v1/generate", response_model=JobRecord, status_code=201)
    async def generate_job(request: CanonicalGenerateRequest) -> JobRecord:
        return await service.submit(request)

    @app.get("/v1/jobs/{job_id}", response_model=JobRecord)
    async def get_job(job_id: str) -> JobRecord:
        job = service.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/v1/backends")
    async def get_backends() -> dict[str, list[dict[str, object]]]:
        backends: list[dict[str, object]] = []
        for backend in registry.list():
            backends.append(
                {
                    "name": backend.name,
                    "display_name": backend.display_name,
                    "available": await backend.health_check(),
                }
            )
        return {"backends": backends}

    return app


app = create_app()


def run() -> None:
    runtime = load_runtime_config()
    uvicorn.run(
        "gateway.main:app",
        host=runtime.app.gateway_host,
        port=runtime.app.gateway_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
