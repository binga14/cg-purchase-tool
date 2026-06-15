from functools import lru_cache
import os
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel

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


def get_list_env(name: str) -> Tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


class Settings(BaseModel):
    app_name: str = "Forecast Purchase API"
    static_dir: Path = Path("storage/static")
    weekly_upload_dir: Path = Path("storage/static/uploads")
    source_train_file: Path = Path("storage/uploads/cg-data.xlsx")
    prepared_train_file: Path = Path("storage/train/cg-data-train.csv")
    forecast_result_file: Path = Path("storage/results/forecast.csv")
    max_upload_size_bytes: int = 200 * 1024 * 1024
    allowed_extensions: Tuple[str, ...] = ("xlsx",)
    # Single timezone for all scheduled jobs (forecast + email).
    scheduled_timezone: str = os.getenv("SCHEDULED_TIMEZONE", "America/Mexico_City")
    scheduled_forecast_enabled: bool = get_bool_env("SCHEDULED_FORECAST_ENABLED", True)
    scheduled_forecast_day_of_week: str = os.getenv(
        "SCHEDULED_FORECAST_DAY_OF_WEEK", "sun"
    )
    scheduled_forecast_hour: int = get_int_env("SCHEDULED_FORECAST_HOUR", 22)
    scheduled_forecast_minute: int = get_int_env("SCHEDULED_FORECAST_MINUTE", 0)
    scheduled_forecast_max_sales_age_weeks: int = get_int_env(
        "SCHEDULED_FORECAST_MAX_SALES_AGE_WEEKS", 2
    )
    scheduled_email_enabled: bool = get_bool_env("SCHEDULED_EMAIL_ENABLED", True)
    scheduled_email_day_of_week: str = os.getenv("SCHEDULED_EMAIL_DAY_OF_WEEK", "mon")
    scheduled_email_hour: int = get_int_env("SCHEDULED_EMAIL_HOUR", 10)
    scheduled_email_minute: int = get_int_env("SCHEDULED_EMAIL_MINUTE", 0)
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
    )
    resend_api_key: Optional[str] = get_optional_env("RESEND_API_KEY")
    email_from_email: Optional[str] = get_optional_env("EMAIL_FROM_EMAIL")
    email_from_name: str = os.getenv("EMAIL_FROM_NAME", "Forecast Purchase App")
    forecast_report_recipients: Tuple[str, ...] = get_list_env(
        "FORECAST_REPORT_RECIPIENT_EMAIL"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
