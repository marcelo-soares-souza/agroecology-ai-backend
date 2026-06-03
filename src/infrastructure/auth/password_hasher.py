from __future__ import annotations

import hashlib
import secrets

import bcrypt

from src.shared.config import PASSWORD_PEPPER


def hash_password(password: str) -> str:
    peppered = password + PASSWORD_PEPPER
    return bcrypt.hashpw(peppered.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    peppered = password + PASSWORD_PEPPER
    return bcrypt.checkpw(peppered.encode(), password_hash.encode())


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
