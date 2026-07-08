from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.domain.dto.chat_message import ChatMessage
from src.domain.models.chat_conversation import (
    ChatConversationDetail,
    ChatConversationMessage,
    ChatConversationSummary,
)
from src.domain.ports.chat_conversation_repository import (
    ChatConversationLimitError,
    ChatConversationRepository,
)
from src.shared.config import CHAT_MAX_CONVERSATIONS_PER_USER, utcnow
from src.shared.uuid7 import uuid7

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresChatConversationRepository(ChatConversationRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_for_user(
        self, user_id: str, limit: int, offset: int
    ) -> tuple[list[ChatConversationSummary], int]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT COUNT(*)::int AS total
                    FROM chat_conversations
                    WHERE user_id = %s AND deleted_at IS NULL
                    """,
                    (user_id,),
                )
                total_row = await cur.fetchone()
                total = int(total_row["total"]) if total_row else 0

                await cur.execute(
                    """
                    SELECT
                        c.*,
                        COUNT(m.id)::int AS message_count,
                        (
                            SELECT m2.content
                            FROM chat_messages m2
                            WHERE m2.conversation_id = c.id
                              AND m2.status = 'done'
                            ORDER BY m2.created_at DESC
                            LIMIT 1
                        ) AS last_message_preview
                    FROM chat_conversations c
                    LEFT JOIN chat_messages m ON m.conversation_id = c.id
                    WHERE c.user_id = %s AND c.deleted_at IS NULL
                    GROUP BY c.id
                    ORDER BY c.last_message_at DESC, c.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, limit, offset),
                )
                rows = await cur.fetchall()

        return [self._to_summary(dict(row)) for row in rows], total

    async def get_for_user(
        self, conversation_id: str, user_id: str
    ) -> ChatConversationDetail | None:
        async with self._pool.connection() as conn:
            summary = await self._get_summary_on_connection(conn, conversation_id, user_id)
            if summary is None:
                return None

            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM chat_messages
                    WHERE conversation_id = %s AND user_id = %s
                    ORDER BY created_at ASC
                    """,
                    (conversation_id, user_id),
                )
                rows = await cur.fetchall()

        return ChatConversationDetail(
            conversation=summary,
            messages=[self._to_message(dict(row)) for row in rows],
        )

    async def get_summary_for_user(
        self, conversation_id: str, user_id: str
    ) -> ChatConversationSummary | None:
        async with self._pool.connection() as conn:
            return await self._get_summary_on_connection(conn, conversation_id, user_id)

    async def create(self, user_id: str, title: str) -> ChatConversationSummary:
        now = utcnow()
        conversation_id = uuid7()
        clean_title = self._normalize_title(title)
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT pg_advisory_xact_lock(1701, hashtext(%s))",
                    (user_id,),
                )
                await cur.execute(
                    """
                    SELECT COUNT(*)::int AS total
                    FROM chat_conversations
                    WHERE user_id = %s AND deleted_at IS NULL
                    """,
                    (user_id,),
                )
                total_row = await cur.fetchone()
                total = int(total_row["total"]) if total_row else 0
                if total >= CHAT_MAX_CONVERSATIONS_PER_USER:
                    raise ChatConversationLimitError(CHAT_MAX_CONVERSATIONS_PER_USER)

                await cur.execute(
                    """
                    INSERT INTO chat_conversations (
                        id, user_id, title, status, created_at, updated_at,
                        last_message_at
                    )
                    VALUES (%s, %s, %s, 'active', %s, %s, %s)
                    RETURNING *
                    """,
                    (conversation_id, user_id, clean_title, now, now, now),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_summary(dict(row))

    async def rename(
        self, conversation_id: str, user_id: str, title: str
    ) -> ChatConversationSummary | None:
        now = utcnow()
        clean_title = self._normalize_title(title)
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE chat_conversations
                    SET title = %s, updated_at = %s
                    WHERE id = %s AND user_id = %s AND deleted_at IS NULL
                    RETURNING *
                    """,
                    (clean_title, now, conversation_id, user_id),
                )
                row = await cur.fetchone()
                return self._to_summary(dict(row)) if row else None

    async def delete(self, conversation_id: str, user_id: str) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    DELETE FROM chat_conversations
                    WHERE id = %s AND user_id = %s
                    """,
                    (conversation_id, user_id),
                )
                return cur.rowcount > 0

    async def append_user_message(
        self, conversation_id: str, user_id: str, content: str
    ) -> ChatConversationMessage:
        return await self._append_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=content,
            status="done",
            task_id=None,
        )

    async def append_assistant_placeholder(
        self, conversation_id: str, user_id: str, task_id: str
    ) -> ChatConversationMessage:
        return await self._append_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content="",
            status="thinking",
            task_id=task_id,
        )

    async def complete_assistant_message(
        self,
        message_id: str,
        user_id: str,
        content: str,
        sources: list[dict],
        duration_ms: int,
    ) -> ChatConversationMessage | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE chat_messages m
                    SET content = %s,
                        sources = %s,
                        status = 'done',
                        error = NULL,
                        duration_ms = %s
                    FROM chat_conversations c
                    WHERE m.id = %s
                      AND m.user_id = %s
                      AND m.conversation_id = c.id
                      AND c.deleted_at IS NULL
                    RETURNING m.*
                    """,
                    (content, Jsonb(sources), duration_ms, message_id, user_id),
                )
                row = await cur.fetchone()
                if row is None:
                    return None
                message = self._to_message(dict(row))
                await self._touch_conversation_on_connection(
                    cur, message.conversation_id, user_id, now
                )
                return message

    async def fail_assistant_message(
        self, message_id: str, user_id: str, error: str
    ) -> ChatConversationMessage | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE chat_messages m
                    SET status = 'error', error = %s
                    FROM chat_conversations c
                    WHERE m.id = %s
                      AND m.user_id = %s
                      AND m.conversation_id = c.id
                      AND c.deleted_at IS NULL
                    RETURNING m.*
                    """,
                    (error, message_id, user_id),
                )
                row = await cur.fetchone()
                if row is None:
                    return None
                message = self._to_message(dict(row))
                await self._touch_conversation_on_connection(
                    cur, message.conversation_id, user_id, now
                )
                return message

    async def get_recent_history(
        self,
        conversation_id: str,
        user_id: str,
        max_messages: int,
        max_message_chars: int,
        max_total_chars: int,
    ) -> list[ChatMessage]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT m.role, m.content
                    FROM chat_messages m
                    JOIN chat_conversations c ON c.id = m.conversation_id
                    WHERE m.conversation_id = %s
                      AND m.user_id = %s
                      AND m.status = 'done'
                      AND m.content <> ''
                      AND c.deleted_at IS NULL
                    ORDER BY m.created_at DESC
                    LIMIT %s
                    """,
                    (conversation_id, user_id, max_messages),
                )
                rows = await cur.fetchall()

        selected: list[ChatMessage] = []
        total_chars = 0
        for row in rows:
            role = str(row["role"]).strip()
            content = str(row["content"]).strip()[:max_message_chars].strip()
            if not role or not content:
                continue
            if selected and total_chars + len(content) > max_total_chars:
                break
            selected.append(ChatMessage(role=role, content=content))
            total_chars += len(content)
        return list(reversed(selected))

    async def delete_for_user(self, user_id: str) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM chat_conversations WHERE user_id = %s",
                    (user_id,),
                )

    async def _append_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        status: str,
        task_id: str | None,
    ) -> ChatConversationMessage:
        now = utcnow()
        message_id = uuid7()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO chat_messages (
                        id, conversation_id, user_id, role, content, status,
                        task_id, created_at
                    )
                    SELECT %s, c.id, %s, %s, %s, %s, %s, %s
                    FROM chat_conversations c
                    WHERE c.id = %s AND c.user_id = %s AND c.deleted_at IS NULL
                    RETURNING *
                    """,
                    (
                        message_id,
                        user_id,
                        role,
                        content,
                        status,
                        task_id,
                        now,
                        conversation_id,
                        user_id,
                    ),
                )
                row = await cur.fetchone()
                if row is None:
                    raise ValueError("Conversation not found")
                if role == "user":
                    await self._touch_conversation_on_connection(
                        cur, conversation_id, user_id, now
                    )
                return self._to_message(dict(row))

    async def _get_summary_on_connection(
        self, conn: Any, conversation_id: str, user_id: str
    ) -> ChatConversationSummary | None:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    c.*,
                    COUNT(m.id)::int AS message_count,
                    (
                        SELECT m2.content
                        FROM chat_messages m2
                        WHERE m2.conversation_id = c.id
                          AND m2.status = 'done'
                        ORDER BY m2.created_at DESC
                        LIMIT 1
                    ) AS last_message_preview
                FROM chat_conversations c
                LEFT JOIN chat_messages m ON m.conversation_id = c.id
                WHERE c.id = %s AND c.user_id = %s AND c.deleted_at IS NULL
                GROUP BY c.id
                """,
                (conversation_id, user_id),
            )
            row = await cur.fetchone()
            return self._to_summary(dict(row)) if row else None

    @staticmethod
    async def _touch_conversation_on_connection(
        cur: Any, conversation_id: str, user_id: str, when
    ) -> None:
        await cur.execute(
            """
            UPDATE chat_conversations
            SET updated_at = %s, last_message_at = %s
            WHERE id = %s AND user_id = %s AND deleted_at IS NULL
            """,
            (when, when, conversation_id, user_id),
        )

    @staticmethod
    def _normalize_title(title: str) -> str:
        clean = " ".join(title.strip().split())
        if not clean:
            return "New chat"
        if len(clean) <= 80:
            return clean
        return clean[:77].rstrip() + "..."

    @staticmethod
    def _to_summary(row: dict[str, Any]) -> ChatConversationSummary:
        preview = row.get("last_message_preview")
        if isinstance(preview, str) and len(preview) > 160:
            preview = preview[:157].rstrip() + "..."
        return ChatConversationSummary(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_message_at=row["last_message_at"],
            deleted_at=row.get("deleted_at"),
            message_count=int(row.get("message_count") or 0),
            last_message_preview=preview,
        )

    @staticmethod
    def _to_message(row: dict[str, Any]) -> ChatConversationMessage:
        sources = row.get("sources")
        return ChatConversationMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            role=row["role"],
            content=row["content"],
            status=row["status"],
            task_id=row.get("task_id"),
            sources=list(sources) if isinstance(sources, list) else None,
            error=row.get("error"),
            duration_ms=row.get("duration_ms"),
            created_at=row["created_at"],
        )
