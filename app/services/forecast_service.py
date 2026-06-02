from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import warnings

import numpy as np
import pandas as pd


warnings.filterwarnings("ignore")

REQUIRED_COLUMNS = [
    "order_date",
    "product_id",
    "product_name",
    "qty",
    "company_id",
    "customer_id",
    "warehouse_id",
    "uom",
    "line_subtotal",
]


@dataclass(frozen=True)
class ForecastConfig:
    test_weeks: int = 4
    forecast_horizon_weeks: int = 4
    cv_holdout_weeks: int = 4
    min_history_weeks: int = 52
    recent_sales_weeks: int = 52
    target_uom: str = "PIEZA"
    holiday_country_code: str = "MX"
    ma_blend_threshold_mape: float = 0.15
    ma_blend_weight: float = 0.50
    top_n: Optional[int] = 300
    use_lag_regressor: bool = True
    max_products: Optional[int] = None


@dataclass(frozen=True)
class ForecastRunResult:
    output_path: Path
    forecast_rows: int
    forecasted_skus: int
    eligible_skus: int


class ForecastInputError(ValueError):
    pass


def create_prophet_model(holidays_df: pd.DataFrame, params: dict):
    from prophet import Prophet

    return Prophet(holidays=holidays_df, **params)


PROPHET_PARAM_GRIDS = {
    "trend_and_seasonal": [
        {
            "growth": "linear",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 8.0,
        },
        {
            "growth": "linear",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "multiplicative",
            "changepoint_prior_scale": 0.10,
            "seasonality_prior_scale": 10.0,
        },
    ],
    "trend_dominant": [
        {
            "growth": "linear",
            "yearly_seasonality": False,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.10,
            "seasonality_prior_scale": 1.0,
        },
        {
            "growth": "linear",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.10,
            "seasonality_prior_scale": 3.0,
        },
    ],
    "seasonal_dominant": [
        {
            "growth": "linear",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.03,
            "seasonality_prior_scale": 10.0,
        },
        {
            "growth": "linear",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "multiplicative",
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 12.0,
        },
    ],
    "stable_low_noise": [
        {
            "growth": "linear",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 5.0,
        },
        {
            "growth": "linear",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "multiplicative",
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 5.0,
        },
    ],
    "high_noise": [
        {
            "growth": "linear",
            "yearly_seasonality": False,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.001,
            "seasonality_prior_scale": 0.1,
        },
        {
            "growth": "flat",
            "yearly_seasonality": False,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.01,
            "seasonality_prior_scale": 0.1,
        },
        {
            "growth": "flat",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.01,
            "seasonality_prior_scale": 1.0,
        },
    ],
    "sparse_or_intermittent": [
        {
            "growth": "flat",
            "yearly_seasonality": False,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.01,
            "seasonality_prior_scale": 0.5,
        },
        {
            "growth": "linear",
            "yearly_seasonality": False,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.005,
            "seasonality_prior_scale": 0.1,
        },
    ],
    "mixed_signal": [
        {
            "growth": "linear",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 3.0,
        },
        {
            "growth": "linear",
            "yearly_seasonality": False,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.02,
            "seasonality_prior_scale": 1.0,
        },
        {
            "growth": "flat",
            "yearly_seasonality": True,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.01,
            "seasonality_prior_scale": 1.0,
        },
    ],
}


