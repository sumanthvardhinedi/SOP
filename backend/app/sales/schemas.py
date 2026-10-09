"""Sales retrieval query validation and public response contract."""
from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SalesQuery(BaseModel):
    # Consistent with existing endpoints: unknown inputs cannot select a shop.
    model_config = ConfigDict(extra="ignore")

    start_date: date | None = Field(default=None, description="Inclusive earliest sales date")
    end_date: date | None = Field(default=None, description="Inclusive latest sales date")
    sku_name: str | None = Field(default=None, description="Exact SKU name, including case and spaces")

    @field_validator("sku_name")
    @classmethod
    def validate_sku_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("sku_name must not be blank")
        return value

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    shop_id: int
    sku_name: str
    num_units_sold: Decimal


class SalesResponse(BaseModel):
    items: list[SaleResponse]
    total: int
