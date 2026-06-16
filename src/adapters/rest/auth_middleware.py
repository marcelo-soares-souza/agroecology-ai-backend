from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.domain.models.user import User
from src.shared.logging_utils import log_event, resolve_client_ip

security = HTTPBearer(auto_error=False)
logger = logging.getLogger("agroecology.auth")


async def _resolve_token(token_str: str, client_ip: str) -> User:
    from src.adapters.rest.dependencies import get_validate_session

    user = await get_validate_session().execute(token_str, client_ip)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if user.status == "deleted":
        log_event(
            logger,
            logging.WARNING,
            "auth_deleted_account_rejected",
            user_id=user.id,
            ip=client_ip,
        )
        raise HTTPException(status_code=401, detail="Account deleted")
    return user


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

    return await _resolve_token(credentials.credentials, client_ip)


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
