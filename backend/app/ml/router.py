"""Authenticated read-only next-day forecasts from stored shop sales."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.ml.model import ForecastInputError
from app.ml.schemas import ForecastResponse
from app.ml.service import forecast_sales

router = APIRouter(prefix="/predictions", tags=["Forecasting"])


@router.post("", response_model=ForecastResponse, summary="Forecast next-day sales for your shop")
async def predict_sales(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ForecastResponse:
    """Train on this user's shop history and return predictions without writing data."""
    try:
        return await forecast_sales(db, current_user.shop_id)
    except ForecastInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
