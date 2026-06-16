from __future__ import annotations

import hashlib
import secrets

import bcrypt

from src.shared.config import PASSWORD_PEPPER

BCRYPT_MAX_PASSWORD_BYTES = 72


def _bcrypt_password_bytes(password: str) -> bytes:
    return (password + PASSWORD_PEPPER).encode()[:BCRYPT_MAX_PASSWORD_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        _bcrypt_password_bytes(password), bcrypt.gensalt(rounds=12)
    ).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(_bcrypt_password_bytes(password), password_hash.encode())


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
