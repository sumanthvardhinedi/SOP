import enum
from datetime import date, datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.sale import Sale
    from app.db.models.shop import Shop
    from app.db.models.user import User


class DatasetStatus(str, enum.Enum):
    """Lifecycle status of an uploaded sales dataset file."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Dataset(Base):
    """Tracks every uploaded CSV/Excel file and its processing metadata."""

    __tablename__ = "datasets"
    __table_args__ = (
        Index("ix_datasets_shop_id_file_hash", "shop_id", "file_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[DatasetStatus] = mapped_column(
        SQLEnum(DatasetStatus, name="dataset_status_enum"),
        default=DatasetStatus.UPLOADED,
        server_default=DatasetStatus.UPLOADED.value,
        nullable=False,
        index=True,
    )
    rows_processed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="datasets")
    uploader: Mapped["User"] = relationship("User", back_populates="uploaded_datasets")
    sales: Mapped[list["Sale"]] = relationship(
        "Sale",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Dataset(id={self.id}, shop_id={self.shop_id}, "
            f"file_name={self.file_name!r}, status={self.status.value})>"
        )
