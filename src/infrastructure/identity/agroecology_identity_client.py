from __future__ import annotations

from typing import Any

import httpx

from src.domain.dto.remote_identity import RemoteIdentity
from src.domain.ports.identity_server_client import (
    IdentityServerClient,
    IdentityServerEmailNotConfirmed,
    IdentityServerInvalidCredentials,
    IdentityServerUnavailable,
)


class AgroecologyIdentityClient(IdentityServerClient):
    def __init__(self, base_url: str, timeout_seconds: float = 8.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def authenticate(self, email: str, password: str) -> RemoteIdentity:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as client:
                csrf_response = await client.get("/api/v1/auth/csrf-token")
                csrf_response.raise_for_status()
                csrf_token = str(csrf_response.json().get("csrfToken", ""))
                if not csrf_token:
                    raise IdentityServerUnavailable("identity.csrf_missing")

                login_response = await client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": password},
                    headers={
                        "X-CSRF-Token": csrf_token,
                        "Cookie": f"csrf_token={csrf_token}",
                    },
                )
                if login_response.status_code == 401:
                    raise IdentityServerInvalidCredentials()
                if login_response.status_code == 403:
                    if self._is_email_not_confirmed(login_response):
                        raise IdentityServerEmailNotConfirmed()
                    raise IdentityServerInvalidCredentials()
                login_response.raise_for_status()
                return self._parse_login_response(login_response.json())
        except (
            IdentityServerEmailNotConfirmed,
            IdentityServerInvalidCredentials,
            IdentityServerUnavailable,
        ):
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise IdentityServerUnavailable(str(exc)) from exc

    @staticmethod
    def _is_email_not_confirmed(response: httpx.Response) -> bool:
        try:
            payload = response.json()
        except ValueError:
            return False
        message_key = payload.get("error", {}).get("message_key")
        return message_key == "auth.email_not_confirmed"

    @staticmethod
    def _parse_login_response(payload: dict[str, Any]) -> RemoteIdentity:
        account = payload["account"]
        name = account.get("name") or account["email"].split("@", 1)[0]
        return RemoteIdentity(
            external_user_id=str(account["id"]),
            email=str(account["email"]),
            full_name=str(name),
            slug=account.get("slug"),
            is_admin=bool(account.get("admin", False)),
            is_confirmed=bool(account.get("confirmed", False)),
        )
