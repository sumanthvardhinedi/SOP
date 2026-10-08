"""Authenticated validation-only sales upload route."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.uploads.schemas import SalesValidationError, SalesValidationResponse
from app.uploads.service import validate_sales_upload

router = APIRouter(prefix="/sales/upload", tags=["Sales upload"])


@router.post("/validate", response_model=SalesValidationResponse)
async def validate_upload(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> SalesValidationResponse:
    """Validate an .xlsx file against the stored user's shop without persisting rows."""
    limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    try:
        contents = await file.read(limit + 1)
    finally:
        await file.close()
    try:
        rows = await run_in_threadpool(
            validate_sales_upload, contents, file.filename, current_user.shop_id, max_bytes=limit
        )
    except SalesValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"success": False, "errors": [error.model_dump() for error in exc.errors]},
        ) from exc
    return SalesValidationResponse(row_count=len(rows), rows=rows)
