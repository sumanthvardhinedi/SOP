"""Public forecasting responses; historical sales are never changed."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ForecastItem(BaseModel):
    sku_name: str
    predicted_units: int = Field(ge=0)


class SkippedSKU(BaseModel):
    sku_name: str
    reason: Literal["incomplete_history", "insufficient_training_data"]
    message: str


class ForecastResponse(BaseModel):
    status: Literal["ok", "no_sales", "insufficient_history"]
    forecast_date: date | None
    items: list[ForecastItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    training_rows: int = Field(default=0, ge=0)
    skipped: list[SkippedSKU] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
