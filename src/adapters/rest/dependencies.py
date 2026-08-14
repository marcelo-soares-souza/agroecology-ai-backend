from __future__ import annotations

import logging

from src.application.admin.delete_user import DeleteUser as AdminDeleteUser
from src.application.admin.get_user import GetUser as AdminGetUser
from src.application.admin.list_users import ListUsers as AdminListUsers
from src.application.admin.update_user import UpdateUser as AdminUpdateUser
from src.application.auth.confirm_email import ConfirmEmail
from src.application.auth.confirm_password_reset import ConfirmPasswordReset
from src.application.auth.delete_my_account import (
    ConfirmDeleteAccount,
    RequestDeleteAccount,
)
from src.application.auth.export_my_data import ExportMyData
from src.application.auth.get_avatar_file import GetAvatarFile
from src.application.auth.get_human_challenge import GetHumanChallenge
from src.application.auth.get_user_by_slug import GetUserBySlug
from src.application.auth.list_active_users import ListActiveUsers
from src.application.auth.login_user import LoginUser
from src.application.auth.logout_user import LogoutUser
from src.application.auth.orcid_auth import OrcidAuthService
from src.application.auth.refresh_token import RefreshToken
from src.application.auth.register_user import RegisterUser
from src.application.auth.request_password_reset import RequestPasswordReset
from src.application.auth.resend_confirmation import ResendConfirmationEmail
from src.application.auth.update_my_profile import UpdateMyProfile
from src.application.auth.upload_my_avatar import UploadMyAvatar
from src.application.auth.validate_session import ValidateSession
from src.application.delete_document import DeleteDocument
from src.application.enqueue_academic_metadata_extraction import (
    EnqueueAcademicMetadataExtraction,
)
from src.application.enqueue_pending_metadata import EnqueuePendingMetadata
from src.application.extract_document_metadata import ExtractDocumentMetadata
from src.application.get_academic_metadata_run_status import (
    GetAcademicMetadataRunStatus,
)
from src.application.get_document_details import GetDocumentDetails
from src.application.get_document_file import GetDocumentFile
from src.application.get_metadata_job_status import GetMetadataJobStatus
from src.application.get_status import GetStatus
from src.application.get_task_status import GetTaskStatus
from src.application.list_document_publication_years import (
    ListDocumentPublicationYears,
)
from src.application.list_documents import ListDocuments
from src.application.list_ingestion_runs import ListIngestionRuns
from src.application.manage_documents import ManageDocuments
from src.application.start_document_academic_metadata_extraction import (
    StartDocumentAcademicMetadataExtraction,
)
from src.application.suggestions.admin_approve_all_pending_document_suggestions import (
    AdminApproveAllPendingDocumentSuggestions as AdminApproveAllPending,
)
from src.application.suggestions.admin_approve_document_suggestion import (
    AdminApproveDocumentSuggestion,
)
from src.application.suggestions.admin_delete_document_suggestion import (
    AdminDeleteDocumentSuggestion,
)
from src.application.suggestions.admin_list_document_suggestions import (
    AdminListDocumentSuggestions,
)
from src.application.suggestions.admin_reject_document_suggestion import (
    AdminRejectDocumentSuggestion,
)
from src.application.suggestions.admin_update_document_suggestion import (
    AdminUpdateDocumentSuggestion,
)
from src.application.suggestions.create_document_suggestion import (
    CreateDocumentSuggestion,
)
from src.application.suggestions.delete_document_suggestion import (
    DeleteDocumentSuggestion,
)
from src.application.suggestions.get_document_suggestion import GetDocumentSuggestion
from src.application.suggestions.get_suggestion_file import GetSuggestionFile
from src.application.suggestions.list_my_document_suggestions import (
    ListMyDocumentSuggestions,
)
from src.application.suggestions.list_public_suggestions import ListPublicSuggestions
from src.application.suggestions.replace_suggestion_file import ReplaceSuggestionFile
from src.application.suggestions.update_document_suggestion import (
    UpdateDocumentSuggestion,
)
from src.application.update_document_metadata import UpdateDocumentMetadata
from src.application.upload_document import UploadDocument
from src.bootstrap.ask_task_service import AskTaskService
from src.bootstrap.container import container
from src.bootstrap.ingestion_task_service import IngestionTaskService
from src.domain.ports.auth_rate_limiter_port import AuthRateLimiterPort
from src.domain.ports.chat_conversation_repository import ChatConversationRepository

