# Sales forecasting

This module serves `POST /api/v1/predictions` from existing stored sales. It does
not persist predictions or modify any tables. The router reuses
`app.core.dependencies.get_current_user` and `app.db.database.get_db`.

## Structure

- `router.py`: authenticated endpoint and public input-error handling.
- `service.py`: asynchronous SQLAlchemy query restricted by the database user's
  shop, plus a worker-thread boundary for DataFrame construction/training/inference.
- `model.py`: supplied LinearRegression approach, causal feature engineering,
  history checks, and next-day inference.
- `schemas.py`: public prediction and skipped-SKU responses.

Database fields map to the supplied model's DataFrame columns:

| Existing sales field | Model input |
| --- | --- |
| `sku_name` | `sku_id` (the name itself, not a new identifier) |
| `date` | `sale_date` |
| `num_units_sold` | `units_sold` |

`shop_id` is applied in SQL before rows reach pandas. Each request constructs and
fits a new estimator using all eligible rows from that shop only. No global fitted
model, cross-shop training, files, caches, or database writes are used.

## Features and missing dates

The model retains lag and shifted rolling-average features for 7/14/21/28 days,
weekend, and the supplied 2026 Indian festival calendar. Rolling transforms run
inside each SKU group, correcting cross-SKU leakage in the original snippet.
Training features exclude their target day; forecast features use the identical
pipeline. Festival flags also apply to the forecast day.

Missing dates remain unknown, **not zero**. Complete daily windows are required;
no calendar expansion creates synthetic observations. To train, the shop needs at
least one SKU with 29 consecutive daily records (28 feature days and one target).
A candidate SKU needs all 28 days immediately before the common forecast date.
A SKU with 28 days can use a model trained on another eligible SKU in the same
shop, following the supplied pooled-regression design.

The forecast date is the day after the latest stored sale **within the shop**,
not tomorrow relative to the server clock and not a separate date for each SKU.
Stale SKUs and SKUs with gaps in that final 28-day window are skipped with reasons.
Older gaps do not disqualify later complete windows. Exact SKU names and case are
preserved; results and skip notices are sorted by SKU name.

Quantities become floating-point values only inside the estimator; historical
NUMERIC values remain unchanged. Predictions are clipped at zero and rounded to
whole units using nearest-even rounding, matching the provided model. Non-finite
outputs fail safely instead of returning NaN/Infinity. Insufficient/empty data
returns a structured HTTP 200 response without fitting an empty model.

## Limits

The calendar is exactly the supplied list and covers only 2026. The response
includes a warning when history or the forecast date falls outside that year;
those dates get festival flag zero. No additional festival dates are inferred.

This is a baseline model, not a measured accuracy guarantee: it trains per request
on the shop's full history, has no saved model or confidence intervals, and one
training row is a technical minimum rather than evidence of predictive quality.
Large histories increase memory/CPU use even though computation is off the async
event loop. No background training, forecasting UI, inventory recommendations,
or multi-day recursive prediction is included.

See the backend README for the API response and request example.
