from functools import lru_cache
import os
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def get_optional_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_path_env(name: str, default: str) -> Path:
    value = os.getenv(name)
    if value is None:
        return Path(default)
    return Path(value)


def get_list_env(name: str) -> Tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


class Settings(BaseModel):
    app_name: str = "Forecast Email API"
    forecast_result_file: Path = Field(
        default_factory=lambda: get_path_env(
            "FORECAST_RESULT_FILE",
            "storage/forecasts/pieza_top_300_weekly_forecast.csv",
        )
    )
    job_status_file: Path = Field(
        default_factory=lambda: get_path_env(
            "JOB_STATUS_FILE", "storage/status/job-status.json"
        )
    )
    forecast_model_callable: Optional[str] = Field(
        default_factory=lambda: get_optional_env("FORECAST_MODEL_CALLABLE")
        or "app.services.forecasting.predict_from_saved_models:run_saved_model_forecast"
    )
    forecast_horizon_days: int = Field(
        default_factory=lambda: get_int_env("FORECAST_HORIZON_DAYS", 28)
    )
    scheduled_timezone: str = Field(
        default_factory=lambda: os.getenv("SCHEDULED_TIMEZONE", "America/Mexico_City")
    )
    scheduled_forecast_enabled: bool = Field(
        default_factory=lambda: get_bool_env("SCHEDULED_FORECAST_ENABLED", True)
    )
    scheduled_forecast_day_of_week: str = Field(
        default_factory=lambda: os.getenv("SCHEDULED_FORECAST_DAY_OF_WEEK", "mon")
    )
    scheduled_forecast_hour: int = Field(
        default_factory=lambda: get_int_env("SCHEDULED_FORECAST_HOUR", 9)
    )
    scheduled_forecast_minute: int = Field(
        default_factory=lambda: get_int_env("SCHEDULED_FORECAST_MINUTE", 0)
    )
    scheduled_email_enabled: bool = Field(
        default_factory=lambda: get_bool_env("SCHEDULED_EMAIL_ENABLED", True)
    )
    scheduled_email_day_of_week: str = Field(
        default_factory=lambda: os.getenv("SCHEDULED_EMAIL_DAY_OF_WEEK", "mon")
    )
    scheduled_email_hour: int = Field(
        default_factory=lambda: get_int_env("SCHEDULED_EMAIL_HOUR", 10)
    )
    scheduled_email_minute: int = Field(
        default_factory=lambda: get_int_env("SCHEDULED_EMAIL_MINUTE", 0)
    )
    celery_broker_url: str = Field(
        default_factory=lambda: os.getenv(
            "CELERY_BROKER_URL", "redis://localhost:6379/0"
        )
    )
    celery_result_backend: str = Field(
        default_factory=lambda: os.getenv(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
        )
    )
    resend_api_key: Optional[str] = Field(
        default_factory=lambda: get_optional_env("RESEND_API_KEY")
    )
    email_from_email: Optional[str] = Field(
        default_factory=lambda: get_optional_env("EMAIL_FROM_EMAIL")
    )
    email_from_name: str = Field(
        default_factory=lambda: os.getenv("EMAIL_FROM_NAME", "Forecast Purchase App")
    )
    forecast_email_subject: str = Field(
        default_factory=lambda: os.getenv(
            "FORECAST_EMAIL_SUBJECT", "Weekly 2-week sales forecast"
        )
    )
    forecast_report_recipients: Tuple[str, ...] = Field(
        default_factory=lambda: get_list_env("FORECAST_REPORT_RECIPIENT_EMAIL")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
