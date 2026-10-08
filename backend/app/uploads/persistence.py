"""Atomic PostgreSQL upserts for already validated sales rows."""
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sale import Sale
from app.uploads.schemas import SalesUploadResponse, ValidatedSale

# Four bound values per row; stay well below asyncpg's 32,767-parameter limit.
UPSERT_BATCH_SIZE = 1_000


async def persist_sales(
    db: AsyncSession, rows: list[ValidatedSale], authenticated_shop_id: int
) -> SalesUploadResponse:
    """Commit all rows once; roll back the whole upload on any write/commit error.

    The caller owns a request-scoped session, already begun by get_current_user.
    Sorting keys gives overlapping uploads a consistent row-lock acquisition order.
    """
    # Defense in depth for non-HTTP callers; never persist an untrusted shop ID.
    if any(row.shop_id != authenticated_shop_id for row in rows):
        raise ValueError("Validated rows must belong to the authenticated user's shop.")
    ordered = sorted(rows, key=lambda row: (row.shop_id, row.date, row.sku_name))
    inserted_count = 0
    try:
        for offset in range(0, len(ordered), UPSERT_BATCH_SIZE):
            values = [
                {**row.model_dump(), "shop_id": authenticated_shop_id}
                for row in ordered[offset:offset + UPSERT_BATCH_SIZE]
            ]
            statement = insert(Sale).values(values)
            statement = statement.on_conflict_do_update(
                constraint="uq_sales_shop_id_date_sku_name",
                set_={"num_units_sold": statement.excluded.num_units_sold},
            ).returning(
                # PostgreSQL's updated conflict tuple has nonzero xmax, whereas
                # a newly inserted tuple has zero. Count results from the write,
                # rather than using a racy pre-write SELECT of existing keys.
                literal_column("xmax = 0").label("inserted")
            )
            result = await db.execute(statement)
            inserted_count += sum(bool(inserted) for inserted in result.scalars())
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return SalesUploadResponse(
        row_count=len(rows), inserted_count=inserted_count,
        updated_count=len(rows) - inserted_count,
    )
