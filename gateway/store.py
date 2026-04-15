from __future__ import annotations

from gateway.models import JobRecord


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def upsert(self, job: JobRecord) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def list_all(self) -> list[JobRecord]:
        return list(self._jobs.values())
