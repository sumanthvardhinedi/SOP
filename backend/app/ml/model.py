"""Daily lag/rolling features and a request-local pooled LinearRegression model.

Input names follow the supplied model: sku_id, sale_date, units_sold. The database
adapter maps sku_name to sku_id; there is no SKU ID column or new database model.
"""
from datetime import date, timedelta
import math

import pandas as pd
from sklearn.linear_model import LinearRegression

from app.ml.schemas import ForecastItem, ForecastResponse, SkippedSKU

WINDOWS = (7, 14, 21, 28)
FEATURES = [
    "lag_7", "lag_14", "lag_21", "lag_28",
    "rolling_avg_7", "rolling_avg_14", "rolling_avg_21", "rolling_avg_28",
    "is_weekend", "is_indian_festival",
]
INDIAN_FESTIVALS = frozenset({
    "2026-01-14", "2026-01-26", "2026-03-04", "2026-03-21",
    "2026-08-15", "2026-08-28", "2026-09-04", "2026-10-20",
    "2026-11-08", "2026-11-09", "2026-12-25",
})


class ForecastInputError(ValueError):
    """Stored history cannot be used by the forecasting model."""


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute causal features within each SKU, using complete calendar windows.

    No resampling or zero-filling: a gap invalidates the affected window. Shifting
    before rolling prevents the current target from leaking into its features.
    Grouped transform keeps rolling means from bleeding across SKU boundaries.
    """
    df = df.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    df = df.sort_values(["sku_id", "sale_date"]).reset_index(drop=True)
    if df.duplicated(["sku_id", "sale_date"]).any():
        raise ForecastInputError("Sales history contains duplicate SKU/date records.")

    grouped_sales = df.groupby("sku_id")["units_sold"]
    grouped_dates = df.groupby("sku_id")["sale_date"]
    for window in WINDOWS:
        # With unique sorted dates, a span of N days over N preceding rows means
        # all N preceding calendar days are present (including yesterday).
        complete = (df["sale_date"] - grouped_dates.shift(window)) == pd.Timedelta(days=window)
        df[f"lag_{window}"] = grouped_sales.shift(window).where(complete)
        df[f"rolling_avg_{window}"] = grouped_sales.transform(
            lambda sales: sales.shift(1).rolling(window, min_periods=window).mean()
        ).where(complete)

    df["day_of_week"] = df["sale_date"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_indian_festival"] = (
        df["sale_date"].dt.strftime("%Y-%m-%d").isin(INDIAN_FESTIVALS)
    ).astype(int)
    return df


def generate_forecast(df: pd.DataFrame) -> ForecastResponse:
    """Predict the day after this shop's latest sale using only this shop's rows.

    Training needs at least one target with its preceding 28 daily observations
    (29 consecutive days for at least one SKU). Prediction needs the 28 days
    immediately before the common forecast date. Incomplete SKUs are reported.
    """
    if df.empty:
        return ForecastResponse(status="no_sales", forecast_date=None)
    df = df.copy()
    try:
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        df["units_sold"] = pd.to_numeric(df["units_sold"]).astype(float)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ForecastInputError("Sales history contains unsupported dates or quantities.") from exc
    if df["sale_date"].isna().any() or not df["units_sold"].map(
        lambda value: math.isfinite(value) and value >= 0
    ).all():
        raise ForecastInputError("Sales history must contain valid dates and finite, non-negative quantities.")

    latest_date = df["sale_date"].max().date()
    if latest_date == date.max:
        raise ForecastInputError("Cannot forecast beyond the last supported calendar date (9999-12-31).")
    forecast_date = latest_date + timedelta(days=1)
    sku_names = sorted(df["sku_id"].unique())
    # Append an unknown target for each SKU. The same causal feature pipeline is
    # used for training and inference; no predicted value enters model fitting.
    future = pd.DataFrame({
        "sku_id": sku_names,
        "sale_date": pd.Timestamp(forecast_date),
        "units_sold": float("nan"),
    })
    featured = create_features(pd.concat([df, future], ignore_index=True))
    training = featured.dropna(subset=[*FEATURES, "units_sold"])
    candidates = featured[featured["sale_date"].dt.date == forecast_date].dropna(subset=FEATURES)
    eligible = set(candidates["sku_id"])
    skipped = []
    for sku in sku_names:
        if sku not in eligible:
            skipped.append(SkippedSKU(
                sku_name=sku, reason="incomplete_history",
                message="Requires all 28 consecutive daily sales records immediately before the forecast date.",
            ))
        elif training.empty:
            skipped.append(SkippedSKU(
                sku_name=sku, reason="insufficient_training_data",
                message="Training requires at least one SKU with 29 consecutive daily sales records.",
            ))

    warnings = []
    if forecast_date.year != 2026 or (df["sale_date"].dt.year != 2026).any():
        warnings.append("The supplied festival calendar covers only 2026; dates outside 2026 use a festival flag of 0.")
    response = ForecastResponse(
        status="insufficient_history", forecast_date=forecast_date,
        training_rows=len(training), skipped=skipped, warnings=warnings,
    )
    if training.empty or candidates.empty:
        return response

    # Do not share a fitted estimator across users or requests.
    model = LinearRegression()
    model.fit(training[FEATURES], training["units_sold"])
    predictions = model.predict(candidates[FEATURES])
    if not all(math.isfinite(float(value)) for value in predictions):
        raise RuntimeError("Forecasting produced a non-finite prediction.")
    response.items = [
        ForecastItem(sku_name=sku, predicted_units=int(round(max(0.0, float(prediction)))))
        for sku, prediction in zip(candidates["sku_id"], predictions, strict=True)
    ]
    response.total = len(response.items)
    response.status = "ok"
    return response
