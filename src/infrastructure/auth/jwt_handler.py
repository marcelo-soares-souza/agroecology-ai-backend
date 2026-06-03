from __future__ import annotations

import time

import jwt

from src.shared.config import JWT_SECRET, JWT_TTL_SECONDS

_ALGORITHM = "HS256"


def create_access_token(user_id: str, roles: list[str]) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "roles": roles,
            "iat": now,
            "exp": now + JWT_TTL_SECONDS,
            "jti": _generate_jti(),
        },
        JWT_SECRET,
        algorithm=_ALGORITHM,
    )


def create_refresh_token(user_id: str) -> str:
    from src.infrastructure.auth.password_hasher import generate_token

    return generate_token(48)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[_ALGORITHM])


def _generate_jti() -> str:
    import uuid

    return str(uuid.uuid4())
