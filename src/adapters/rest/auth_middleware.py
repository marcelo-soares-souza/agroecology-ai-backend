from __future__ import annotations


from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.auth.jwt_handler import decode_token
from src.domain.models.user import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    from src.adapters.rest.dependencies import _user_repo

    if _user_repo is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    user = await _user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.status != "active":
        raise HTTPException(status_code=401, detail="Account not active")

    return user


def require_role(role: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.roles is None or role not in user.roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency
