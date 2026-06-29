from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from math import ceil
from pathlib import Path
from shutil import copyfile
from typing import Any, Callable, Mapping, Optional
from zoneinfo import ZoneInfo

from app.core.config import get_settings


class ForecastRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForecastRunResult:
    output_path: Path
    horizon_days: int


def import_callable(dotted_path: str) -> Callable:
    module_path, separator, callable_name = dotted_path.partition(":")
    if not separator or not module_path or not callable_name:
        raise ForecastRunError(
            "FORECAST_MODEL_CALLABLE must use the format 'module.path:function_name'."
        )

    try:
        module = import_module(module_path)
    except ImportError as exc:
        raise ForecastRunError(
            f"Could not import forecast model module '{module_path}'."
        ) from exc

    forecast_callable = getattr(module, callable_name, None)
    if not callable(forecast_callable):
        raise ForecastRunError(
            f"Forecast model callable '{callable_name}' was not found in '{module_path}'."
        )

    return forecast_callable


def call_model(
    forecast_callable: Callable,
    output_path: Path,
    horizon_days: int,
    forecast_start_date: str,
) -> Optional[Path]:
    horizon_weeks = max(1, ceil(horizon_days / 7))
    result = forecast_callable(
        output_path=output_path,
        horizon_weeks=horizon_weeks,
        forecast_start_date=forecast_start_date,
    )
    if result is None:
        return None
    if isinstance(result, Mapping):
        error_count = int(result.get("error_count", 0))
        if error_count:
            raise ForecastRunError(
                f"Forecast model failed for {error_count} registered model(s)."
            )
        generated_path: Any = result.get("output_csv_path")
        if not generated_path:
            raise ForecastRunError(
                "Forecast model result did not include 'output_csv_path'."
            )
        return Path(generated_path)
    return Path(result)


def run_forecast(
    forecast_start_date: Optional[str] = None,
) -> ForecastRunResult:
    settings = get_settings()
    if not settings.forecast_model_callable:
        raise ForecastRunError(
            "No forecast model is configured. Set FORECAST_MODEL_CALLABLE after the "
            "packaged model is added to the codebase."
        )

    output_path = settings.forecast_result_file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_start_date = forecast_start_date or datetime.now(
        ZoneInfo(settings.scheduled_timezone)
    ).date().isoformat()

    forecast_callable = import_callable(settings.forecast_model_callable)
    generated_path = call_model(
        forecast_callable,
        output_path=output_path,
        horizon_days=settings.forecast_horizon_days,
        forecast_start_date=resolved_start_date,
    )

    final_path = generated_path or output_path
    if not final_path.exists():
        raise ForecastRunError(
            f"Forecast model completed without creating a CSV at '{final_path}'."
        )
    if final_path.suffix.lower() != ".csv":
        raise ForecastRunError(
            f"Forecast model must generate a CSV file, got '{final_path.name}'."
        )
    if final_path.stat().st_size == 0:
        raise ForecastRunError("Forecast model generated an empty CSV file.")

    if final_path != output_path:
        copyfile(final_path, output_path)
        final_path = output_path

    return ForecastRunResult(
        output_path=final_path,
        horizon_days=settings.forecast_horizon_days,
    )
