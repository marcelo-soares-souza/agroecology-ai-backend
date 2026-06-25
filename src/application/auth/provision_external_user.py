from __future__ import annotations

import re
import unicodedata

from src.domain.dto.remote_identity import RemoteIdentity
from src.domain.models.user import User
from src.domain.ports.auth_services_port import PasswordHasherPort
from src.domain.ports.external_identity_repository import ExternalIdentityRepository
from src.domain.ports.user_repository import UserRepository


class ProvisionExternalUser:
    def __init__(
        self,
        user_repo: UserRepository,
        external_identity_repo: ExternalIdentityRepository,
        password_hasher: PasswordHasherPort,
        provider: str = "agroecology_map",
    ) -> None:
        self._user_repo = user_repo
        self._external_identity_repo = external_identity_repo
        self._password_hasher = password_hasher
        self._provider = provider

    async def execute(self, remote_identity: RemoteIdentity, password: str) -> User:
        existing_identity = await self._external_identity_repo.get_by_provider_user_id(
            self._provider, remote_identity.external_user_id
        )
        if existing_identity:
            user = await self._user_repo.get_by_id(existing_identity.user_id)
            if user:
                return user

        user = await self._user_repo.get_by_email(remote_identity.email)
        if user is None:
            user = await self._create_user(remote_identity, password)

        await self._external_identity_repo.upsert(
            user_id=user.id,
            provider=self._provider,
            external_user_id=remote_identity.external_user_id,
            external_email=remote_identity.email,
            external_slug=remote_identity.slug,
        )
        return user

    async def _create_user(
        self, remote_identity: RemoteIdentity, password: str
    ) -> User:
        password_hash = self._password_hasher.hash_password(password)
        slug = await self._generate_slug(
            remote_identity.slug or remote_identity.full_name or remote_identity.email
        )
        role_key = "admin" if remote_identity.is_admin else "user"
        user = await self._user_repo.create(
            email=remote_identity.email,
            full_name=remote_identity.full_name,
            password_hash=password_hash,
            slug=slug,
            locale="pt-BR",
            role_key=role_key,
            privacy_policy_accepted=False,
            tos_accepted=False,
        )
        if remote_identity.is_confirmed:
            await self._user_repo.confirm_email(user.id)
            confirmed = await self._user_repo.get_by_id(user.id)
            if confirmed:
                user = confirmed
        if remote_identity.is_admin:
            await self._user_repo.assign_role(user.id, "admin")
            updated = await self._user_repo.get_by_id(user.id)
            if updated:
                user = updated
        return user

    async def _generate_slug(self, value: str) -> str:
        base = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode()
            .strip()
            .lower()
        )
        base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
        if not base:
            base = "user"
        candidate = base[:100].strip("-") or "user"
        suffix = 1
        while await self._user_repo.get_by_slug(candidate) is not None:
            suffix_text = f"-{suffix}"
            candidate = f"{base[: 100 - len(suffix_text)].strip('-')}{suffix_text}"
            suffix += 1
        return candidate
