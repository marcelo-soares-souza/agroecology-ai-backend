from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.domain.models.user import User
from src.infrastructure.auth.jwt_handler import decode_token
from src.shared.logging_utils import log_event

security = HTTPBearer(auto_error=False)
logger = logging.getLogger("agroecology.auth")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    if credentials is None:
        log_event(logger, logging.WARNING, "auth_missing_credentials")
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        log_event(logger, logging.WARNING, "auth_invalid_token")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        log_event(logger, logging.WARNING, "auth_missing_subject")
        raise HTTPException(status_code=401, detail="Invalid token")

    from src.adapters.rest.dependencies import _user_repo

    if _user_repo is None:
        log_event(logger, logging.ERROR, "auth_service_not_initialized")
        raise HTTPException(status_code=503, detail="Service not initialized")
    user = await _user_repo.get_by_id(user_id)
    if not user:
        log_event(logger, logging.WARNING, "auth_user_not_found", user_id=user_id)
        raise HTTPException(status_code=401, detail="User not found")
    if user.status != "active":
        log_event(logger, logging.WARNING, "auth_user_inactive", user_id=user.id)
        raise HTTPException(status_code=401, detail="Account not active")

    return user


def require_role(role: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.roles is None or role not in user.roles:
            log_event(
                logger,
                logging.WARNING,
                "auth_insufficient_permissions",
                user_id=user.id,
                required_role=role,
            )
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency
