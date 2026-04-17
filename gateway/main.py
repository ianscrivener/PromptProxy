from __future__ import annotations

import json
from pathlib import Path

import httpx
import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from gateway.config import load_runtime_config, resolve_path
from gateway.job_service import JobService
from gateway.models import CanonicalGenerateRequest, JobRecord
from gateway.plugins.base import BackendAdapter
from gateway.plugins.bfl import BflAdapter
from gateway.plugins.byteplus import BytePlusAdapter
from gateway.plugins.drawthings import DrawThingsAdapter
from gateway.plugins.fal import FalAdapter
from gateway.registry import AdapterRegistry
from gateway.sinks.jsonl import JsonlSink


def _load_fal_models_from_file(project_root: Path) -> list[dict[str, str | None]]:
    models_path = project_root / "fal_models.json"
    if not models_path.exists():
        return []

    try:
        with models_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return []

    if not isinstance(payload, dict):
        return []

    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        return []

    models: list[dict[str, str | None]] = []
    seen_model_refs: set[str] = set()
    for item in raw_models:
        if not isinstance(item, dict):
            continue

        model_ref = item.get("endpoint_id")
        if not isinstance(model_ref, str) or not model_ref:
            continue

        if model_ref in seen_model_refs:
            continue
        seen_model_refs.add(model_ref)

        display_name: str | None = None
        group_key: str | None = None
        group_label: str | None = None

        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            metadata_display_name = metadata.get("display_name")
            if isinstance(metadata_display_name, str):
                display_name = metadata_display_name

            group = metadata.get("group")
            if isinstance(group, dict):
                raw_group_key = group.get("key")
                raw_group_label = group.get("label")
                if isinstance(raw_group_key, str):
                    group_key = raw_group_key
                if isinstance(raw_group_label, str):
                    group_label = raw_group_label

        models.append(
            {
                "model_ref": model_ref,
                "display_name": display_name,
                "group_key": group_key,
                "group_label": group_label,
            }
        )

    return models


def create_app(
    config_path: str | Path | None = None,
    env_file: str | Path | None = ".env",
    fal_adapter: BackendAdapter | None = None,
    bfl_adapter: BackendAdapter | None = None,
    drawthings_adapter: BackendAdapter | None = None,
    byteplus_adapter: BackendAdapter | None = None,
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
    drawthings = drawthings_adapter or DrawThingsAdapter(
        address=app_config.drawthings_address,
        timeout_seconds=app_config.request_timeout_seconds,
        use_tls=app_config.drawthings_use_tls,
        use_compression=app_config.drawthings_use_compression,
        enabled=app_config.drawthings_enabled,
        health_check_timeout_seconds=app_config.drawthings_health_check_timeout_seconds,
    )
    byteplus = byteplus_adapter or BytePlusAdapter(
        api_key=runtime.secrets.byteplus_ark_api_key,
        api_base_url=app_config.byteplus_api_base_url,
        timeout_seconds=app_config.request_timeout_seconds,
    )
    registry = AdapterRegistry([fal, bfl, drawthings, byteplus])
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

    @app.get("/v1/providers")
    async def get_providers() -> dict[str, list[dict[str, object]]]:
        providers: list[dict[str, object]] = []
        for provider in registry.list():
            providers.append(
                {
                    "name": provider.name,
                    "display_name": provider.display_name,
                    "available": await provider.health_check(),
                }
            )
        return {"providers": providers}

    @app.get("/v1/providers/{provider_name}/models")
    async def get_provider_models(provider_name: str) -> dict[str, object]:
        provider = registry.get(provider_name)
        if provider is None:
            raise HTTPException(status_code=404, detail="Provider not found")

        models: list[dict[str, str | None]]
        if provider.name == "fal":
            models = _load_fal_models_from_file(runtime.project_root)
            if not models:
                models = [{"model_ref": model_ref} for model_ref in provider.supported_models]
        elif hasattr(provider, "list_models") and callable(getattr(provider, "list_models")):
            try:
                dynamic_models = await provider.list_models()
            except Exception:
                dynamic_models = []

            if dynamic_models:
                models = dynamic_models
            else:
                models = [{"model_ref": model_ref} for model_ref in provider.supported_models]
        else:
            models = [{"model_ref": model_ref} for model_ref in provider.supported_models]

        return {
            "provider": {
                "name": provider.name,
                "display_name": provider.display_name,
            },
            "models": models,
        }

    @app.get("/docs/swagger", include_in_schema=False)
    async def swagger_docs() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
        )

    @app.get("/openapi.yaml", include_in_schema=False)
    async def openapi_yaml() -> Response:
        schema = app.openapi()
        content = yaml.safe_dump(schema, sort_keys=False, allow_unicode=False)
        return Response(content=content, media_type="application/yaml")

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
