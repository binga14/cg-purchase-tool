from functools import lru_cache
from pathlib import Path
from typing import Tuple

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Forecast Purchase API"
    static_dir: Path = Path("storage/static")
    monthly_upload_dir: Path = Path("storage/static/uploads")
    source_train_file: Path = Path("storage/uploads/cg-data.xlsx")
    prepared_train_file: Path = Path("storage/train/cg-data-train.csv")
    forecast_result_file: Path = Path("storage/results/forecast.csv")
    max_upload_size_bytes: int = 200 * 1024 * 1024
    allowed_extensions: Tuple[str, ...] = ("xlsx",)


@lru_cache
def get_settings() -> Settings:
    return Settings()