logger = logging.getLogger("agroecology.bootstrap")


def get_manage_docs() -> ManageDocuments | None:
    return container.manage_docs


def get_status_service() -> GetStatus | None:
    return container.get_status


def get_task_status() -> GetTaskStatus:
    assert container.task_status is not None
    return container.task_status


def get_ask_task_service() -> AskTaskService:
    assert container.ask_task_service is not None, "ask_task_service not initialized"
    return container.ask_task_service


def get_chat_conversation_repo() -> ChatConversationRepository:
    assert container.chat_repo is not None, "chat_repo not initialized"
    return container.chat_repo


def get_ingestion_task_service() -> IngestionTaskService:
    assert container.ingestion_task_service is not None, (
        "ingestion_task_service not initialized"
    )
    return container.ingestion_task_service


# ── Auth use case getters ────────────────────────────────────────────────


def get_register_user() -> RegisterUser:
    assert container.register_user is not None
    return container.register_user


def get_human_challenge() -> GetHumanChallenge:
    assert container.get_human_challenge is not None
    return container.get_human_challenge


def get_auth_rate_limiter() -> AuthRateLimiterPort:
    assert container.auth_rate_limiter is not None
    return container.auth_rate_limiter


def get_login_user() -> LoginUser:
    assert container.login_user is not None
    return container.login_user


def get_orcid_auth_service() -> OrcidAuthService:
    assert container.orcid_auth_service is not None
    return container.orcid_auth_service


def get_refresh_token() -> RefreshToken:
    assert container.refresh_token is not None
    return container.refresh_token


def get_logout_user() -> LogoutUser:
    assert container.logout_user is not None
    return container.logout_user


def get_confirm_email() -> ConfirmEmail:
    assert container.confirm_email is not None
    return container.confirm_email


def get_user_by_slug() -> GetUserBySlug:
    assert container.get_user_by_slug is not None
    return container.get_user_by_slug


def get_resend_confirmation_email() -> ResendConfirmationEmail:
    assert container.resend_confirmation_email is not None
    return container.resend_confirmation_email


def get_request_password_reset() -> RequestPasswordReset:
    assert container.request_password_reset is not None
    return container.request_password_reset


def get_confirm_password_reset() -> ConfirmPasswordReset:
    assert container.confirm_password_reset is not None
    return container.confirm_password_reset


def get_update_my_profile() -> UpdateMyProfile:
    assert container.update_my_profile is not None
    return container.update_my_profile


def get_upload_my_avatar() -> UploadMyAvatar:
    assert container.upload_my_avatar is not None
    return container.upload_my_avatar


def get_list_active_users() -> ListActiveUsers:
    assert container.list_active_users is not None
    return container.list_active_users


def get_validate_session() -> ValidateSession:
    assert container.validate_session is not None
    return container.validate_session


def get_avatar_file() -> GetAvatarFile:
    assert container.get_avatar_file is not None
    return container.get_avatar_file


def get_export_my_data() -> ExportMyData:
    assert container.export_my_data is not None
    return container.export_my_data


def get_request_delete_account() -> RequestDeleteAccount:
    assert container.request_delete_account is not None
    return container.request_delete_account


def get_confirm_delete_account() -> ConfirmDeleteAccount:
    assert container.confirm_delete_account is not None
    return container.confirm_delete_account


# ── Admin use case getters ───────────────────────────────────────────────


def get_list_users() -> AdminListUsers:
    assert container.list_users is not None
    return container.list_users


def get_admin_get_user() -> AdminGetUser:
    assert container.get_user is not None
    return container.get_user


def get_update_user() -> AdminUpdateUser:
    assert container.update_user is not None
    return container.update_user


def get_delete_user() -> AdminDeleteUser:
    assert container.delete_user is not None
    return container.delete_user


# ── Document use case getters ────────────────────────────────────────────


def get_upload_document() -> UploadDocument:
    assert container.upload_document is not None
    return container.upload_document


def get_extract_document_metadata() -> ExtractDocumentMetadata:
    assert container.extract_document_metadata is not None
    return container.extract_document_metadata


