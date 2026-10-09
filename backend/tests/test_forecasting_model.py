"""Independent feature/estimator tests using generated daily histories."""
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.ml import model as forecasting
from app.ml.model import FEATURES, ForecastInputError, create_features, generate_forecast


def history(days=42, *, sku="Apple", start=date(2026, 1, 1), value=20.25):
    return pd.DataFrame([
        {"sku_id": sku, "sale_date": start + timedelta(days=index),
         "units_sold": value(index) if callable(value) else value}
        for index in range(days)
    ])


def test_features_are_causal_sorted_and_leave_input_unchanged():
    source = history(value=lambda index: float(index)).sample(frac=1, random_state=1)
    before = source.copy(deep=True)
    featured = create_features(source)
    for window in (7, 14, 21, 28):
        assert featured.loc[28, f"lag_{window}"] == 28 - window
        assert featured.loc[28, f"rolling_avg_{window}"] == pytest.approx((28 - window + 27) / 2)
    assert len(featured.dropna(subset=FEATURES)) == 14
    assert_frame_equal(source, before)
    modified = history(value=lambda index: float(index))
    modified.loc[28:, "units_sold"] = 10000
    assert_frame_equal(
        featured.loc[:28, FEATURES], create_features(modified).loc[:28, FEATURES]
    )


def test_rolling_features_never_cross_sku_boundaries():
    frame = pd.concat([history(sku="A", value=1000), history(sku="B", value=2)])
    features = create_features(frame)
    second = features[features.sku_id == "B"].reset_index(drop=True)
    for window in (7, 14, 21, 28):
        assert second.loc[:window - 1, f"rolling_avg_{window}"].isna().all()
        assert second.loc[window:, f"rolling_avg_{window}"].eq(2).all()
    assert len(features.dropna(subset=FEATURES)) == 28


def test_missing_dates_invalidate_calendar_windows_without_zero_filling():
    source = history(70).drop(index=35)
    featured = create_features(source)
    assert len(featured) == len(source)
    dates = featured.sale_date.dt.date
    assert featured.loc[dates == date(2026, 2, 6), "lag_7"].isna().all()
    assert featured.loc[dates == date(2026, 3, 5), "rolling_avg_28"].isna().all()
    assert featured.loc[dates == date(2026, 3, 6), "rolling_avg_28"].notna().all()


def test_calendar_features_use_supplied_festival_dates_and_weekends():
    features = create_features(history(30))
    assert features.loc[features.sale_date.dt.date == date(2026, 1, 14), "is_indian_festival"].item() == 1
    assert features.loc[features.sale_date.dt.date == date(2026, 1, 15), "is_indian_festival"].item() == 0
    assert features.loc[features.sale_date.dt.date == date(2026, 1, 3), "is_weekend"].item() == 1
    assert features.loc[features.sale_date.dt.date == date(2026, 1, 5), "is_weekend"].item() == 0


def test_constant_decimal_history_real_estimator():
    source = history(value=Decimal("20.75"))
    before = source.copy(deep=True)
    result = generate_forecast(source)
    assert result.status == "ok"
    assert result.forecast_date == date(2026, 2, 12)
    assert result.training_rows == 14
    assert [row.model_dump() for row in result.items] == [{"sku_name": "Apple", "predicted_units": 21}]
    assert result.total == 1
    assert result.skipped == []
    assert_frame_equal(source, before)


def test_linear_history_real_estimator_extrapolates_next_day():
    result = generate_forecast(history(70, value=lambda index: index + 1))
    assert result.items[0].predicted_units == 71


def test_empty_history_does_not_fit(monkeypatch):
    monkeypatch.setattr(forecasting.LinearRegression, "fit", lambda *_: pytest.fail("Must not fit"))
    result = generate_forecast(pd.DataFrame())
    assert result.status == "no_sales"
    assert result.forecast_date is None
    assert result.total == result.training_rows == 0
    assert not result.items and not result.skipped


@pytest.mark.parametrize("days,reason", [(1, "incomplete_history"), (27, "incomplete_history"), (28, "insufficient_training_data")])
def test_insufficient_history_returns_reason_instead_of_fitting(monkeypatch, days, reason):
    monkeypatch.setattr(forecasting.LinearRegression, "fit", lambda *_: pytest.fail("Must not fit"))
    result = generate_forecast(history(days))
    assert result.status == "insufficient_history"
    assert result.total == result.training_rows == 0
    assert result.skipped[0].reason == reason


