from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

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
from src.shared.logging_utils import log_event, mask_email, resolve_client_ip

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger("agroecology.auth")


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
async def get_human_challenge(request: Request, locale: str = "pt-BR"):
    log_event(
        logger,
        logging.INFO,
        "human_challenge_requested",
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        locale=locale,
    )
    return create_challenge(locale)


@router.post("/register", response_model=MessageResponse)
async def register(body: RegisterRequest, request: Request):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()

    log_event(
        logger,
        logging.INFO,
        "register_attempted",
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        email=mask_email(body.email),
        locale=body.locale,
    )
    if not verify_challenge(body.challenge_id, body.challenge_answer):
        log_event(
            logger,
            logging.WARNING,
            "register_failed",
            reason="invalid_challenge",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            email=mask_email(body.email),
        )
        raise HTTPException(status_code=400, detail="Invalid challenge answer")

    existing = await repo.get_by_email(body.email)
    if existing:
        log_event(
            logger,
            logging.WARNING,
            "register_failed",
            reason="email_already_registered",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            email=mask_email(body.email),
        )
        raise HTTPException(status_code=400, detail="Email already registered")

    import re
    import unicodedata

    slug_base = unicodedata.normalize("NFD", body.full_name.lower())
    slug_base = "".join(c for c in slug_base if not unicodedata.combining(c))
    slug_base = re.sub(r"[^a-z0-9]+", "-", slug_base).strip("-")
    slug = slug_base or body.email.split("@")[0]

    existing = await repo.get_by_slug(slug)
    counter = 1
    while existing:
        counter += 1
        slug = f"{slug_base}-{counter}"
        existing = await repo.get_by_slug(slug)

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

    import asyncio as _asyncio

    _asyncio.create_task(
        _send_emails_async(
            email=body.email,
            full_name=body.full_name,
            token=token,
            locale=body.locale,
        )
    )

    log_event(
        logger,
        logging.INFO,
        "register_completed",
        user_id=user.id,
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        email=mask_email(body.email),
        locale=body.locale,
    )

    return MessageResponse(
        message="Registration successful. Check your email to confirm your account."
    )


async def _send_emails_async(
    email: str, full_name: str, token: str, locale: str
) -> None:
    from src.infrastructure.email.smtp_service import (
        send_admin_new_user_notification,
        send_confirmation_email,
    )

    await send_confirmation_email(email, token, locale)
    await send_admin_new_user_notification(email, full_name, locale)


@router.post("/confirm-email/resend", response_model=MessageResponse)
async def resend_confirmation(email: str, request: Request):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    user = await repo.get_by_email(email)
    if not user:
        log_event(
            logger,
            logging.WARNING,
            "confirm_email_resend_failed",
            reason="email_not_found",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            email=mask_email(email),
        )
        raise HTTPException(status_code=400, detail="Email not found")
    if user.email_confirmed_at:
        log_event(
            logger,
            logging.WARNING,
            "confirm_email_resend_failed",
            reason="already_confirmed",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            email=mask_email(email),
            user_id=user.id,
        )
        raise HTTPException(status_code=400, detail="Email already confirmed")

    token = generate_token()
    token_hash = hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    await repo.create_confirmation(user.id, token_hash, expires_at)

    import asyncio as _asyncio2
    from src.infrastructure.email.smtp_service import send_confirmation_email

    _asyncio2.create_task(send_confirmation_email(user.email, token, user.locale))

    log_event(
        logger,
        logging.INFO,
        "confirm_email_resent",
        user_id=user.id,
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        email=mask_email(user.email),
    )

    return MessageResponse(message="Confirmation email resent. Check your inbox.")


