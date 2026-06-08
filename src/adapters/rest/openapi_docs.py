from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute


APP_DESCRIPTION = """
Agroecology Map AI exposes a RAG API for document management, ingestion,
semantic question answering, and user administration.

## Authentication

Most endpoints require a bearer access token returned by `POST /api/v1/auth/login`.
Send it as:

```http
Authorization: Bearer <access_token>
```

Admin-only endpoints require a user with the `admin` role.

## Main workflow

1. Create an account with `POST /api/v1/auth/register`.
2. Confirm the email with `POST /api/v1/auth/confirm-email`.
3. Login with `POST /api/v1/auth/login`.
4. Upload documents with `POST /api/v1/documents`.
5. Start indexing with `POST /api/v1/ingest`.
6. Ask a question with `POST /api/v1/ask`.
7. Poll the answer with `GET /api/v1/answer/{task_id}`.

## Document ingestion

Only `.pdf`, `.md`, and `.txt` uploads are accepted. Each file must be at most
50 MB. Uploaded documents become searchable after ingestion completes.

## Async answers

Question answering is asynchronous. `POST /api/v1/ask` returns a `task_id`.
Poll `GET /api/v1/answer/{task_id}` until `status` is `done` or `error`.
Tasks expire after the configured task TTL.
"""


TAGS_METADATA = [
    {
        "name": "health",
        "description": "Service health and readiness checks.",
    },
    {
        "name": "auth",
        "description": "Registration, login, token refresh, logout, and profile lookup.",
    },
    {
        "name": "rag",
        "description": "Question answering, answer polling, and RAG runtime status.",
    },
    {
        "name": "ingestion",
        "description": "Document indexing jobs and ingestion history.",
    },
    {
        "name": "documents",
        "description": "Upload, list, update, view, download, and delete source documents.",
    },
    {
        "name": "admin",
        "description": "Admin-only user management endpoints.",
    },
    {
        "name": "suggestions",
        "description": "Document suggestion workflow: users propose documents, admins review and approve them.",
    },
]


