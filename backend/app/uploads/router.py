"""Authenticated Excel validation and persistence routes."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.uploads.persistence import persist_sales
from app.uploads.schemas import (
    SalesUploadResponse, SalesValidationError, SalesValidationResponse, ValidatedSale,
)
from app.uploads.service import validate_sales_upload

router = APIRouter(prefix="/sales/upload", tags=["Sales upload"])


async def _validated_rows(
    file: UploadFile, current_user: User, *, reject_duplicate_keys: bool = False
) -> list[ValidatedSale]:
    limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    try:
        contents = await file.read(limit + 1)
    finally:
        await file.close()
    try:
        return await run_in_threadpool(
            validate_sales_upload, contents, file.filename, current_user.shop_id,
            max_bytes=limit, reject_duplicate_keys=reject_duplicate_keys,
        )
    except SalesValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"success": False, "errors": [error.model_dump() for error in exc.errors]},
        ) from exc


@router.post("/validate", response_model=SalesValidationResponse)
async def validate_upload(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> SalesValidationResponse:
    """Validate an .xlsx file against the stored user's shop without persisting rows."""
    rows = await _validated_rows(file, current_user)
    return SalesValidationResponse(row_count=len(rows), rows=rows)


@router.post("", response_model=SalesUploadResponse)
async def upload_sales(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SalesUploadResponse:
    """Validate the entire workbook, then atomically insert or replace daily sales."""
    rows = await _validated_rows(file, current_user, reject_duplicate_keys=True)
    try:
        return await persist_sales(db, rows, current_user.shop_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not save the sales upload. The transaction was rolled back.",
        ) from exc
