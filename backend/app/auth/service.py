"""Authentication business logic and user verification service."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import Token, UserLogin, UserRegister
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.shop import Shop
from app.db.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Look up a user by normalized email address."""
    normalized_email = email.strip().lower()
    result = await db.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    return result.scalar_one_or_none()


async def get_shop_by_id(db: AsyncSession, shop_id: int) -> Shop | None:
    """Look up a shop by its primary key ID."""
    result = await db.execute(select(Shop).where(Shop.id == shop_id))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, payload: UserRegister) -> User:
    """Register a new user assigned to an existing shop.

    1. Checks for duplicate email.
    2. Verifies that `payload.shop_id` exists in `shops`.
    3. Hashes the password with Argon2id.
    4. Persists the user and returns the ORM object.
    """
    normalized_email = payload.email.strip().lower()

    existing_user = await get_user_by_email(db, normalized_email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address is already registered.",
        )

    shop = await get_shop_by_id(db, payload.shop_id)
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with id {payload.shop_id} does not exist.",
        )

    user = User(
        name=payload.name,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        shop_id=shop.id,
    )

    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not register user due to a conflicting email or invalid shop reference.",
        ) from exc

    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, payload: UserLogin) -> Token:
    """Verify user email and password and issue a signed JWT access token.

    Returns a generic 401 error on failure so email existence is never leaked.
    """
    invalid_credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = await get_user_by_email(db, payload.email)
    if user is None:
        raise invalid_credentials_exc

    if not verify_password(payload.password, user.password_hash):
        raise invalid_credentials_exc

    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer")

