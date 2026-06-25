import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from prophet.forecaster import Prophet
from prophet.serialize import model_from_json


MA_BLEND_WEIGHT_DEFAULT = 0.50


class SavedForecastModelError(RuntimeError):
    pass


def _load_json(path: Path):
    with open(path, "r") as fin:
        return json.load(fin)


def _resolve_artifact_dir() -> Path:
    """
    Prefer FORECAST_ARTIFACT_DIR from environment.
    Otherwise default to ./storage/forecast_artifacts from project root.
    """
    env_path = os.getenv("FORECAST_ARTIFACT_DIR")
    if env_path:
        return Path(env_path)

    return Path("storage") / "forecast_artifacts"


@contextmanager
def _skip_prophet_backend_loading():
    original_loader = Prophet._load_stan_backend

    def load_no_backend(self, stan_backend):
        self.stan_backend = None

    Prophet._load_stan_backend = load_no_backend
    try:
        yield
    finally:
        Prophet._load_stan_backend = original_loader


def run_saved_model_forecast(output_path: Path, horizon_days: Optional[int] = None) -> Path:
    """
    Backend-facing callable.

    Called by app/services/forecast_service.py through FORECAST_MODEL_CALLABLE.

    Parameters:
        output_path:
            Final CSV path expected by the backend.
        horizon_days:
            Existing backend setting. For this saved model version, the actual
            horizon comes from forecast_artifacts/config.json. We validate it
            loosely but do not retrain or change the saved model horizon.

    Returns:
        Path to generated CSV.
    """
    artifact_dir = _resolve_artifact_dir()
    model_dir = artifact_dir / "models"
    config_path = artifact_dir / "config.json"
    metadata_path = artifact_dir / "metadata.csv"

    if not artifact_dir.exists():
        raise SavedForecastModelError(f"Artifact directory not found: {artifact_dir}")

    if not config_path.exists():
        raise SavedForecastModelError(f"Missing artifact config: {config_path}")

    if not metadata_path.exists():
        raise SavedForecastModelError(f"Missing artifact metadata: {metadata_path}")

    if not model_dir.exists():
        raise SavedForecastModelError(f"Missing model directory: {model_dir}")

    config = _load_json(config_path)
    metadata = pd.read_csv(metadata_path)

    forecast_horizon_weeks = int(config["forecast_horizon_weeks"])
    last_training_week = pd.to_datetime(config["last_training_week"])
    output_columns = config["output_columns"]
    ma_blend_weight = float(config.get("ma_blend_weight", MA_BLEND_WEIGHT_DEFAULT))

    if horizon_days is not None:
        requested_weeks = max(1, round(int(horizon_days) / 7))
        if requested_weeks != forecast_horizon_weeks:
            print(
                f"Warning: backend requested horizon_days={horizon_days} "
                f"~ {requested_weeks} weeks, but artifact was trained for "
                f"{forecast_horizon_weeks} weeks. Using artifact horizon."
            )

    future_week_index = pd.date_range(
        start=last_training_week + pd.Timedelta(weeks=1),
        periods=forecast_horizon_weeks,
        freq="7D",
    )

    output_rows = []

    for _, row in metadata.iterrows():
        model_path = model_dir / row["model_file"]

        if not model_path.exists():
            raise SavedForecastModelError(f"Missing model file: {model_path}")

        with open(model_path, "r") as fin:
            with _skip_prophet_backend_loading():
                model = model_from_json(json.load(fin))

        future_df = pd.DataFrame({"ds": future_week_index})

        use_lag = bool(row.get("use_lag_regressor", False))
        if use_lag:
            future_df["lag_mean"] = float(row["lag_mean"])

        forecast = model.predict(future_df)

        prophet_yhat = np.clip(
            forecast["yhat"].to_numpy(),
            a_min=0,
            a_max=None,
        )

        ma_blended = bool(row.get("ma_blended", False))
        if ma_blended:
            ma_yhat = np.array(json.loads(row["ma_yhat_json"]), dtype=float)
            final_yhat = (
                (1 - ma_blend_weight) * prophet_yhat
                + ma_blend_weight * ma_yhat
            )
        else:
            final_yhat = prophet_yhat

        for week_start_date, forecasted_qty in zip(future_week_index, final_yhat):
            output_rows.append({
                "sku": row["sku"],
                "product_name": row["product_name"],
                "uom": row["uom"],
                "category_l1": row["category_l1"],
                "category_l2": row["category_l2"],
                "week_start_date": week_start_date.date().isoformat(),
                "forecasted_qty": round(float(max(forecasted_qty, 0)), 2),
            })

    final_output = pd.DataFrame(output_rows)

    if final_output.empty:
        raise SavedForecastModelError("Saved model generated an empty forecast output.")

    final_output = final_output[output_columns]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    final_output.to_csv(output_path, index=False)

    print(f"Saved forecast CSV: {output_path}")
    print(f"Rows: {len(final_output):,}")
    print(f"Unique SKUs: {final_output['sku'].nunique():,}")
    print(f"Columns: {list(final_output.columns)}")

    return output_path