ENDPOINT_DOCS: dict[tuple[str, str], dict[str, object]] = {
    ("GET", "/api/v1/health"): {
        "tags": ["health"],
        "summary": "Check API health",
        "description": """
Returns a minimal health response when the API process is reachable.

Use this endpoint for load balancers, uptime checks, and deployment smoke tests.
It does not require authentication.
""",
    },
    ("GET", "/api/v1/auth/human-challenge"): {
        "summary": "Create a human challenge",
        "description": """
Creates a simple anti-abuse challenge used by registration.

Pass the optional `locale` query parameter, for example `pt-BR` or `en`.
Use the returned `challenge_id` and answer in `POST /api/v1/auth/register`.
""",
    },
    ("POST", "/api/v1/auth/register"): {
        "summary": "Register a user",
        "description": """
Creates a new user account and sends an email confirmation link.

First call `GET /api/v1/auth/human-challenge`, then submit the challenge answer
with the user's name, email, password, and locale. The account cannot login until
the email confirmation endpoint succeeds.
""",
    },
    ("POST", "/api/v1/auth/confirm-email/resend"): {
        "summary": "Resend confirmation email",
        "description": """
Sends a new email confirmation token to a registered but unconfirmed user.

Provide the email as the `email` query parameter.
""",
    },
    ("POST", "/api/v1/auth/confirm-email"): {
        "summary": "Confirm email",
        "description": """
Confirms a registered user's email address.

Submit the raw confirmation token received by email. After confirmation, the
user can authenticate with `POST /api/v1/auth/login`.
""",
    },
    ("POST", "/api/v1/auth/login"): {
        "summary": "Login",
        "description": """
Authenticates an active, email-confirmed user.

The response contains an `access_token` for authenticated API calls and a
`refresh_token` for issuing a new token pair.
""",
    },
    ("POST", "/api/v1/auth/refresh"): {
        "summary": "Refresh tokens",
        "description": """
Rotates a refresh token and returns a new access token and refresh token.

Provide the current refresh token as the `refresh_token` query parameter. The old
refresh token is revoked when the new pair is issued.
""",
    },
    ("POST", "/api/v1/auth/logout"): {
        "summary": "Logout",
        "description": """
Revokes all refresh tokens for the authenticated user.

Send the access token in the `Authorization` header. Existing access tokens may
remain valid until their normal expiration, but refresh is disabled.
""",
    },
    ("POST", "/api/v1/auth/password-reset/request"): {
        "summary": "Request password reset",
        "description": """
Starts a password reset flow for an email address.

Provide the email as the `email` query parameter. The endpoint returns the same
message whether or not the email exists.
""",
    },
    ("POST", "/api/v1/auth/password-reset/confirm"): {
        "summary": "Confirm password reset",
        "description": """
Sets a new password using a valid reset token.

Provide `token` and `new_password` as query parameters. The new password must
have at least 8 characters.
""",
    },
    ("GET", "/api/v1/auth/me"): {
        "summary": "Get current user",
        "description": """
Returns the authenticated user's profile and role list.

Send the access token in the `Authorization` header.
""",
    },
    ("GET", "/api/v1/auth/users/by-slug/{slug}"): {
        "summary": "Find user by slug",
        "description": """
Returns a public user profile by slug. If no slug match exists, the endpoint also
tries the same value as a user id.
""",
    },
    ("POST", "/api/v1/ask"): {
        "tags": ["rag"],
        "summary": "Ask a question",
        "description": """
Starts an asynchronous RAG question-answering task.

Send `question`, optional `top_k`, and optional chat `history`. The response
contains a `task_id`. Poll `GET /api/v1/answer/{task_id}` until the answer is
ready. Requires authentication.
""",
    },
    ("GET", "/api/v1/answer/{task_id}"): {
        "tags": ["rag"],
        "summary": "Get an answer task",
        "description": """
Returns the current state of a question-answering task.

When `status` is `processing`, poll again later. When `status` is `done`, read
`answer` and `sources`. When `status` is `error`, inspect `error`.
""",
    },
    ("GET", "/api/v1/status"): {
        "tags": ["rag"],
        "summary": "Get RAG status",
        "description": """
Returns index readiness, ingestion status, cache metrics, model configuration,
retrieval limits, and document counts.

Use this endpoint before asking questions to confirm that the index is ready.
Requires authentication.
""",
    },
    ("POST", "/api/v1/ingest"): {
        "tags": ["ingestion"],
        "summary": "Start ingestion",
        "description": """
Starts indexing uploaded documents into the vector store.

Set `force=true` to rebuild the index even when documents already appear
indexed. Only one ingestion can run at a time. Requires the `admin` role.
""",
    },
    ("GET", "/api/v1/ingest/status"): {
        "tags": ["ingestion"],
        "summary": "Get current ingestion status",
        "description": """
Returns the active ingestion state, indexed chunk count, current run id, and any
last ingestion error. Requires authentication.
""",
    },
    ("GET", "/api/v1/ingestion/runs"): {
        "tags": ["ingestion"],
        "summary": "List ingestion runs",
        "description": """
Returns all recorded ingestion runs, including status, chunk count, start time,
finish time, and error text when present. Requires authentication.
""",
    },
    ("GET", "/api/v1/ingestion/runs/{run_id}"): {
        "tags": ["ingestion"],
        "summary": "Get ingestion run",
        "description": """
Returns one ingestion run by id. Use this after `GET /api/v1/ingestion/runs` or
from the run id returned by ingestion status. Requires authentication.
""",
    },
    ("POST", "/api/v1/documents"): {
        "tags": ["documents"],
        "summary": "Upload documents",
        "description": """
Uploads one or more source documents as multipart form data.

Use the `files` field for `.pdf`, `.md`, or `.txt` files. Optional form fields
`title`, `authors`, and `url` are applied to uploaded records. Duplicate,
empty, unsupported, or over-50-MB files are returned in `skipped`. Requires the
`admin` role.
""",
    },
    ("GET", "/api/v1/documents"): {
        "tags": ["documents"],
        "summary": "List documents",
        "description": """
Returns all uploaded document records and their ingestion flags.

Use this endpoint to find document ids for update, download, deletion, or manual
metadata extraction.
""",
    },
    ("GET", "/api/v1/documents/metadata-status"): {
        "tags": ["documents"],
        "summary": "Get metadata extraction queue status",
        "description": """
Returns pending, running, and active counts for queued PDF metadata extraction
jobs. Requires the `admin` role.
""",
    },
    ("GET", "/api/v1/documents/{doc_id}"): {
        "tags": ["documents"],
        "summary": "Get document",
        "description": """
Returns a single document record by UUIDv7 id.

Use `GET /api/v1/documents` to discover available ids.
""",
    },
    ("PUT", "/api/v1/documents/{doc_id}"): {
        "tags": ["documents"],
        "summary": "Update document metadata",
        "description": """
Updates editable document metadata: `title`, `authors`, and `url`.

Send only the fields that should change. Requires the `admin` role.
""",
    },
    ("POST", "/api/v1/documents/{doc_id}/extract-metadata"): {
        "tags": ["documents"],
        "summary": "Extract document metadata",
        "description": """
Extracts title and author metadata from a single PDF and stores missing fields.

This endpoint only supports PDF documents and requires the `admin` role.
""",
    },
    ("GET", "/api/v1/documents/{doc_id}/view"): {
        "tags": ["documents"],
        "summary": "View document file",
        "description": """
Returns the stored file inline for browser viewing.

The response is a file response, not JSON. Use this endpoint from browser UI
links or embedded PDF viewers.
""",
    },
    ("GET", "/api/v1/documents/{doc_id}/download"): {
        "tags": ["documents"],
        "summary": "Download document file",
        "description": """
Returns the stored file as a file response.

Use this endpoint when a client needs the original uploaded document bytes.
""",
    },
    ("POST", "/api/v1/documents/extract-all-metadata"): {
        "tags": ["documents"],
        "summary": "Queue metadata extraction for all PDFs",
        "description": """
Queues metadata extraction jobs for PDF documents that are missing title or
authors. Requires the `admin` role.
""",
    },
    ("DELETE", "/api/v1/documents/{doc_id}"): {
        "tags": ["documents"],
        "summary": "Delete document",
        "description": """
Deletes a document record, removes its stored file, and removes its indexed
chunks. Requires the `admin` role.
""",
    },
    ("GET", "/api/v1/admin/users"): {
        "summary": "List users",
        "description": """
Returns all registered users. Requires the `admin` role.
""",
    },
    ("GET", "/api/v1/admin/users/{user_id}"): {
        "summary": "Get user",
        "description": """
Returns one user by UUIDv7 id. Requires the `admin` role.
""",
    },
    ("PUT", "/api/v1/admin/users/{user_id}"): {
        "summary": "Update user",
        "description": """
Updates user profile fields, account status, locale, or role.

Use `role_key` with `admin` or `user` to replace the user's role assignment.
Requires the `admin` role.
""",
    },
    ("DELETE", "/api/v1/admin/users/{user_id}"): {
        "summary": "Delete user",
        "description": """
Deletes a user account by id. Requires the `admin` role.
""",
    },
}


def apply_openapi_docs(app: FastAPI) -> None:
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            docs = ENDPOINT_DOCS.get((method, route.path))
            if docs is None:
                continue
            route.summary = str(docs["summary"])
            route.description = str(docs["description"]).strip()
            if "tags" in docs:
                route.tags = list(docs["tags"])  # type: ignore[call-overload]
