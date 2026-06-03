from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from src.adapters.rest.auth_middleware import get_current_user
from src.adapters.rest.schemas import (
    ChallengeResponse,
    ConfirmEmailRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from src.domain.models.user import User
from src.infrastructure.auth.human_check import create_challenge, verify_challenge
from src.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
)
from src.infrastructure.auth.password_hasher import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from src.shared.config import REFRESH_TOKEN_TTL_DAYS

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status,
        "slug": user.slug,
        "locale": user.locale,
        "roles": user.roles or [],
        "email_confirmed_at": user.email_confirmed_at.isoformat()
        if user.email_confirmed_at
        else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


@router.get("/human-challenge", response_model=ChallengeResponse)
async def get_human_challenge(locale: str = "pt-BR"):
    return create_challenge(locale)


@router.post("/register", response_model=MessageResponse)
async def register(body: RegisterRequest):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()

    if not verify_challenge(body.challenge_id, body.challenge_answer):
        raise HTTPException(status_code=400, detail="Invalid challenge answer")

    existing = await repo.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    import re
    import unicodedata

    slug_base = unicodedata.normalize("NFD", body.full_name.lower())
    slug_base = "".join(c for c in slug_base if not unicodedata.combining(c))
    slug_base = re.sub(r"[^a-z0-9]+", "-", slug_base).strip("-")
    slug = slug_base or body.email.split("@")[0]

    password_hash = hash_password(body.password)
    user = await repo.create(
        email=body.email,
        full_name=body.full_name,
        password_hash=password_hash,
        slug=slug,
        locale=body.locale,
        role_key="user",
    )

    token = generate_token()
    token_hash = hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    await repo.create_confirmation(user.id, token_hash, expires_at)

    return MessageResponse(
        message="Registration successful. Check your email to confirm your account."
    )


@router.post("/confirm-email", response_model=MessageResponse)
async def confirm_email(body: ConfirmEmailRequest):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    token_hash = hash_token(body.token)
    confirmation = await repo.get_confirmation(token_hash)

    if not confirmation:
        raise HTTPException(
            status_code=400, detail="Invalid or expired confirmation token"
        )
    if confirmation["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Confirmation token expired")

    await repo.confirm_email(confirmation["user_id"])
    await repo.mark_confirmation_done(confirmation["id"])

    return MessageResponse(message="Email confirmed successfully. You can now login.")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    user = await repo.get_by_email(body.email)

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.email_confirmed_at is None:
        raise HTTPException(status_code=401, detail="Email not confirmed")
    if user.status != "active":
        raise HTTPException(status_code=401, detail="Account is not active")

    await repo.update_last_login(user.id)

    roles = user.roles or []
    access_token = create_access_token(user.id, roles)
    raw_refresh = create_refresh_token(user.id)
    refresh_hash = hash_token(raw_refresh)
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    await repo.store_refresh_token(user.id, refresh_hash, exp)

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    token_hash = hash_token(refresh_token)
    stored = await repo.get_refresh_token(token_hash)

    if not stored:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if stored["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")
    if stored.get("revoked_at"):
        await repo.revoke_all_refresh_tokens(stored["user_id"])
        raise HTTPException(status_code=401, detail="Token reuse detected")

    await repo.revoke_refresh_token(token_hash)

    user = await repo.get_by_id(stored["user_id"])
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="Account not active")

    roles = user.roles or []
    access_token = create_access_token(user.id, roles)
    raw_refresh = create_refresh_token(user.id)
    new_hash = hash_token(raw_refresh)
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    await repo.store_refresh_token(user.id, new_hash, exp)

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/logout", response_model=MessageResponse)
async def logout(user: User = Depends(get_current_user)):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    await repo.revoke_all_refresh_tokens(user.id)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return _serialize_user(user)
