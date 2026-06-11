from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.adapters.rest.auth_middleware import require_role
from src.adapters.rest.dependencies import (
    get_admin_get_user,
    get_delete_user,
    get_list_users,
    get_update_user,
)
from src.adapters.rest.schemas import MessageResponse, UserResponse, UserUpdateRequest
from src.domain.models.user import User
from src.shared.logging_utils import log_event

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = logging.getLogger("agroecology.audit")


def _raise_admin_error(message: str) -> None:
    lower = message.lower()
    if "cannot " in lower or "last administrator" in lower:
        raise HTTPException(status_code=403, detail=message)
    raise HTTPException(status_code=400, detail=message)


@router.get("/users", response_model=list[UserResponse])
async def list_users(user: User = Depends(require_role("admin"))):
    return await get_list_users().execute()


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, user: User = Depends(require_role("admin"))):
    result = await get_admin_get_user().execute(user_id=user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, body: UserUpdateRequest, user: User = Depends(require_role("admin"))
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="update_user",
        admin_id=user.id,
        target_id=user_id,
        new_status=body.status,
        new_role_key=body.role_key,
    )
    try:
        result = await get_update_user().execute(
            actor_user_id=user.id,
            user_id=user_id,
            full_name=body.full_name,
            email=body.email,
            status=body.status,
            locale=body.locale,
            role_key=body.role_key,
        )
    except ValueError as exc:
        _raise_admin_error(str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(user_id: str, user: User = Depends(require_role("admin"))):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="delete_user",
        admin_id=user.id,
        target_id=user_id,
    )
    try:
        result = await get_delete_user().execute(actor_user_id=user.id, user_id=user_id)
    except ValueError as exc:
        _raise_admin_error(str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return MessageResponse(message="User deleted successfully")
