from __future__ import annotations

from typing import Any

import httpx

from src.domain.dto.orcid_identity import OrcidIdentity


class OrcidOAuthError(Exception):
    pass


class OrcidOAuthClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        token_url: str,
        userinfo_url: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._token_url = token_url
        self._userinfo_url = userinfo_url
        self._timeout_seconds = timeout_seconds

    async def exchange_code(self, code: str) -> OrcidIdentity:
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            token_response = await client.post(
                self._token_url,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            if token_response.status_code >= 400:
                raise OrcidOAuthError("ORCID token exchange failed")

            token_payload = token_response.json()
            access_token = str(token_payload.get("access_token") or "")
            identity = self._identity_from_token_payload(token_payload)

            if access_token:
                userinfo = await self._fetch_userinfo(client, access_token)
                identity = self._merge_identity(identity, userinfo)

            if not identity.orcid_id:
                raise OrcidOAuthError("ORCID iD missing from token response")

            return identity

    async def _fetch_userinfo(
        self, client: httpx.AsyncClient, access_token: str
    ) -> dict[str, Any]:
        response = await client.get(
            self._userinfo_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
        )
        if response.status_code >= 400:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _identity_from_token_payload(payload: dict[str, Any]) -> OrcidIdentity:
        orcid_id = str(
            payload.get("orcid") or payload.get("orcid_id") or payload.get("sub") or ""
        ).strip()
        if not orcid_id:
            identifier = payload.get("orcid-identifier")
            if isinstance(identifier, dict):
                orcid_id = str(identifier.get("path") or "").strip()

        name = str(payload.get("name") or "").strip() or None
        email = str(payload.get("email") or "").strip().lower() or None
        return OrcidIdentity(orcid_id=orcid_id, name=name, email=email)

    @staticmethod
    def _merge_identity(
        identity: OrcidIdentity, userinfo: dict[str, Any]
    ) -> OrcidIdentity:
        orcid_id = str(
            userinfo.get("sub")
            or userinfo.get("orcid")
            or userinfo.get("orcid_id")
            or identity.orcid_id
        ).strip()
        name = str(userinfo.get("name") or identity.name or "").strip() or None
        email = (
            str(userinfo.get("email") or identity.email or "").strip().lower() or None
        )
        return OrcidIdentity(orcid_id=orcid_id, name=name, email=email)
