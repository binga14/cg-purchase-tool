from functools import lru_cache
from pathlib import Path
from typing import Tuple

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Forecast Purchase API"
    api_prefix: str = "/api"
    upload_dir: Path = Path("storage/uploads")
    forecast_output_dir: Path = Path("storage/forecasts")
    max_upload_size_bytes: int = 25 * 1024 * 1024
    allowed_extensions: Tuple[str, ...] = ("xlsx", "csv")


@lru_cache
def get_settings() -> Settings:
    return Settings()
