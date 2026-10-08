from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Sale(Base):
    """Historical sales identified by shop, SKU, and date."""

    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("num_units_sold >= 0", name="num_units_sold_non_negative"),
        CheckConstraint("length(trim(sku_name)) > 0", name="sku_name_not_empty"),
        Index("ix_sales_shop_id_date", "shop_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shop_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    num_units_sold: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Sale(id={self.id}, shop_id={self.shop_id}, "
            f"date={self.date}, sku_name={self.sku_name!r}, "
            f"num_units_sold={self.num_units_sold})>"
        )
