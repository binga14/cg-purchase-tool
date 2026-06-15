from app.services.cg_pipeline_service import run_scheduled_forecast_if_ready
from app.services.email_service import send_forecast_email_if_ready
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.run_scheduled_forecast")
def run_scheduled_forecast() -> bool:
    return run_scheduled_forecast_if_ready()


@celery_app.task(name="app.workers.tasks.send_forecast_email")
def send_forecast_email() -> bool:
    return send_forecast_email_if_ready()
