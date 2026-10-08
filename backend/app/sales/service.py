"""Read sales using mandatory shop ownership and optional database filters."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sale import Sale
from app.sales.schemas import SalesQuery


async def get_sales(db: AsyncSession, shop_id: int, filters: SalesQuery) -> list[Sale]:
    """The caller supplies shop_id from the authenticated database user."""
    statement = select(Sale).where(Sale.shop_id == shop_id)
    if filters.start_date is not None:
        statement = statement.where(Sale.date >= filters.start_date)
    if filters.end_date is not None:
        statement = statement.where(Sale.date <= filters.end_date)
    if filters.sku_name is not None:
        statement = statement.where(Sale.sku_name == filters.sku_name)
    result = await db.execute(statement.order_by(Sale.date.asc(), Sale.id.asc()))
    return list(result.scalars().all())
