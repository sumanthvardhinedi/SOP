"""Exports the application models for SQLAlchemy and Alembic discovery."""

from app.db.base import Base
from app.db.models.sale import Sale
from app.db.models.user import User

__all__ = ["Base", "User", "Sale"]
