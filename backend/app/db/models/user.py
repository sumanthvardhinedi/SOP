from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

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
        Integer,
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r}, shop_id={self.shop_id})>"
