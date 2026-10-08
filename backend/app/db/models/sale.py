from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.dataset import Dataset
    from app.db.models.shop import Shop


class Sale(Base, TimestampMixin):
    """Represents actual historical sales records belonging to a shop and dataset.

    Future ML predictions must NOT be stored in this table.
    """

    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("length(trim(product)) > 0", name="product_not_empty"),
        Index("ix_sales_shop_date_product", "shop_id", "date", "product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    product: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="sales")
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="sales")

    def __repr__(self) -> str:
        return (
            f"<Sale(id={self.id}, shop_id={self.shop_id}, "
            f"date={self.date}, product={self.product!r}, quantity={self.quantity})>"
        )
