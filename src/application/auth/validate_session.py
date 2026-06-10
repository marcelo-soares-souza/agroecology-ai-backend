from __future__ import annotations

import logging

from src.domain.models.user import User
from src.domain.ports.auth_services_port import TokenServicePort
from src.domain.ports.user_repository import UserRepository
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.auth")


class ValidateSession:
    def __init__(
        self, token_service: TokenServicePort, user_repo: UserRepository
    ) -> None:
        self._token_service = token_service
        self._user_repo = user_repo

    async def execute(self, token: str, client_ip: str) -> User | None:
        payload = self._token_service.decode(token)
        if not payload:
            log_event(logger, logging.WARNING, "auth_invalid_token", ip=client_ip)
            return None

        user_id = payload.get("sub")
        if not user_id:
            log_event(logger, logging.WARNING, "auth_missing_subject", ip=client_ip)
            return None

        user = await self._user_repo.get_by_id(user_id)
        if not user:
            log_event(
                logger,
                logging.WARNING,
                "auth_user_not_found",
                user_id=user_id,
                ip=client_ip,
            )
            return None

        if user.status != "active":
            log_event(
                logger,
                logging.WARNING,
                "auth_user_inactive",
                user_id=user.id,
                ip=client_ip,
            )
            return None

        return user
