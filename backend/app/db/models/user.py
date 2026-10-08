from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.dataset import Dataset
    from app.db.models.shop import Shop


class User(Base, TimestampMixin):
    """Represents an authenticated user assigned to a specific shop.

    Never expose `password_hash` in API schemas or responses.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="users")
    uploaded_datasets: Mapped[list["Dataset"]] = relationship(
        "Dataset",
        back_populates="uploader",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r}, shop_id={self.shop_id})>"