def run_forecast_csv(
    input_path: Path,
    output_path: Path,
    config: ForecastConfig = ForecastConfig(),
) -> ForecastRunResult:
    sales = read_sales_csv(input_path)
    product_uom_weekly, global_min_week, global_max_week = build_weekly_sales(sales, config)
    product_uom_weekly, eligible_skus = filter_eligible_series(
        product_uom_weekly, global_max_week, config
    )

    holidays_df = build_weekly_holidays(global_min_week, global_max_week, config)
    test_results, chosen_configs = run_backtests(
        product_uom_weekly,
        global_max_week,
        holidays_df,
        config,
    )
    future_forecasts = build_future_forecasts(
        product_uom_weekly,
        global_max_week,
        holidays_df,
        test_results,
        chosen_configs,
        config,
    )

    if config.top_n is not None and not test_results.empty and not future_forecasts.empty:
        top_n_ids = (
            test_results[test_results["model_status"] == "ok"]
            .dropna(subset=["mape"])
            .sort_values("mape", ascending=True)
            .head(config.top_n)["product_uom_id"]
            .tolist()
        )
        future_forecasts = future_forecasts[
            future_forecasts["product_uom_id"].isin(top_n_ids)
        ].copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    future_forecasts.to_csv(output_path, index=False)

    forecasted_skus = (
        future_forecasts["product_uom_id"].nunique()
        if "product_uom_id" in future_forecasts.columns
        else 0
    )
    return ForecastRunResult(
        output_path=output_path,
        forecast_rows=len(future_forecasts),
        forecasted_skus=forecasted_skus,
        eligible_skus=eligible_skus,
    )


def read_sales_csv(input_path: Path) -> pd.DataFrame:
    columns = pd.read_csv(input_path, nrows=0).columns.tolist()
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ForecastInputError(f"CSV is missing required columns: {missing}")

    sales = pd.read_csv(input_path, usecols=REQUIRED_COLUMNS)
    if sales.empty:
        raise ForecastInputError("CSV has no sales rows.")
    return sales


def build_weekly_sales(
    sales: pd.DataFrame,
    config: ForecastConfig,
) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"], errors="coerce")

    string_cols = [
        "product_id",
        "product_name",
        "company_id",
        "customer_id",
        "warehouse_id",
        "uom",
    ]
    for col in string_cols:
        sales[col] = sales[col].astype("string").str.strip()

    sales["uom"] = sales["uom"].str.upper().replace(
        {"PZA": "PIEZA", "NA": pd.NA, "NAN": pd.NA, "": pd.NA}
    )
    sales["product_name"] = sales["product_name"].fillna("")
    sales["qty"] = pd.to_numeric(sales["qty"], errors="coerce").fillna(0.0)
    sales["line_subtotal"] = pd.to_numeric(
        sales["line_subtotal"], errors="coerce"
    ).fillna(0.0)

    sales_clean = sales.dropna(subset=["order_date", "product_id", "uom"]).copy()
    sales_clean = sales_clean[sales_clean["uom"] == config.target_uom.upper()].copy()
    if sales_clean.empty:
        raise ForecastInputError(
            f"CSV has no valid rows for target UOM {config.target_uom.upper()}."
        )

    sales_clean["week_start"] = sales_clean["order_date"].dt.to_period("W-SUN").apply(
        lambda row: row.start_time
    )
    sales_clean["product_uom_id"] = (
        sales_clean["product_id"].astype(str) + "__" + sales_clean["uom"].astype(str)
    )

    product_uom_weekly = (
        sales_clean.groupby(
            ["product_uom_id", "product_id", "product_name", "uom", "week_start"],
            as_index=False,
        )
        .agg(
            weekly_qty_sold=("qty", "sum"),
            weekly_revenue=("line_subtotal", "sum"),
            order_line_count=("qty", "size"),
            unique_customers=("customer_id", "nunique"),
        )
        .sort_values(["product_id", "uom", "week_start"])
        .reset_index(drop=True)
    )

    product_uom_weekly["avg_price"] = np.where(
        product_uom_weekly["weekly_qty_sold"] > 0,
        product_uom_weekly["weekly_revenue"] / product_uom_weekly["weekly_qty_sold"],
        np.nan,
    )

    return (
        product_uom_weekly,
        product_uom_weekly["week_start"].min(),
        product_uom_weekly["week_start"].max(),
    )


