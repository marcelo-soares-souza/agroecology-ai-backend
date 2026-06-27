from __future__ import annotations

import logging

from src.domain.dto.data_export import (
    ExportedExternalIdentityData,
    ExportedSuggestionData,
    ExportedUserData,
    PersonalDataExport,
)
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.external_identity_repository import ExternalIdentityRepository
from src.domain.ports.user_repository import UserRepository

logger = logging.getLogger("agroecology.auth")


class ExportMyData:
    def __init__(
        self,
        user_repo: UserRepository,
        suggestion_repo: DocumentSuggestionRepository,
        external_identity_repo: ExternalIdentityRepository | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._suggestion_repo = suggestion_repo
        self._external_identity_repo = external_identity_repo

    async def execute(self, user_id: str) -> PersonalDataExport:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        suggestions = await self._suggestion_repo.list_for_user(user_id)
        external_identities = (
            await self._external_identity_repo.list_for_user(user_id)
            if self._external_identity_repo is not None
            else []
        )

        return PersonalDataExport(
            user=ExportedUserData(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                slug=user.slug,
                locale=user.locale,
                status=user.status,
                about=user.about,
                link=user.link,
                created_at=user.created_at.isoformat() if user.created_at else None,
                updated_at=user.updated_at.isoformat() if user.updated_at else None,
                email_confirmed_at=(
                    user.email_confirmed_at.isoformat()
                    if user.email_confirmed_at
                    else None
                ),
                last_login_at=(
                    user.last_login_at.isoformat() if user.last_login_at else None
                ),
                roles=user.roles,
                approved_suggestions_count=user.approved_suggestions_count,
                privacy_policy_accepted=user.privacy_policy_accepted,
                privacy_policy_accepted_at=(
                    user.privacy_policy_accepted_at.isoformat()
                    if user.privacy_policy_accepted_at
                    else None
                ),
                privacy_policy_version=user.privacy_policy_version,
                tos_accepted=user.tos_accepted,
                tos_accepted_at=(
                    user.tos_accepted_at.isoformat() if user.tos_accepted_at else None
                ),
                tos_version=user.tos_version,
                deleted_at=user.deleted_at.isoformat() if user.deleted_at else None,
                erased_at=user.erased_at.isoformat() if user.erased_at else None,
                erasure_status=user.erasure_status,
            ),
            suggestions=[
                ExportedSuggestionData(
                    id=s.id,
                    status=s.status,
                    title=s.title,
                    authors=s.authors,
                    url=s.url,
                    user_comment=s.user_comment,
                    admin_comment=s.admin_comment,
                    original_filename=s.original_filename,
                    file_type=s.file_type,
                    file_size=s.file_size,
                    document_id=s.document_id,
                    reviewed_by=s.reviewed_by,
                    reviewed_at=s.reviewed_at.isoformat() if s.reviewed_at else None,
                    created_at=s.created_at.isoformat(),
                    updated_at=s.updated_at.isoformat(),
                )
                for s in suggestions
            ],
            external_identities=[
                ExportedExternalIdentityData(
                    id=identity.id,
                    provider=identity.provider,
                    external_user_id=identity.external_user_id,
                    external_email=identity.external_email,
                    external_slug=identity.external_slug,
                    created_at=identity.created_at.isoformat(),
                    updated_at=identity.updated_at.isoformat(),
                    deleted_at=(
                        identity.deleted_at.isoformat()
                        if identity.deleted_at
                        else None
                    ),
                )
                for identity in external_identities
            ],
        )
