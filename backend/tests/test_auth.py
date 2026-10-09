"""Phase 2 Authentication and Multi-Shop Isolation Test Suite."""

from datetime import timedelta
import uuid

from httpx import AsyncClient
import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    ExpiredSignatureError,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.models.user import User


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@example.com"


# ---------------------------------------------------------------------------
# Health Check Preservation
# ---------------------------------------------------------------------------


async def test_health_endpoint_still_works(client: AsyncClient) -> None:
    """Verify Phase 1 GET /health endpoint remains intact."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Registration Tests (1 - 6)
# ---------------------------------------------------------------------------


async def test_register_user_success(
    client: AsyncClient,
    db_session: AsyncSession,
    shop_a: int,
) -> None:
    """1, 4, 5, 6: Successful registration hashes password, never stores plaintext, and never returns password_hash."""
    email = _unique_email("john")
    raw_password = "StrongPassword!2026"

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "John",
            "email": f"  {email.upper()}  ",
            "password": raw_password,
            "shop_id": shop_a,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "John"
    assert data["email"] == email
    assert data["shop_id"] == shop_a
    assert "id" in data

    # 6. Password and password_hash must never be returned in API response
    assert "password" not in data
    assert "password_hash" not in data

    # 4 & 5. Verify database stores Argon2 hash and never stores plaintext password
    result = await db_session.execute(select(User).where(User.id == data["id"]))
    db_user = result.scalar_one()
    assert db_user.password_hash != raw_password
    assert db_user.password_hash.startswith("$argon2")
    assert verify_password(raw_password, db_user.password_hash) is True


async def test_register_duplicate_email_rejected(
    client: AsyncClient,
    shop_a: int,
) -> None:
    """2. Duplicate email registration returns HTTP 409 Conflict."""
    email = _unique_email("duplicate")
    payload = {
        "name": "First User",
        "email": email,
        "password": "StrongPassword!123",
        "shop_id": shop_a,
    }

    first_res = await client.post("/api/v1/auth/register", json=payload)
    assert first_res.status_code == 201

    # Attempt registering again with same email (case-insensitive)
    second_res = await client.post(
        "/api/v1/auth/register",
        json={**payload, "email": email.upper()},
    )
    assert second_res.status_code == 409
    assert "already registered" in second_res.json()["detail"].lower()


async def test_register_without_shop_record_succeeds(client: AsyncClient) -> None:
    """Registration accepts a shop identifier without a shop lookup."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Orphan User",
            "email": _unique_email("orphan"),
            "password": "StrongPassword!123",
            "shop_id": 999_999_999,
        },
    )
    assert response.status_code == 201
    assert response.json()["shop_id"] == 999_999_999


# ---------------------------------------------------------------------------
# Login Tests (7 - 10)
# ---------------------------------------------------------------------------


async def test_login_success_returns_jwt(
    client: AsyncClient,
    shop_a: int,
) -> None:
    """7 & 10. Valid login credentials return HTTP 200 and a valid Bearer JWT."""
    email = _unique_email("login")
    password = "CorrectHorseBatteryStaple!1"

    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Alice",
            "email": email,
            "password": password,
            "shop_id": shop_a,
        },
    )
    assert reg_res.status_code == 201
    user_id = reg_res.json()["id"]

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert token_data["token_type"] == "bearer"
    assert isinstance(token_data["access_token"], str) and len(token_data["access_token"]) > 20

    decoded = decode_access_token(token_data["access_token"])
    assert int(decoded["sub"]) == user_id
    assert "exp" in decoded
    assert "password" not in decoded
    assert "password_hash" not in decoded


async def test_login_incorrect_password_returns_401(
    client: AsyncClient,
    shop_a: int,
) -> None:
    """8. Login with an incorrect password returns HTTP 401 Unauthorized."""
    email = _unique_email("wrongpass")
    await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Bob",
            "email": email,
            "password": "RightPassword!123",
            "shop_id": shop_a,
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword!999"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    """9. Login with an unknown email returns generic HTTP 401 Unauthorized."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": _unique_email("nonexistent"),
            "password": "AnyPassword!123",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


# ---------------------------------------------------------------------------
# JWT Unit & Security Tests (11 - 13)
# ---------------------------------------------------------------------------


