from app.services.email_service import (
    send_forecast_email as send_forecast_email_report,
)
from app.services.forecast_service import run_forecast
from app.services.job_status_service import (
    EMAIL_JOB,
    FORECAST_JOB,
    mark_failed,
    mark_running,
    mark_success,
)
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.run_scheduled_forecast")
def run_scheduled_forecast() -> bool:
    mark_running(FORECAST_JOB)
    try:
        result = run_forecast()
    except Exception as exc:
        mark_failed(FORECAST_JOB, str(exc))
        raise

    mark_success(FORECAST_JOB, output_path=result.output_path)
    return True


@celery_app.task(name="app.workers.tasks.send_forecast_email")
def send_forecast_email() -> bool:
    mark_running(EMAIL_JOB)
    try:
        send_forecast_email_report()
    except Exception as exc:
        mark_failed(EMAIL_JOB, str(exc))
        raise

    mark_success(EMAIL_JOB, sent=True)
    return True
