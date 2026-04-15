from __future__ import annotations

from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx

from gateway.config import AppConfig, resolve_path
from gateway.image_store import persist_result_images
from gateway.models import CanonicalGenerateRequest, JobRecord, utc_now
from gateway.registry import AdapterRegistry
from gateway.sidecar import write_image_sidecars
from gateway.sinks.jsonl import JsonlSink
from gateway.store import InMemoryJobStore


class JobService:
    def __init__(
        self,
        registry: AdapterRegistry,
        sink: JsonlSink,
        config: AppConfig,
        project_root: Path,
        image_client: httpx.AsyncClient | None = None,
        store: InMemoryJobStore | None = None,
    ) -> None:
        self.registry = registry
        self.sink = sink
        self.config = config
        self.project_root = project_root
        self.image_client = image_client
        self.store = store or InMemoryJobStore()

        self.output_dir = resolve_path(config.image_output_path, project_root)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def submit(self, request: CanonicalGenerateRequest) -> JobRecord:
        job_id = str(uuid4())
        record = JobRecord(
            job_id=job_id,
            proxy_timestamp=utc_now(),
            gateway_version=self.config.gateway_version,
            backend=request.backend,
            model_ref=request.model_ref,
            status="pending",
            request=request,
        )
        self.store.upsert(record)
        await self._write_log("dispatch", record)

        adapter = self.registry.get(request.backend)
        if adapter is None:
            failed = record.model_copy(
                update={
                    "status": "failed",
                    "error": f"Unsupported backend: {request.backend}",
                }
            )
            self.store.upsert(failed)
            await self._write_log("completion", failed)
            return failed

        try:
            started = perf_counter()
            result = await adapter.generate(request)
            elapsed_ms = int((perf_counter() - started) * 1000)
            if result.duration_ms is None:
                result = result.model_copy(update={"duration_ms": elapsed_ms})

            result = await persist_result_images(
                result=result,
                job_id=job_id,
                output_dir=self.output_dir,
                static_base_url=self.config.static_image_base_url,
                client=self.image_client,
            )
            completed = record.model_copy(update={"status": "succeeded", "result": result})
            self.store.upsert(completed)

            if self.config.sidecar_enabled:
                await write_image_sidecars(completed)

            await self._write_log("completion", completed)
            return completed
        except Exception as exc:
            failed = record.model_copy(update={"status": "failed", "error": str(exc)})
            self.store.upsert(failed)
            await self._write_log("completion", failed)
            return failed

    def get_job(self, job_id: str) -> JobRecord | None:
        return self.store.get(job_id)

    async def _write_log(self, event: str, job: JobRecord) -> None:
        payload = job.model_dump(mode="json")
        for field in self.config.log_exclude_fields:
            payload.pop(field, None)
        payload["event"] = event
        await self.sink.write(payload)
