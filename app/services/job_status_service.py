import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings


FORECAST_JOB = "forecast"
EMAIL_JOB = "email"

PENDING = "pending"
RUNNING = "running"
SUCCESS = "success"
FAILED = "failed"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_status() -> dict[str, Any]:
    return {
        FORECAST_JOB: {
            "status": PENDING,
            "startedAt": None,
            "completedAt": None,
            "errorMessage": None,
            "outputPath": None,
        },
        EMAIL_JOB: {
            "status": PENDING,
            "startedAt": None,
            "completedAt": None,
            "errorMessage": None,
            "sentAt": None,
        },
    }


def status_path() -> Path:
    return get_settings().job_status_file


def read_status() -> dict[str, Any]:
    path = status_path()
    if not path.exists():
        return default_status()

    try:
        status = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default_status()

    merged_status = default_status()
    for job_name, job_status in status.items():
        if job_name in merged_status and isinstance(job_status, dict):
            merged_status[job_name].update(job_status)
    return merged_status


def write_status(status: dict[str, Any]) -> None:
    path = status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2, sort_keys=True))


def mark_running(job_name: str) -> None:
    status = read_status()
    status[job_name].update(
        {
            "status": RUNNING,
            "startedAt": utc_now_iso(),
            "completedAt": None,
            "errorMessage": None,
        }
    )
    write_status(status)


def mark_success(
    job_name: str,
    *,
    output_path: Optional[Path] = None,
    sent: bool = False,
) -> None:
    status = read_status()
    status[job_name].update(
        {
            "status": SUCCESS,
            "completedAt": utc_now_iso(),
            "errorMessage": None,
        }
    )
    if output_path is not None:
        status[job_name]["outputPath"] = str(output_path)
    if sent:
        status[job_name]["sentAt"] = utc_now_iso()
    write_status(status)


def mark_failed(job_name: str, error_message: str) -> None:
    status = read_status()
    status[job_name].update(
        {
            "status": FAILED,
            "completedAt": utc_now_iso(),
            "errorMessage": error_message,
        }
    )
    write_status(status)