def filter_eligible_series(
    product_uom_weekly: pd.DataFrame,
    global_max_week: pd.Timestamp,
    config: ForecastConfig,
) -> tuple[pd.DataFrame, int]:
    recent_sales_start_week = global_max_week - pd.Timedelta(
        weeks=config.recent_sales_weeks - 1
    )
    product_history_summary = (
        product_uom_weekly.groupby(
            ["product_uom_id", "product_id", "product_name", "uom"], as_index=False
        )
        .agg(
            first_sales_week=("week_start", "min"),
            last_sales_week=("week_start", "max"),
            total_qty_sold=("weekly_qty_sold", "sum"),
        )
    )
    product_history_summary["history_weeks"] = (
        ((global_max_week - product_history_summary["first_sales_week"]).dt.days // 7) + 1
    )

    recent_sales_summary = (
        product_uom_weekly[product_uom_weekly["week_start"] >= recent_sales_start_week]
        .groupby("product_uom_id", as_index=False)
        .agg(
            qty_sold_last_52_weeks=("weekly_qty_sold", "sum"),
            active_sales_weeks_last_52=(
                "weekly_qty_sold",
                lambda series: int((series > 0).sum()),
            ),
        )
    )
    product_history_summary = product_history_summary.merge(
        recent_sales_summary, on="product_uom_id", how="left"
    )
    product_history_summary[
        ["qty_sold_last_52_weeks", "active_sales_weeks_last_52"]
    ] = product_history_summary[
        ["qty_sold_last_52_weeks", "active_sales_weeks_last_52"]
    ].fillna(
        0
    )

    eligible_ids = product_history_summary.loc[
        (product_history_summary["history_weeks"] >= config.min_history_weeks)
        & (product_history_summary["qty_sold_last_52_weeks"] > 0),
        "product_uom_id",
    ]
    filtered_weekly = product_uom_weekly[
        product_uom_weekly["product_uom_id"].isin(eligible_ids)
    ].copy()
    if filtered_weekly.empty:
        raise ForecastInputError("No product series have enough history to forecast.")

    return filtered_weekly, int(filtered_weekly["product_uom_id"].nunique())


def build_weekly_holidays(
    global_min_week: pd.Timestamp,
    global_max_week: pd.Timestamp,
    config: ForecastConfig,
) -> pd.DataFrame:
    import holidays

    holiday_start_year = int(global_min_week.year)
    holiday_end_year = int(
        (global_max_week + pd.DateOffset(weeks=config.forecast_horizon_weeks)).year
    )
    holiday_years = list(range(holiday_start_year, holiday_end_year + 1))
    holiday_week_end = global_max_week + pd.Timedelta(
        weeks=config.forecast_horizon_weeks
    )
    holiday_calendar = holidays.country_holidays(
        config.holiday_country_code, years=holiday_years
    )

    holiday_records = []
    for holiday_date, holiday_name in holiday_calendar.items():
        holiday_timestamp = pd.Timestamp(holiday_date)
        holiday_week_start = holiday_timestamp.to_period("W-SUN").start_time
        holiday_records.append(
            {
                "holiday": f"{config.holiday_country_code.lower()}_{holiday_name}",
                "holiday_date": holiday_timestamp,
                "ds": holiday_week_start,
            }
        )

    holiday_detail = pd.DataFrame(holiday_records)
    if holiday_detail.empty:
        return pd.DataFrame(columns=["holiday", "ds", "lower_window", "upper_window"])

    holiday_detail = holiday_detail[
        (holiday_detail["ds"] >= global_min_week)
        & (holiday_detail["ds"] <= holiday_week_end)
    ].copy()
    return (
        holiday_detail[["holiday", "ds"]]
        .drop_duplicates()
        .assign(lower_window=0, upper_window=0)
        .reset_index(drop=True)
    )


def prepare_prophet_series(
    product_uom_weekly: pd.DataFrame,
    product_uom_id: str,
    end_week: pd.Timestamp,
) -> pd.DataFrame:
    df = product_uom_weekly[
        product_uom_weekly["product_uom_id"] == product_uom_id
    ].copy()
    ts = (
        df.sort_values("week_start")
        .set_index("week_start")["weekly_qty_sold"]
        .sort_index()
        .astype(float)
    )
    full_weeks = pd.date_range(start=ts.index.min(), end=end_week, freq="7D")
    ts = ts.reindex(full_weeks, fill_value=0.0)
    prophet_df = ts.reset_index()
    prophet_df.columns = ["ds", "y"]
    return prophet_df


def calculate_train_signal_from_prophet_df(
    train_df: pd.DataFrame,
    period: int = 52,
) -> dict:
    ts = train_df.set_index("ds")["y"].astype(float)
    result = {
        "total_weeks": len(ts),
        "active_weeks": int((ts > 0).sum()),
        "zero_ratio": float((ts == 0).mean()),
        "mean_weekly_qty": float(ts.mean()),
        "total_qty": float(ts.sum()),
        "trend_strength": np.nan,
        "seasonality_strength": np.nan,
        "noise_ratio": np.nan,
        "trend_slope_per_week": np.nan,
        "signal_status": "ok",
    }

    if result["total_weeks"] < 104:
        result["signal_status"] = "short_series"
        return result
    if result["active_weeks"] < 52:
        result["signal_status"] = "sparse_series"
        return result
    if ts.nunique() <= 1:
        result["signal_status"] = "constant_series"
        return result

    try:
        from statsmodels.tsa.seasonal import STL

        fit = STL(ts, period=period, robust=True).fit()
        trend = pd.Series(fit.trend, index=ts.index)
        seasonal = pd.Series(fit.seasonal, index=ts.index)
        resid = pd.Series(fit.resid, index=ts.index)

        var_resid = np.nanvar(resid)
        var_observed = np.nanvar(ts)
        trend_denom = np.nanvar(trend + resid)
        seasonal_denom = np.nanvar(seasonal + resid)

        result["trend_strength"] = (
            max(0, 1 - var_resid / trend_denom) if trend_denom > 0 else np.nan
        )
        result["seasonality_strength"] = (
            max(0, 1 - var_resid / seasonal_denom)
            if seasonal_denom > 0
            else np.nan
        )
        result["noise_ratio"] = (
            min(1, var_resid / var_observed) if var_observed > 0 else np.nan
        )
        result["trend_slope_per_week"] = np.polyfit(
            np.arange(len(trend)), trend.values, 1
        )[0]
    except Exception as exc:
        result["signal_status"] = f"signal_error: {exc}"

    return result


def assign_signal_group(signal: dict) -> str:
    trend = signal["trend_strength"]
    seasonal = signal["seasonality_strength"]
    noise = signal["noise_ratio"]
    zero_ratio = signal["zero_ratio"]

    if zero_ratio > 0.45:
        return "sparse_or_intermittent"
    if noise > 0.45:
        return "high_noise"
    if trend >= 0.50 and seasonal >= 0.50 and noise <= 0.35:
        return "trend_and_seasonal"
    if trend >= 0.50 and seasonal < 0.50 and noise <= 0.35:
        return "trend_dominant"
    if trend < 0.50 and seasonal >= 0.50 and noise <= 0.35:
        return "seasonal_dominant"
    if noise <= 0.25:
        return "stable_low_noise"
    return "mixed_signal"


def add_lag_regressor(df: pd.DataFrame, lag_weeks: int = 4) -> pd.DataFrame:
    df = df.copy()
    df["lag_mean"] = (
        df["y"]
        .shift(1)
        .rolling(window=lag_weeks, min_periods=1)
        .mean()
        .fillna(df["y"].mean())
    )
    return df


def compute_ma_forecast(
    train_df: pd.DataFrame,
    n_steps: int,
    windows: tuple[int, ...] = (4, 8, 12),
) -> np.ndarray:
    y = train_df["y"].values
    best_mae = np.inf
    best_val = np.mean(y[-4:]) if len(y) >= 4 else np.mean(y)

    for window in windows:
        if len(y) < window + n_steps:
            continue
        cv_actual = y[-(n_steps + window) : -window]
        if len(y) >= n_steps + 2 * window:
            cv_pred_val = np.mean(y[-(n_steps + 2 * window) : -(n_steps + window)])
        else:
            cv_pred_val = np.mean(y[:-n_steps])
        cv_pred = np.full(len(cv_actual), cv_pred_val)
        mae = np.mean(np.abs(cv_actual - cv_pred))
        if mae < best_mae:
            best_mae = mae
            best_val = float(np.mean(y[-window:]))

    return np.clip(np.full(n_steps, best_val), a_min=0, a_max=None)


def select_best_prophet_params_cv(
    train_df: pd.DataFrame,
    signal_group: str,
    holidays_df: pd.DataFrame,
    cv_holdout_weeks: int,
    use_lag_regressor: bool = False,
) -> tuple[dict, float]:
    candidates = PROPHET_PARAM_GRIDS.get(signal_group, PROPHET_PARAM_GRIDS["mixed_signal"])

    if len(train_df) <= cv_holdout_weeks + 20:
        return candidates[0], np.nan

    cv_train = train_df.iloc[:-cv_holdout_weeks].copy()
    cv_val = train_df.iloc[-cv_holdout_weeks:].copy()
    if cv_val["y"].sum() == 0:
        return candidates[0], np.nan

    best_params = candidates[0]
    best_mape = np.inf

    if use_lag_regressor:
        cv_train_r = add_lag_regressor(cv_train)
        last_vals = cv_train["y"].values[-4:]
        cv_val_r = cv_val.copy()
        cv_val_r["lag_mean"] = float(np.mean(last_vals))
    else:
        cv_train_r = cv_train
        cv_val_r = cv_val

    for params in candidates:
        try:
            model = create_prophet_model(holidays_df, params)
            if use_lag_regressor:
                model.add_regressor("lag_mean")
            model.fit(cv_train_r)
            predict_input = (
                cv_val_r[["ds", "lag_mean"]]
                if use_lag_regressor
                else cv_val_r[["ds"]]
            )
            forecast = model.predict(predict_input)
            yhat = np.clip(forecast["yhat"].to_numpy(), a_min=0, a_max=None)
            actual_total = cv_val["y"].values.sum()
            cv_mape = (
                abs(actual_total - yhat.sum()) / actual_total
                if actual_total > 0
                else np.nan
            )
            if np.isfinite(cv_mape) and cv_mape < best_mape:
                best_mape = cv_mape
                best_params = params
        except Exception:
            continue

    return best_params, best_mape if np.isfinite(best_mape) else np.nan


def calculate_forecast_metrics(actual: pd.Series, predicted: np.ndarray) -> dict:
    actual_array = np.asarray(actual, dtype=float)
    predicted_array = np.asarray(predicted, dtype=float)

    actual_total = actual_array.sum()
    forecast_total = predicted_array.sum()
    total_abs_error = abs(actual_total - forecast_total)
    if actual_total == 0:
        mape = np.nan
        accuracy_mape = np.nan
    else:
        mape = total_abs_error / actual_total
        accuracy_mape = max(0, 1 - mape)

    weekly_error = actual_array - predicted_array
    weekly_abs_error = np.abs(weekly_error)
    denominator = (np.abs(actual_array) + np.abs(predicted_array)) / 2
    smape_mask = denominator != 0

    return {
        "test_actual_total": actual_total,
        "test_forecast_total": forecast_total,
        "total_abs_error": total_abs_error,
        "mape": mape,
        "accuracy_mape": accuracy_mape,
        "mae_weekly": weekly_abs_error.mean(),
        "rmse_weekly": np.sqrt(np.mean(weekly_error**2)),
        "smape_weekly": (
            np.nan
            if smape_mask.sum() == 0
            else np.mean(weekly_abs_error[smape_mask] / denominator[smape_mask])
        ),
    }


def run_backtests(
    product_uom_weekly: pd.DataFrame,
    global_max_week: pd.Timestamp,
    holidays_df: pd.DataFrame,
    config: ForecastConfig,
) -> tuple[pd.DataFrame, dict]:
    product_uom_ids = product_uom_weekly["product_uom_id"].drop_duplicates().tolist()
    if config.max_products is not None:
        product_uom_ids = product_uom_ids[: config.max_products]

    results = []
    chosen_configs = {}

    for product_uom_id in product_uom_ids:
        meta = product_uom_weekly[
            product_uom_weekly["product_uom_id"] == product_uom_id
        ].iloc[0]
        base_row = {
            "product_uom_id": product_uom_id,
            "product_id": meta["product_id"],
            "product_name": meta["product_name"],
            "uom": meta["uom"],
        }

        try:
            prophet_df = prepare_prophet_series(
                product_uom_weekly, product_uom_id, global_max_week
            )
            if len(prophet_df) <= config.test_weeks + config.cv_holdout_weeks + 20:
                results.append({**base_row, "model_status": "too_short_for_train_test"})
                continue

            train_df = prophet_df.iloc[: -config.test_weeks].copy()
            test_df = prophet_df.iloc[-config.test_weeks :].copy()
            signal = calculate_train_signal_from_prophet_df(train_df)
            if signal["signal_status"] != "ok":
                results.append({**base_row, "model_status": signal["signal_status"], **signal})
                continue

            signal_group = assign_signal_group(signal)
            use_lag = (
                config.use_lag_regressor
                and signal_group not in ("sparse_or_intermittent",)
            )
            best_params, cv_mape = select_best_prophet_params_cv(
                train_df,
                signal_group,
                holidays_df,
                config.cv_holdout_weeks,
                use_lag_regressor=use_lag,
            )

            if use_lag:
                train_df_r = add_lag_regressor(train_df)
                test_df_r = test_df.copy()
                test_df_r["lag_mean"] = float(np.mean(train_df["y"].values[-4:]))
            else:
                train_df_r = train_df
                test_df_r = test_df

            model = create_prophet_model(holidays_df, best_params)
            if use_lag:
                model.add_regressor("lag_mean")
            model.fit(train_df_r)

            predict_input = test_df_r[["ds", "lag_mean"]] if use_lag else test_df[["ds"]]
            forecast = model.predict(predict_input)
            prophet_yhat = np.clip(forecast["yhat"].to_numpy(), a_min=0, a_max=None)
            ma_yhat = compute_ma_forecast(train_df, n_steps=config.test_weeks)
            blend_ma = np.isfinite(cv_mape) and cv_mape > config.ma_blend_threshold_mape
            final_yhat = (
                (1 - config.ma_blend_weight) * prophet_yhat
                + config.ma_blend_weight * ma_yhat
                if blend_ma
                else prophet_yhat
            )
            metrics = calculate_forecast_metrics(test_df["y"], final_yhat)

            results.append(
                {
                    **base_row,
                    "signal_group": signal_group,
                    "model_status": "ok",
                    **signal,
                    **metrics,
                    **best_params,
                    "cv_mape": cv_mape,
                    "ma_blended": blend_ma,
                    "use_lag_regressor": use_lag,
                    "holiday_country": config.holiday_country_code,
                    "holiday_rows": len(holidays_df),
                }
            )
            chosen_configs[product_uom_id] = {
                "best_params": best_params,
                "signal_group": signal_group,
                "use_lag": use_lag,
                "ma_blended": blend_ma,
            }
        except Exception as exc:
            results.append(
                {**base_row, "model_status": "model_error", "error_message": str(exc)}
            )

    return pd.DataFrame(results), chosen_configs


def build_future_forecasts(
    product_uom_weekly: pd.DataFrame,
    global_max_week: pd.Timestamp,
    holidays_df: pd.DataFrame,
    test_results: pd.DataFrame,
    chosen_configs: dict,
    config: ForecastConfig,
) -> pd.DataFrame:
    if test_results.empty or not chosen_configs:
        return pd.DataFrame()

    backtest_lookup = (
        test_results[test_results["model_status"] == "ok"]
        .set_index("product_uom_id")[["mape", "accuracy_mape", "signal_group"]]
        .rename(columns={"mape": "backtest_mape", "accuracy_mape": "backtest_accuracy"})
        .to_dict(orient="index")
    )
    future_week_index = pd.date_range(
        start=global_max_week + pd.Timedelta(weeks=1),
        periods=config.forecast_horizon_weeks,
        freq="7D",
    )

    future_rows = []
    for product_uom_id, product_config in chosen_configs.items():
        meta = product_uom_weekly[
            product_uom_weekly["product_uom_id"] == product_uom_id
        ].iloc[0]
        best_params = product_config["best_params"]
        signal_group = product_config["signal_group"]
        use_lag = product_config["use_lag"]
        blend_ma = product_config["ma_blended"]

        try:
            full_df = prepare_prophet_series(
                product_uom_weekly, product_uom_id, global_max_week
            )
            if use_lag:
                full_df_r = add_lag_regressor(full_df)
                future_df = pd.DataFrame(
                    {
                        "ds": future_week_index,
                        "lag_mean": np.full(
                            config.forecast_horizon_weeks,
                            float(np.mean(full_df["y"].values[-4:])),
                        ),
                    }
                )
            else:
                full_df_r = full_df
                future_df = pd.DataFrame({"ds": future_week_index})

            model = create_prophet_model(holidays_df, best_params)
            if use_lag:
                model.add_regressor("lag_mean")
            model.fit(full_df_r)

            forecast = model.predict(future_df)
            prophet_yhat = np.clip(forecast["yhat"].to_numpy(), a_min=0, a_max=None)
            prophet_lower = np.clip(
                forecast["yhat_lower"].to_numpy(), a_min=0, a_max=None
            )
            prophet_upper = np.clip(
                forecast["yhat_upper"].to_numpy(), a_min=0, a_max=None
            )
            ma_yhat = compute_ma_forecast(
                full_df, n_steps=config.forecast_horizon_weeks
            )
            final_yhat = (
                (1 - config.ma_blend_weight) * prophet_yhat
                + config.ma_blend_weight * ma_yhat
                if blend_ma
                else prophet_yhat
            )

            backtest_info = backtest_lookup.get(product_uom_id, {})
            for ds_val, prophet_val, ma_val, final_val, lo, hi in zip(
                future_week_index,
                prophet_yhat,
                ma_yhat,
                final_yhat,
                prophet_lower,
                prophet_upper,
            ):
                future_rows.append(
                    {
                        "product_uom_id": product_uom_id,
                        "product_id": meta["product_id"],
                        "product_name": meta["product_name"],
                        "uom": meta["uom"],
                        "signal_group": signal_group,
                        "week_start": ds_val,
                        "forecast_qty": float(final_val),
                        "forecast_qty_prophet": float(prophet_val),
                        "forecast_qty_ma": float(ma_val),
                        "forecast_qty_lower": float(lo),
                        "forecast_qty_upper": float(hi),
                        "ma_blended": blend_ma,
                        "use_lag_regressor": use_lag,
                        "backtest_mape": backtest_info.get("backtest_mape"),
                        "backtest_accuracy": backtest_info.get("backtest_accuracy"),
                    }
                )
        except Exception:
            continue

    return pd.DataFrame(future_rows)
