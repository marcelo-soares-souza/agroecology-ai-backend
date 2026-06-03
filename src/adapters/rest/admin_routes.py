from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.adapters.rest.auth_middleware import require_role
from src.adapters.rest.schemas import MessageResponse, UserResponse, UserUpdateRequest
from src.domain.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


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


@router.get("/users", response_model=list[UserResponse])
async def list_users(user: User = Depends(require_role("admin"))):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    users = await repo.list_all()
    return [_serialize_user(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, user: User = Depends(require_role("admin"))):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    u = await repo.get_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user(u)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, body: UserUpdateRequest, user: User = Depends(require_role("admin"))
):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    kwargs = {}
    if body.full_name is not None:
        kwargs["full_name"] = body.full_name
    if body.email is not None:
        kwargs["email"] = body.email
    if body.status is not None:
        kwargs["status"] = body.status
    if body.locale is not None:
        kwargs["locale"] = body.locale

    u = await repo.update(user_id, **kwargs)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    if body.role_key is not None:
        role_id = (
            "00000000-0000-0000-0000-000000000001"
            if body.role_key == "admin"
            else "00000000-0000-0000-0000-000000000002"
        )
        async with repo._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM user_roles WHERE user_id = %s", (user_id,)
                )
                from src.shared.uuid7 import uuid7

                await cur.execute(
                    "INSERT INTO user_roles (id, user_id, role_id) VALUES (%s,%s,%s)",
                    (uuid7(), user_id, role_id),
                )

    return _serialize_user(u)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(user_id: str, user: User = Depends(require_role("admin"))):
    from src.adapters.rest.dependencies import get_user_repo

    repo = await get_user_repo()
    deleted = await repo.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return MessageResponse(message="User deleted successfully")
