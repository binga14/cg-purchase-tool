from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forecast_purchase",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

# Celery uses a single timezone for all Beat schedules, matching SCHEDULED_TIMEZONE.
celery_app.conf.update(
    timezone=settings.scheduled_timezone,
    enable_utc=False,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

beat_schedule = {}

if settings.scheduled_forecast_enabled:
    beat_schedule["scheduled-forecast"] = {
        "task": "app.workers.tasks.run_scheduled_forecast",
        "schedule": crontab(
            day_of_week=settings.scheduled_forecast_day_of_week,
            hour=settings.scheduled_forecast_hour,
            minute=settings.scheduled_forecast_minute,
        ),
    }

if settings.scheduled_email_enabled:
    beat_schedule["scheduled-forecast-email"] = {
        "task": "app.workers.tasks.send_forecast_email",
        "schedule": crontab(
            day_of_week=settings.scheduled_email_day_of_week,
            hour=settings.scheduled_email_hour,
            minute=settings.scheduled_email_minute,
        ),
    }

celery_app.conf.beat_schedule = beat_schedule
