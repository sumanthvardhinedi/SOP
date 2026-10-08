"""Password hashing (Argon2) and JWT token utilities."""

from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings

# Argon2id password hasher (argon2-cffi default parameters)
_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Never log or persist the plaintext password.
    """
    return _password_hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2 password hash."""
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    subject: int | str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token identifying the user via `sub`.

    Does not include sensitive data (such as passwords or database secrets).
    """
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        # Ensure core claims cannot be accidentally overwritten with unsafe values
        for key, value in extra_claims.items():
            if key not in {"sub", "iat", "exp", "type", "password", "password_hash"}:
                payload[key] = value

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises `ExpiredSignatureError` if expired or `InvalidTokenError` if invalid.
    """
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "exp"]},
    )

    if payload.get("type") not in (None, "access"):
        raise InvalidTokenError("Invalid token type.")

    sub = payload.get("sub")
    if not sub or not str(sub).isdigit() or int(sub) <= 0:
        raise InvalidTokenError("Token subject must be a valid positive user ID.")

    return payload


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "ExpiredSignatureError",
    "InvalidTokenError",
]

