from __future__ import annotations

import asyncio
import json
from pathlib import Path

from gateway.models import JobRecord


async def write_image_sidecars(job: JobRecord) -> list[Path]:
    if job.result is None:
        return []

    job_payload = job.model_dump(mode="json")
    sidecar_paths: list[Path] = []

    for image in job.result.images:
        if not image.local_path:
            continue

        image_path = Path(image.local_path)
        sidecar_path = image_path.with_suffix(".json")
        sidecar_payload = {
            "image_file": image_path.name,
            "image_url": image.url,
            "image_original_url": image.original_url,
            "job": job_payload,
        }
        sidecar_text = json.dumps(sidecar_payload, indent=2, ensure_ascii=True)
        await asyncio.to_thread(sidecar_path.write_text, sidecar_text, encoding="utf-8")
        sidecar_paths.append(sidecar_path)

    return sidecar_paths