@router.post("/confirm-email", response_model=MessageResponse)
async def confirm_email(body: ConfirmEmailRequest, request: Request):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    token_hash = hash_token(body.token)
    confirmation = await repo.get_confirmation(token_hash)

    if not confirmation:
        log_event(
            logger,
            logging.WARNING,
            "confirm_email_failed",
            reason="invalid_or_expired_token",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
        )
        raise HTTPException(
            status_code=400, detail="Invalid or expired confirmation token"
        )
    if confirmation["expires_at"] < datetime.now(timezone.utc):
        log_event(
            logger,
            logging.WARNING,
            "confirm_email_failed",
            reason="token_expired",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            user_id=confirmation["user_id"],
        )
        raise HTTPException(status_code=400, detail="Confirmation token expired")

    await repo.confirm_email(confirmation["user_id"])
    await repo.mark_confirmation_done(confirmation["id"])
    log_event(
        logger,
        logging.INFO,
        "confirm_email_completed",
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        user_id=confirmation["user_id"],
    )

    return MessageResponse(message="Email confirmed successfully. You can now login.")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    user = await repo.get_by_email(body.email)

    if not user or not verify_password(body.password, user.password_hash):
        log_event(
            logger,
            logging.WARNING,
            "login_failed",
            reason="invalid_credentials",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            email=mask_email(body.email),
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.email_confirmed_at is None:
        log_event(
            logger,
            logging.WARNING,
            "login_failed",
            reason="email_not_confirmed",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            user_id=user.id,
            email=mask_email(body.email),
        )
        raise HTTPException(status_code=401, detail="Email not confirmed")
    if user.status != "active":
        log_event(
            logger,
            logging.WARNING,
            "login_failed",
            reason="account_not_active",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            user_id=user.id,
            email=mask_email(body.email),
        )
        raise HTTPException(status_code=401, detail="Account is not active")

    await repo.update_last_login(user.id)

    roles = user.roles or []
    access_token = create_access_token(user.id, roles)
    raw_refresh = create_refresh_token(user.id)
    refresh_hash = hash_token(raw_refresh)
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    await repo.store_refresh_token(user.id, refresh_hash, exp)
    log_event(
        logger,
        logging.INFO,
        "login_completed",
        user_id=user.id,
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        email=mask_email(user.email),
        roles=",".join(roles),
    )

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, request: Request):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    token_hash = hash_token(refresh_token)
    stored = await repo.get_refresh_token(token_hash)

    if not stored:
        log_event(
            logger,
            logging.WARNING,
            "refresh_failed",
            reason="invalid_token",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
        )
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if stored["expires_at"] < datetime.now(timezone.utc):
        log_event(
            logger,
            logging.WARNING,
            "refresh_failed",
            reason="token_expired",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            user_id=stored["user_id"],
        )
        raise HTTPException(status_code=401, detail="Refresh token expired")
    if stored.get("revoked_at"):
        await repo.revoke_all_refresh_tokens(stored["user_id"])
        log_event(
            logger,
            logging.WARNING,
            "refresh_failed",
            reason="token_reuse_detected",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            user_id=stored["user_id"],
        )
        raise HTTPException(status_code=401, detail="Token reuse detected")

    await repo.revoke_refresh_token(token_hash)

    user = await repo.get_by_id(stored["user_id"])
    if not user or user.status != "active":
        log_event(
            logger,
            logging.WARNING,
            "refresh_failed",
            reason="account_not_active",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            user_id=stored["user_id"],
        )
        raise HTTPException(status_code=401, detail="Account not active")

    roles = user.roles or []
    access_token = create_access_token(user.id, roles)
    raw_refresh = create_refresh_token(user.id)
    new_hash = hash_token(raw_refresh)
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    await repo.store_refresh_token(user.id, new_hash, exp)
    log_event(
        logger,
        logging.INFO,
        "refresh_completed",
        user_id=user.id,
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        email=mask_email(user.email),
    )

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, user: User = Depends(get_current_user)):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    await repo.revoke_all_refresh_tokens(user.id)
    log_event(
        logger,
        logging.INFO,
        "logout_completed",
        user_id=user.id,
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
    )
    return MessageResponse(message="Logged out successfully")


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(email: str, request: Request):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    user = await repo.get_by_email(email)
    if not user:
        log_event(
            logger,
            logging.INFO,
            "password_reset_requested",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
            email=mask_email(email),
            user_exists=False,
        )
        return MessageResponse(
            message="If the email exists, a reset link has been sent."
        )

    token = generate_token()
    token_hash = hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await repo.create_confirmation(user.id, token_hash, expires_at)

    from src.infrastructure.email.smtp_service import send_reset_email
    import asyncio as _asyncio3

    _asyncio3.create_task(send_reset_email(user.email, token, user.locale))

    log_event(
        logger,
        logging.INFO,
        "password_reset_requested",
        user_id=user.id,
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        email=mask_email(user.email),
        user_exists=True,
    )

    return MessageResponse(message="If the email exists, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(token: str, new_password: str, request: Request):
    from src.adapters.rest.dependencies import get_user_repo

    if len(new_password) < 8:
        log_event(
            logger,
            logging.WARNING,
            "password_reset_confirm_failed",
            reason="password_too_short",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
        )
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    repo = await get_user_repo()
    token_hash = hash_token(token)
    confirmation = await repo.get_confirmation(token_hash)

    if not confirmation or confirmation["expires_at"] < datetime.now(timezone.utc):
        log_event(
            logger,
            logging.WARNING,
            "password_reset_confirm_failed",
            reason="invalid_or_expired_token",
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
        )
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    password_hash = hash_password(new_password)
    await repo.update(confirmation["user_id"], password_hash=password_hash)
    await repo.mark_confirmation_done(confirmation["id"])
    log_event(
        logger,
        logging.INFO,
        "password_reset_confirmed",
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        user_id=confirmation["user_id"],
    )

    return MessageResponse(message="Password reset successfully")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return _serialize_user(user)


@router.get("/users/by-slug/{slug}", response_model=UserResponse)
async def get_user_by_slug(slug: str):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    user = await repo.get_by_slug(slug)
    if not user:
        user = await repo.get_by_id(slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user(user)