def get_list_documents() -> ListDocuments:
    assert container.list_documents is not None
    return container.list_documents


def get_list_document_publication_years() -> ListDocumentPublicationYears:
    assert container.list_document_publication_years is not None
    return container.list_document_publication_years


def get_document_details() -> GetDocumentDetails:
    assert container.get_document_details is not None
    return container.get_document_details


def get_update_document_metadata() -> UpdateDocumentMetadata:
    assert container.update_document_metadata is not None
    return container.update_document_metadata


def get_document_file() -> GetDocumentFile:
    assert container.get_document_file is not None
    return container.get_document_file


def get_delete_document() -> DeleteDocument:
    assert container.delete_document is not None
    return container.delete_document


def get_list_ingestion_runs() -> ListIngestionRuns:
    assert container.list_ingestion_runs is not None
    return container.list_ingestion_runs


def get_enqueue_pending_metadata() -> EnqueuePendingMetadata:
    assert container.enqueue_pending_metadata is not None
    return container.enqueue_pending_metadata


def get_metadata_job_status() -> GetMetadataJobStatus:
    assert container.get_metadata_job_status is not None
    return container.get_metadata_job_status


def get_enqueue_academic_metadata_extraction() -> EnqueueAcademicMetadataExtraction:
    assert container.enqueue_academic_metadata_extraction is not None
    return container.enqueue_academic_metadata_extraction


def get_start_document_academic_metadata_extraction() -> (
    StartDocumentAcademicMetadataExtraction
):
    assert container.start_document_academic_metadata_extraction is not None
    return container.start_document_academic_metadata_extraction


def get_academic_metadata_run_status() -> GetAcademicMetadataRunStatus:
    assert container.get_academic_metadata_run_status is not None
    return container.get_academic_metadata_run_status


# ── Suggestion use case getters ──────────────────────────────────────────


def get_create_document_suggestion() -> CreateDocumentSuggestion:
    assert container.create_document_suggestion is not None
    return container.create_document_suggestion


def get_list_my_document_suggestions() -> ListMyDocumentSuggestions:
    assert container.list_my_document_suggestions is not None
    return container.list_my_document_suggestions


def get_get_document_suggestion() -> GetDocumentSuggestion:
    assert container.get_document_suggestion is not None
    return container.get_document_suggestion


def get_update_document_suggestion() -> UpdateDocumentSuggestion:
    assert container.update_document_suggestion is not None
    return container.update_document_suggestion


def get_delete_document_suggestion() -> DeleteDocumentSuggestion:
    assert container.delete_document_suggestion is not None
    return container.delete_document_suggestion


def get_replace_suggestion_file() -> ReplaceSuggestionFile:
    assert container.replace_suggestion_file is not None
    return container.replace_suggestion_file


def get_suggestion_file() -> GetSuggestionFile:
    assert container.get_suggestion_file is not None
    return container.get_suggestion_file


def get_admin_list_document_suggestions() -> AdminListDocumentSuggestions:
    assert container.admin_list_document_suggestions is not None
    return container.admin_list_document_suggestions


def get_admin_update_document_suggestion() -> AdminUpdateDocumentSuggestion:
    assert container.admin_update_document_suggestion is not None
    return container.admin_update_document_suggestion


def get_admin_reject_document_suggestion() -> AdminRejectDocumentSuggestion:
    assert container.admin_reject_document_suggestion is not None
    return container.admin_reject_document_suggestion


def get_admin_approve_document_suggestion() -> AdminApproveDocumentSuggestion:
    assert container.admin_approve_document_suggestion is not None
    return container.admin_approve_document_suggestion


def get_admin_approve_all_pending_document_suggestions() -> AdminApproveAllPending:
    assert container.admin_approve_all_pending_document_suggestions is not None
    return container.admin_approve_all_pending_document_suggestions


def get_admin_delete_document_suggestion() -> AdminDeleteDocumentSuggestion:
    assert container.admin_delete_document_suggestion is not None
    return container.admin_delete_document_suggestion


def get_list_public_suggestions() -> ListPublicSuggestions:
    assert container.list_public_suggestions is not None
    return container.list_public_suggestions


async def init_services() -> None:
    await container.init()


async def shutdown_services() -> None:
    await container.shutdown()
