from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ForecastJob:
    id: str
    uploaded_file_name: str
    input_path: Path
    output_path: Path
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def output_available(self) -> bool:
        return self.status == "completed" and self.output_path.exists()


class ForecastJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ForecastJob] = {}
        self._lock = Lock()

    def create(self, job: ForecastJob) -> ForecastJob:
        with self._lock:
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> Optional[ForecastJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def mark_processing(self, job_id: str) -> Optional[ForecastJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.status = "processing"
            job.started_at = utc_now_iso()
            return job

    def mark_completed(self, job_id: str) -> Optional[ForecastJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.status = "completed"
            job.completed_at = utc_now_iso()
            return job

    def mark_failed(self, job_id: str, error_message: str) -> Optional[ForecastJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.status = "failed"
            job.completed_at = utc_now_iso()
            job.error_message = error_message
            return job


forecast_job_store = ForecastJobStore()
