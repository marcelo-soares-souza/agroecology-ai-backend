from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.domain.models.user import User
from src.infrastructure.auth.jwt_handler import decode_token
from src.shared.logging_utils import log_event, resolve_client_ip

security = HTTPBearer(auto_error=False)
logger = logging.getLogger("agroecology.auth")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    client_ip = resolve_client_ip(
        request.headers, request.client.host if request.client else None
    )
    if credentials is None:
        log_event(logger, logging.WARNING, "auth_missing_credentials", ip=client_ip)
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        log_event(logger, logging.WARNING, "auth_invalid_token", ip=client_ip)
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        log_event(logger, logging.WARNING, "auth_missing_subject", ip=client_ip)
        raise HTTPException(status_code=401, detail="Invalid token")

    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    user = await repo.get_by_id(user_id)
    if not user:
        log_event(
            logger,
            logging.WARNING,
            "auth_user_not_found",
            user_id=user_id,
            ip=client_ip,
        )
        raise HTTPException(status_code=401, detail="User not found")
    if user.status != "active":
        log_event(
            logger, logging.WARNING, "auth_user_inactive", user_id=user.id, ip=client_ip
        )
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
