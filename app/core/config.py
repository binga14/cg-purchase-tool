from functools import lru_cache
import os
from pathlib import Path
from typing import Tuple

from pydantic import BaseModel


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


class Settings(BaseModel):
    app_name: str = "Forecast Purchase API"
    static_dir: Path = Path("storage/static")
    weekly_upload_dir: Path = Path("storage/static/uploads")
    source_train_file: Path = Path("storage/uploads/cg-data.xlsx")
    prepared_train_file: Path = Path("storage/train/cg-data-train.csv")
    forecast_result_file: Path = Path("storage/results/forecast.csv")
    max_upload_size_bytes: int = 200 * 1024 * 1024
    allowed_extensions: Tuple[str, ...] = ("xlsx",)
    scheduled_forecast_enabled: bool = get_bool_env("SCHEDULED_FORECAST_ENABLED", True)
    scheduled_forecast_day_of_week: str = os.getenv(
        "SCHEDULED_FORECAST_DAY_OF_WEEK", "sun"
    )
    scheduled_forecast_hour: int = get_int_env("SCHEDULED_FORECAST_HOUR", 22)
    scheduled_forecast_minute: int = get_int_env("SCHEDULED_FORECAST_MINUTE", 0)
    scheduled_forecast_timezone: str = os.getenv(
        "SCHEDULED_FORECAST_TIMEZONE", "America/Mexico_City"
    )
    scheduled_forecast_max_sales_age_weeks: int = get_int_env(
        "SCHEDULED_FORECAST_MAX_SALES_AGE_WEEKS", 2
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
