"""Validation preview and structured error schemas; no persistence models."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class ValidatedSale(BaseModel):
    shop_id: int
    sku_name: str
    num_units_sold: Decimal
    date: date


class SalesValidationResponse(BaseModel):
    success: Literal[True] = True
    row_count: int
    rows: list[ValidatedSale]


class ValidationIssue(BaseModel):
    row: int | None = None
    column: str | None = None
    message: str


class SalesValidationError(ValueError):
    """A client file error, independent of FastAPI and database access."""

    def __init__(self, errors: list[ValidationIssue], status_code: int = 422):
        super().__init__("Sales file validation failed.")
        self.errors = errors
        self.status_code = status_code
