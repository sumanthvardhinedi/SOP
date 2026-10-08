"""Authentication routes: POST /register, POST /login, GET /me."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import Token, UserLogin, UserRegister, UserResponse
from app.auth.service import authenticate_user, register_user
from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user assigned to a shop",
)
async def register(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Create a new user account associated with an existing shop."""
    return await register_user(db=db, payload=payload)


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain a JWT access token",
)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate with email and password and return a Bearer JWT token."""
    return await authenticate_user(db=db, payload=payload)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the currently authenticated user's profile and shop assignment",
)
async def read_current_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the authenticated user's profile (including authoritative `shop_id`)."""
    return current_user

