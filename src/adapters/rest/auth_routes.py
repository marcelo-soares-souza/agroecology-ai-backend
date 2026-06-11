from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from src.adapters.rest.auth_middleware import get_current_user
from src.adapters.rest.dependencies import get_confirm_email, get_confirm_password_reset
from src.adapters.rest.dependencies import (
    get_human_challenge as get_human_challenge_use_case,
)
from src.adapters.rest.dependencies import (
    get_confirm_delete_account,
    get_export_my_data,
    get_list_active_users as get_list_active_users_use_case,
)
from src.adapters.rest.dependencies import (
    get_login_user,
    get_logout_user,
    get_refresh_token,
    get_register_user,
    get_request_delete_account,
    get_request_password_reset,
    get_resend_confirmation_email,
)
from src.adapters.rest.dependencies import (
    get_update_my_profile as get_update_my_profile_use_case,
)
from src.adapters.rest.dependencies import (
    get_upload_my_avatar as get_upload_my_avatar_use_case,
)
from src.adapters.rest.dependencies import get_user_by_slug as get_user_by_slug_use_case
from src.adapters.rest.schemas import (
    ChallengeResponse,
    ConfirmEmailRequest,
    DeleteAccountConfirmRequest,
    ExportDataResponse,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PublicUserResponse,
    RefreshRequest,
    RegisterRequest,
    ResendConfirmationRequest,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from src.adapters.rest.serializers import serialize_public_user, serialize_user
from src.domain.models.user import User
from src.shared.logging_utils import log_event, mask_email, resolve_client_ip

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger("agroecology.auth")


@router.get("/human-challenge", response_model=ChallengeResponse)
async def human_challenge(request: Request, locale: str = "pt-BR"):
    log_event(
        logger,
        logging.INFO,
        "human_challenge_requested",
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        locale=locale,
    )
    return get_human_challenge_use_case().execute(locale)


@router.post("/register", response_model=MessageResponse)
async def register(body: RegisterRequest, request: Request):
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
    try:
        result = await get_register_user().execute(
            email=body.email,
            full_name=body.full_name,
            password=body.password,
            locale=body.locale,
            challenge_id=body.challenge_id,
            challenge_answer=body.challenge_answer,
            privacy_policy_accepted=body.privacy_policy_accepted,
            tos_accepted=body.tos_accepted,
        )
    except ValueError as e:
        log_event(logger, logging.WARNING, "register_failed", reason=str(e))
        raise HTTPException(status_code=400, detail="Registration failed")

    log_event(
        logger,
        logging.INFO,
        "register_completed",
        user_id=result.id,
        email=mask_email(body.email),
        locale=body.locale,
    )
    return MessageResponse(
        message="Registration successful. Check your email to confirm your account."
    )


@router.post("/confirm-email/resend", response_model=MessageResponse)
async def resend_confirmation(body: ResendConfirmationRequest, request: Request):
    log_event(
        logger,
        logging.INFO,
        "confirm_email_resend_requested",
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
        email=mask_email(body.email),
    )
    try:
        result = await get_resend_confirmation_email().execute(email=body.email)
    except ValueError as e:
        log_event(logger, logging.WARNING, "confirm_email_resend_failed", reason=str(e))
        raise HTTPException(
            status_code=400, detail="Confirmation email could not be sent"
        )

    return MessageResponse(message=result.message)


@router.post("/confirm-email", response_model=MessageResponse)
async def confirm_email(body: ConfirmEmailRequest, request: Request):
    try:
        await get_confirm_email().execute(token=body.token)
    except ValueError as e:
        log_event(
            logger,
            logging.WARNING,
            "confirm_email_failed",
            reason=str(e),
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
        )
        raise HTTPException(status_code=400, detail=str(e))

    return MessageResponse(message="Email confirmed successfully. You can now login.")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    try:
        result = await get_login_user().execute(
            email=body.email, password=body.password
        )
    except ValueError as e:
        log_event(
            logger,
            logging.WARNING,
            "login_failed",
            reason=str(e),
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
        )
        raise HTTPException(status_code=401, detail=str(e))

    log_event(
        logger,
        logging.INFO,
        "login_completed",
        user_id=result.user.id,
        ip=resolve_client_ip(
            request.headers, request.client.host if request.client else None
        ),
    )
    return TokenResponse(
        access_token=result.access_token, refresh_token=result.refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request):
    try:
        result = await get_refresh_token().execute(refresh_token=body.refresh_token)
    except ValueError as e:
        log_event(
            logger,
            logging.WARNING,
            "refresh_failed",
            reason=str(e),
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
        )
        raise HTTPException(status_code=401, detail=str(e))

    return TokenResponse(
        access_token=result.access_token, refresh_token=result.refresh_token
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, user: User = Depends(get_current_user)):
    await get_logout_user().execute(user_id=user.id)
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
async def request_password_reset(body: PasswordResetRequest, request: Request):
    try:
        await get_request_password_reset().execute(email=body.email)
    except ValueError:
        pass  # intentionally swallow - don't reveal whether email exists

    return MessageResponse(message="If the email exists, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(body: PasswordResetConfirmRequest, request: Request):
    try:
        await get_confirm_password_reset().execute(
            token=body.token, new_password=body.new_password
        )
    except ValueError as e:
        log_event(
            logger,
            logging.WARNING,
            "password_reset_confirm_failed",
            reason=str(e),
            ip=resolve_client_ip(
                request.headers, request.client.host if request.client else None
            ),
        )
        raise HTTPException(status_code=400, detail=str(e))

    return MessageResponse(message="Password reset successfully")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return serialize_user(user)


@router.put("/me/profile", response_model=UserResponse)
async def update_my_profile(
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        result = await get_update_my_profile_use_case().execute(
            user_id=current_user.id,
            full_name=body.full_name,
            email=body.email,
            about=body.about,
            link=body.link,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(result)


@router.post("/me/profile/avatar", response_model=UserResponse)
async def upload_my_avatar(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    try:
        result = await get_upload_my_avatar_use_case().execute(
            user_id=current_user.id,
            content=content,
            content_type=file.content_type or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return serialize_user(result)


@router.get("/users/by-slug/{slug}", response_model=UserResponse)
async def get_user_by_slug(slug: str):
    user = await get_user_by_slug_use_case().execute(slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(user)


@router.get("/users", response_model=list[PublicUserResponse])
async def list_active_users():
    users = await get_list_active_users_use_case().execute()
    return [serialize_public_user(u) for u in users]


@router.get("/me/export", response_model=ExportDataResponse)
async def export_my_data(user: User = Depends(get_current_user)):
    try:
        data = await get_export_my_data().execute(user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExportDataResponse(**data)


@router.post("/me/delete-request", response_model=MessageResponse)
async def request_delete_account(
    request: Request, user: User = Depends(get_current_user)
):
    try:
        await get_request_delete_account().execute(user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return MessageResponse(
        message="Confirmation email sent. Check your inbox to complete account deletion."
    )


@router.post("/me/delete-confirm", response_model=MessageResponse)
async def confirm_delete_account(body: DeleteAccountConfirmRequest, request: Request):
    try:
        await get_confirm_delete_account().execute(token=body.token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return MessageResponse(message="Account deleted successfully.")
