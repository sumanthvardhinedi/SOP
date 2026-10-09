"""FastAPI reusable authentication and authorization dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.database import get_db
from app.db.models.user import User

# auto_error=False ensures missing or malformed Authorization headers consistently return HTTP 401
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized_exception(detail: str = "Could not validate credentials.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve and return the authenticated User ORM model from the Bearer JWT.

    Multi-Shop Security Rule:
    All downstream endpoints MUST derive the user's shop via `current_user.shop_id`
    from this database-backed `User` instance—never from client-supplied parameters.
    """
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized_exception("Authentication credentials were not provided.")

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except ExpiredSignatureError as exc:
        raise _unauthorized_exception("Token has expired.") from exc
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise _unauthorized_exception("Invalid authentication token.") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise _unauthorized_exception("Authenticated user no longer exists.")

    return user