def test_jwt_create_and_decode_valid_token() -> None:
    """11. Valid JWT is created and decoded accurately with sub and exp claims."""
    token = create_access_token(subject=42)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_invalid_token_rejected() -> None:
    """12. Tampered or malformed JWT raises InvalidTokenError."""
    valid_token = create_access_token(subject=42)
    tampered_token = valid_token[:-4] + "xxxx"

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered_token)

    wrong_secret_token = jwt.encode(
        {"sub": "42"},
        "completely-different-secret-key-0000",
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(wrong_secret_token)


def test_jwt_expired_token_rejected() -> None:
    """13. Expired JWT raises ExpiredSignatureError."""
    expired_token = create_access_token(
        subject=42,
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(ExpiredSignatureError):
        decode_access_token(expired_token)


def test_password_hashing_and_verification() -> None:
    """4 & 5. Argon2 password hashing produces salted hashes and verifies accurately."""
    secret = "MySuperSecretPassword!2026"
    hashed = hash_password(secret)
    assert hashed != secret
    assert hashed.startswith("$argon2")
    assert verify_password(secret, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


# ---------------------------------------------------------------------------
# /api/v1/auth/me Tests (14 - 18)
# ---------------------------------------------------------------------------


async def test_me_endpoint_with_valid_token(
    client: AsyncClient,
    shop_a: int,
) -> None:
    """14, 17, 18. GET /api/v1/auth/me with valid token returns correct user and shop_id without password_hash."""
    email = _unique_email("me_valid")
    password = "ValidPassword!123"

    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Sumanth",
            "email": email,
            "password": password,
            "shop_id": shop_a,
        },
    )
    created_user = reg_res.json()

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]

    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["id"] == created_user["id"]
    assert me_data["name"] == "Sumanth"
    assert me_data["email"] == email
    assert me_data["shop_id"] == shop_a
    assert "password" not in me_data
    assert "password_hash" not in me_data


async def test_me_endpoint_missing_token_returns_401(client: AsyncClient) -> None:
    """15. GET /api/v1/auth/me without Authorization header returns HTTP 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_endpoint_invalid_or_expired_token_returns_401(
    client: AsyncClient,
    shop_a: int,
) -> None:
    """16. GET /api/v1/auth/me with invalid or expired token returns HTTP 401."""
    bad_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-jwt-token"},
    )
    assert bad_res.status_code == 401

    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Temp User",
            "email": _unique_email("expired"),
            "password": "ValidPassword!123",
            "shop_id": shop_a,
        },
    )
    user_id = reg_res.json()["id"]
    expired_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(seconds=-30),
    )

    exp_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert exp_res.status_code == 401


# ---------------------------------------------------------------------------
# Multi-Shop Isolation & Identity Authority Test
# ---------------------------------------------------------------------------


async def test_multi_shop_identity_derived_strictly_from_authenticated_user(
    client: AsyncClient,
    shop_a: int,
    shop_b: int,
) -> None:
    """Verify User A (Shop A) and User B (Shop B) always resolve their own shop_id from JWT/database."""
    email_a = _unique_email("user_shop_a")
    email_b = _unique_email("user_shop_b")
    password = "ShopIsolationPassword!1"

    # Register User A in Shop A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "User A",
            "email": email_a,
            "password": password,
            "shop_id": shop_a,
        },
    )
    assert reg_a.status_code == 201

    # Register User B in Shop B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "User B",
            "email": email_b,
            "password": password,
            "shop_id": shop_b,
        },
    )
    assert reg_b.status_code == 201

    # Login both users
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": email_a, "password": password},
    )
    token_a = login_a.json()["access_token"]

    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": email_b, "password": password},
    )
    token_b = login_b.json()["access_token"]

    # Even if User A passes a spoofed ?shop_id=<shop_b> in the query string,
    # the backend resolves User A's authoritative shop_id (shop_a) from the database.
    me_a = await client.get(
        f"/api/v1/auth/me?shop_id={shop_b}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert me_a.status_code == 200
    assert me_a.json()["id"] == reg_a.json()["id"]
    assert me_a.json()["shop_id"] == shop_a
    assert me_a.json()["shop_id"] != shop_b

    # And User B resolves strictly to shop_b
    me_b = await client.get(
        f"/api/v1/auth/me?shop_id={shop_a}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert me_b.status_code == 200
    assert me_b.json()["id"] == reg_b.json()["id"]
    assert me_b.json()["shop_id"] == shop_b
    assert me_b.json()["shop_id"] != shop_a


async def test_me_uses_current_database_shop_despite_token_claim(
    client: AsyncClient,
    db_session: AsyncSession,
    shop_a: int,
    shop_b: int,
) -> None:
    """A stale or misleading JWT shop claim cannot override the database."""
    user = User(
        name="Reassigned User",
        email=_unique_email("reassigned"),
        password_hash=hash_password("ValidPassword!123"),
        shop_id=shop_a,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id, extra_claims={"shop_id": shop_a})
    user.shop_id = shop_b
    await db_session.commit()
    db_session.expunge_all()

    response = await client.get(
        f"/api/v1/auth/me?shop_id={shop_a}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["shop_id"] == shop_b


async def test_me_rejects_token_for_deleted_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = User(
        name="Deleted User",
        email=_unique_email("deleted"),
        password_hash=hash_password("ValidPassword!123"),
        shop_id=101,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id)
    await db_session.delete(user)
    await db_session.commit()

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
