"""Load authorized history asynchronously, then compute forecasts off the event loop."""
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.models.sale import Sale
from app.ml.model import generate_forecast
from app.ml.schemas import ForecastResponse


def _forecast_rows(rows: Sequence[tuple[str, date, Decimal]]) -> ForecastResponse:
    frame = pd.DataFrame.from_records(rows, columns=["sku_id", "sale_date", "units_sold"])
    return generate_forecast(frame)


async def forecast_sales(db: AsyncSession, shop_id: int) -> ForecastResponse:
    """shop_id must come from the authenticated database user, never the client."""
    result = await db.execute(
        select(Sale.sku_name, Sale.date, Sale.num_units_sold)
        .where(Sale.shop_id == shop_id)
        .order_by(Sale.sku_name.asc(), Sale.date.asc())
    )
    # Pass detached values only to the worker; AsyncSession stays on its event loop.
    rows = [tuple(row) for row in result.all()]
    return await run_in_threadpool(_forecast_rows, rows)