def test_29_days_is_minimum_for_training():
    result = generate_forecast(history(29, value=5))
    assert result.status == "ok"
    assert result.training_rows == 1
    assert result.items[0].predicted_units == 5


def test_28_day_sku_can_use_pooled_training_within_shop():
    result = generate_forecast(pd.concat([
        history(42, sku="B", value=20),
        history(28, sku="A", start=date(2026, 1, 15), value=20),
    ]).sample(frac=1, random_state=2))
    assert result.status == "ok"
    assert result.training_rows == 14
    assert [row.sku_name for row in result.items] == ["A", "B"]


def test_stale_and_gapped_skus_are_reported_with_common_forecast_date():
    frame = pd.concat([
        history(sku="Current"),
        history(41, sku="Stale"),
        history(sku="Gapped").drop(index=40),
        history(10, sku="Short", start=date(2026, 2, 2)),
    ])
    result = generate_forecast(frame)
    assert result.forecast_date == date(2026, 2, 12)
    assert [row.sku_name for row in result.items] == ["Current"]
    assert [row.sku_name for row in result.skipped] == ["Gapped", "Short", "Stale"]
    assert {row.reason for row in result.skipped} == {"incomplete_history"}


def test_old_gaps_do_not_discard_later_complete_windows():
    result = generate_forecast(history(70, value=5).drop(index=2))
    assert result.status == "ok"
    assert result.training_rows == 39
    assert result.items[0].predicted_units == 5


def test_no_eligible_skus_does_not_fit_even_with_historical_training(monkeypatch):
    monkeypatch.setattr(forecasting.LinearRegression, "fit", lambda *_: pytest.fail("Must not fit"))
    result = generate_forecast(history(42).drop(index=40))
    assert result.training_rows > 0
    assert result.status == "insufficient_history"
    assert result.total == 0


def test_forecast_uses_same_lags_rolling_and_calendar_features(monkeypatch):
    seen = {}
    class Estimator:
        def fit(self, x, y):
            seen["training"] = x
            assert y.notna().all()
        def predict(self, x):
            seen["prediction"] = x
            return [5.5]
    monkeypatch.setattr(forecasting, "LinearRegression", Estimator)
    # 2026-11-08 is both a Sunday and a supplied festival date.
    frame = history(42, start=date(2026, 9, 27), value=lambda index: index + 0.25)
    result = generate_forecast(frame)
    assert result.forecast_date == date(2026, 11, 8)
    features = seen["prediction"].iloc[0]
    for window in (7, 14, 21, 28):
        assert features[f"lag_{window}"] == 42 - window + 0.25
        assert features[f"rolling_avg_{window}"] == pytest.approx((42 - window + 41) / 2 + 0.25)
    assert features.is_weekend == features.is_indian_festival == 1
    assert list(seen["training"].columns) == FEATURES
    assert result.items[0].predicted_units == 6


@pytest.mark.parametrize("prediction,expected", [(-12.7, 0), (0, 0), (1.4, 1), (2.5, 2), (3.5, 4), (1e20, 10**20)])
def test_prediction_clips_and_rounds_without_integer_overflow(monkeypatch, prediction, expected):
    monkeypatch.setattr(forecasting.LinearRegression, "predict", lambda *_: [prediction])
    assert generate_forecast(history()).items[0].predicted_units == expected


@pytest.mark.parametrize("prediction", [float("nan"), float("inf")])
def test_nonfinite_predictions_are_not_returned(monkeypatch, prediction):
    monkeypatch.setattr(forecasting.LinearRegression, "predict", lambda *_: [prediction])
    with pytest.raises(RuntimeError, match="non-finite"):
        generate_forecast(history())


def test_calendar_coverage_is_explicit_outside_2026():
    result = generate_forecast(history(start=date(2027, 1, 1)))
    assert result.status == "ok"
    assert "only 2026" in result.warnings[0]


def test_duplicate_daily_rows_are_not_silently_merged():
    frame = history()
    with pytest.raises(ForecastInputError, match="duplicate"):
        generate_forecast(pd.concat([frame, frame.iloc[:1]]))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, "bad"])
def test_invalid_history_quantities_are_rejected(value):
    frame = history().astype({"units_sold": object})
    frame.loc[0, "units_sold"] = value
    with pytest.raises(ForecastInputError):
        generate_forecast(frame)


def test_last_calendar_day_is_rejected_clearly():
    with pytest.raises(ForecastInputError, match="calendar date|unsupported dates"):
        generate_forecast(history(1, start=date.max))
