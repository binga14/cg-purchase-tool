from typing import Optional

from app.core.config import get_settings
from app.services.cg_pipeline_service import run_scheduled_forecast_if_ready

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except ModuleNotFoundError:
    BackgroundScheduler = None
    CronTrigger = None


forecast_scheduler: Optional["BackgroundScheduler"] = None


def start_scheduler() -> None:
    global forecast_scheduler

    settings = get_settings()
    if not settings.scheduled_forecast_enabled:
        return
    if BackgroundScheduler is None or CronTrigger is None:
        print("APScheduler is not installed. Scheduled forecasting is disabled.")
        return
    if forecast_scheduler is not None and forecast_scheduler.running:
        return

    forecast_scheduler = BackgroundScheduler(
        timezone=settings.scheduled_forecast_timezone
    )
    forecast_scheduler.add_job(
        run_scheduled_forecast_if_ready,
        CronTrigger(
            day_of_week=settings.scheduled_forecast_day_of_week,
            hour=settings.scheduled_forecast_hour,
            minute=settings.scheduled_forecast_minute,
            timezone=settings.scheduled_forecast_timezone,
        ),
        id="scheduled_forecast",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    forecast_scheduler.start()


def stop_scheduler() -> None:
    global forecast_scheduler

    if forecast_scheduler is not None and forecast_scheduler.running:
        forecast_scheduler.shutdown(wait=False)
    forecast_scheduler = None
