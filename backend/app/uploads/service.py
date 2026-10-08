"""Validate an entire sales workbook. This module never accesses the database."""
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from pathlib import PurePath

from app.uploads.parser import iter_excel_rows
from app.uploads.schemas import SalesValidationError, ValidatedSale, ValidationIssue

REQUIRED_COLUMNS = ("shop_id", "sku_name", "num_units_sold", "date")
DEFAULT_MAX_BYTES = 20 * 1024 * 1024


def _shop_id(value: object, authenticated_shop_id: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("shop_id must be an integer")
    number = Decimal(str(value))
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError("shop_id must be an integer")
    if number != authenticated_shop_id:
        raise ValueError(
            f"shop_id {number} does not match authenticated user's shop_id {authenticated_shop_id}"
        )
    return authenticated_shop_id


def _sku_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("sku_name must be a non-empty string")
    if len(value) > 255:
        raise ValueError("sku_name must be at most 255 characters")
    return value


def _units(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("num_units_sold must be numeric")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("num_units_sold must be finite")
    if number < 0:
        raise ValueError("num_units_sold must be >= 0")
    if number > Decimal("9999999999.99") or number != number.quantize(Decimal("0.01")):
        raise ValueError("num_units_sold must fit NUMERIC(12,2), with at most two decimal places")
    return number


def _date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise ValueError("date must be a valid Excel date cell or ISO date (YYYY-MM-DD)")


def validate_sales_upload(
    contents: bytes,
    filename: str | None,
    authenticated_shop_id: int,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[ValidatedSale]:
    """Return all validated rows, or raise structured errors without a partial preview."""
    if not filename or PurePath(filename).suffix.lower() != ".xlsx":
        raise SalesValidationError([ValidationIssue(message="Only .xlsx files are supported.")], 415)
    if len(contents) > max_bytes:
        raise SalesValidationError([ValidationIssue(message="File exceeds the upload size limit.")], 413)
    if not contents:
        raise SalesValidationError([ValidationIssue(message="File is empty.")])

    validators = {
        "shop_id": lambda value: _shop_id(value, authenticated_shop_id),
        "sku_name": _sku_name,
        "num_units_sold": _units,
        "date": _date,
    }
    errors = []
    validated = []
    data_row_count = 0
    with closing(iter_excel_rows(contents)) as excel_rows:
        header_cells = next(excel_rows, ())
        headers = [cell.value for cell in header_cells]
        if len(headers) != 4 or any(headers.count(column) != 1 for column in REQUIRED_COLUMNS):
            raise SalesValidationError([ValidationIssue(
                row=1,
                message="Headers must contain exactly shop_id, sku_name, num_units_sold, date, "
                        "once each, with no extra columns.",
            )])
        for row_number, cells in enumerate(excel_rows, start=2):
            if all(cell.value is None for cell in cells):
                continue
            data_row_count += 1
            if len(cells) > len(headers):
                errors.append(ValidationIssue(row=row_number, message="Unexpected extra column in data row."))
            row_values = {}
            for index, column in enumerate(headers):
                cell = cells[index] if index < len(cells) else None
                value = cell.value if cell is not None else None
                try:
                    if value is None:
                        raise ValueError(f"{column} is required")
                    if cell.data_type in {"f", "e"}:
                        raise ValueError(f"{column} must not contain a formula or Excel error")
                    row_values[column] = validators[column](value)
                except ValueError as exc:
                    errors.append(ValidationIssue(row=row_number, column=column, message=str(exc)))
            if len(row_values) == 4:
                validated.append(ValidatedSale(**row_values))
    if not data_row_count:
        errors.append(ValidationIssue(message="Workbook must contain at least one data row."))
    if errors:
        raise SalesValidationError(errors)
    return validated
