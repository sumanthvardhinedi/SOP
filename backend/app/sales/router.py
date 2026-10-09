"""Authenticated, read-only sales retrieval."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.sales.schemas import SaleResponse, SalesQuery, SalesResponse
from app.sales.service import get_sales

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.get("", response_model=SalesResponse, summary="Retrieve the authenticated shop's sales")
async def read_sales(
    filters: Annotated[SalesQuery, Query()],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SalesResponse:
    rows = await get_sales(db, current_user.shop_id, filters)
    return SalesResponse(
        items=[SaleResponse.model_validate(row) for row in rows],
        total=len(rows),
    )
