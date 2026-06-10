from __future__ import annotations

from src.domain.dto.suggestion_file import SuggestionFile
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.config import DATA_DIR_PENDING

_SUGGESTIONS_DIR = DATA_DIR_PENDING.name


class GetSuggestionFile:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        storage: FileStoragePort,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._storage = storage

    async def execute(
        self, suggestion_id: str, user_id: str, is_admin: bool = False
    ) -> SuggestionFile | None:
        if is_admin:
            suggestion = await self._suggestion_repo.get(suggestion_id)
        else:
            suggestion = await self._suggestion_repo.get_for_user(
                suggestion_id, user_id
            )

        if suggestion is None:
            return None
        if not suggestion.original_filename or suggestion.file_type != "pdf":
            return None
        if not await self._storage.exists(_SUGGESTIONS_DIR, suggestion_id, ".pdf"):
            return None

        return SuggestionFile(
            filename=suggestion.original_filename,
            path=self._storage.get_path(_SUGGESTIONS_DIR, suggestion_id, ".pdf"),
            media_type="application/pdf",
        )
