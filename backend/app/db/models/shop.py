from typing import TYPE_CHECKING
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.dataset import Dataset
    from app.db.models.sale import Sale
    from app.db.models.user import User


class Shop(Base, TimestampMixin):
    """Represents an individual shop tenant in the system.

    Supports any number of shops without hardcoding limits.
    """

    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        "Dataset",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
    sales: Mapped[list["Sale"]] = relationship(
        "Sale",
        back_populates="shop",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Shop(id={self.id}, name={self.name!r})>"
