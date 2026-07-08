from __future__ import annotations

import asyncio
import logging
from functools import partial

from src.application.ask_question import AskQuestion
from src.application.manage_documents import ManageDocuments
from src.bootstrap.task_manager import TaskManager
from src.domain.dto.answer_result import TaskSubmissionResult
from src.domain.dto.chat_message import ChatMessage
from src.domain.dto.document_metadata import DocumentMetadataMap
from src.domain.ports.cache_port import CachePort
from src.domain.ports.chat_conversation_repository import ChatConversationRepository
from src.shared.config import (
    LLM_MAX_HISTORY_MESSAGE_CHARS,
    LLM_MAX_HISTORY_TOTAL_CHARS,
    LLM_MAX_HISTORY_TURNS,
)
from src.shared.logging_utils import log_event, perf_fields, take_perf_snapshot

logger = logging.getLogger("agroecology.bootstrap")


class AskTaskService:
    def __init__(
        self,
        ask_question: AskQuestion,
        task_manager: TaskManager,
        cache: CachePort,
        manage_documents: ManageDocuments,
        chat_repo: ChatConversationRepository | None = None,
    ) -> None:
        self._ask_question = ask_question
        self._task_manager = task_manager
        self._cache = cache
        self._manage_documents = manage_documents
        self._chat_repo = chat_repo

    async def submit(
        self,
        question: str,
        top_k: int,
        history: list[ChatMessage],
        locale: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> TaskSubmissionResult:
        chat_repo = self._chat_repo
        task_conversation_id: str | None = None
        user_message_id: str | None = None
        assistant_message_id: str | None = None
        answer_history = history

        if user_id is not None and chat_repo is not None:
            if conversation_id:
                conversation = await chat_repo.get_summary_for_user(
                    conversation_id,
                    user_id,
                )
                if conversation is None:
                    raise ValueError("Conversation not found")
            else:
                conversation = await chat_repo.create(
                    user_id,
                    self._title_from_question(question),
                )
            task_conversation_id = conversation.id
            if conversation_id:
                answer_history = await chat_repo.get_recent_history(
                    conversation_id=task_conversation_id,
                    user_id=user_id,
                    max_messages=LLM_MAX_HISTORY_TURNS * 2,
                    max_message_chars=LLM_MAX_HISTORY_MESSAGE_CHARS,
                    max_total_chars=LLM_MAX_HISTORY_TOTAL_CHARS,
                )

        should_use_cache = not answer_history
        cache_question = self._cache_question_key(question, locale)
        cached = self._cache.get(cache_question, top_k) if should_use_cache else None

        task_id = self._task_manager.create(
            question,
            top_k,
            conversation_id=task_conversation_id,
        )

        if user_id is not None and task_conversation_id and chat_repo is not None:
            user_message = await chat_repo.append_user_message(
                task_conversation_id,
                user_id,
                question,
            )
            assistant_message = await chat_repo.append_assistant_placeholder(
                task_conversation_id,
                user_id,
                task_id,
            )
            user_message_id = user_message.id
            assistant_message_id = assistant_message.id
            self._task_manager.update(
                task_id,
                status="processing",
                conversation_id=task_conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )

        if cached:
            cached_sources = cached.to_source_dicts()
            if user_id is not None and assistant_message_id and chat_repo is not None:
                await chat_repo.complete_assistant_message(
                    assistant_message_id,
                    user_id,
                    cached.answer,
                    cached_sources,
                    0,
                )
            self._task_manager.update(
                task_id,
                status="done",
                answer=cached.answer,
                sources=cached_sources,
                conversation_id=task_conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
            log_event(
                logger,
                logging.INFO,
                "ask_completed_from_cache",
                task_id=task_id,
                top_k=top_k,
                history_messages=len(answer_history),
                locale=locale,
                conversation_id=task_conversation_id,
            )
            return TaskSubmissionResult(
                task_id=task_id,
                status="done",
                conversation_id=task_conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )

        log_event(
            logger,
            logging.INFO,
            "ask_task_created",
            task_id=task_id,
            top_k=top_k,
            history_messages=len(answer_history),
            locale=locale,
            conversation_id=task_conversation_id,
        )

        document_metadata_map = await self._manage_documents.get_metadata_map()
        asyncio.create_task(
            self._process_task_async(
                task_id=task_id,
                question=question,
                top_k=top_k,
                document_metadata_map=document_metadata_map,
                history=answer_history,
                should_cache=should_use_cache,
                locale=locale,
                cache_question=cache_question,
                user_id=user_id,
                conversation_id=task_conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
        )
        return TaskSubmissionResult(
            task_id=task_id,
            status="processing",
            conversation_id=task_conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
        )

    async def _process_task_async(
        self,
        *,
        task_id: str,
        question: str,
        top_k: int,
        document_metadata_map: DocumentMetadataMap,
        history: list[ChatMessage],
        should_cache: bool,
        locale: str | None,
        cache_question: str,
        user_id: str | None,
        conversation_id: str | None,
        user_message_id: str | None,
        assistant_message_id: str | None,
    ) -> None:
        started_at = take_perf_snapshot()
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                partial(
                    self._ask_question.execute,
                    question,
                    top_k,
                    document_metadata_map,
                    history=history,
                    locale=locale,
                ),
            )
            sources = result.to_source_dicts()
            task_metrics = perf_fields(started_at, "task")
            duration_ms = int(task_metrics.get("task_wall_ms") or 0)
            if (
                user_id is not None
                and assistant_message_id
                and self._chat_repo is not None
            ):
                await self._chat_repo.complete_assistant_message(
                    assistant_message_id,
                    user_id,
                    result.answer,
                    sources,
                    duration_ms,
                )
            self._task_manager.update(
                task_id,
                status="done",
                answer=result.answer,
                sources=sources,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
            if should_cache and result.answer.strip():
                self._cache.set(cache_question, result, top_k)
            log_event(
                logger,
                logging.INFO,
                "ask_task_completed",
                task_id=task_id,
                retrieved_sources=len(result.sources),
                answer_chars=len(result.answer),
                cached=should_cache,
                locale=locale,
                conversation_id=conversation_id,
                **task_metrics,
            )
        except Exception as exc:
            if (
                user_id is not None
                and assistant_message_id
                and self._chat_repo is not None
            ):
                await self._chat_repo.fail_assistant_message(
                    assistant_message_id,
                    user_id,
                    str(exc),
                )
            self._task_manager.update(
                task_id,
                status="error",
                error=str(exc),
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
            log_event(
                logger,
                logging.ERROR,
                "ask_task_failed",
                task_id=task_id,
                error=exc,
                conversation_id=conversation_id,
                **perf_fields(started_at, "task"),
            )

    @staticmethod
    def _cache_question_key(question: str, locale: str | None) -> str:
        normalized_locale = (locale or "").strip().lower()
        if not normalized_locale:
            return question
        return f"{question}\n\n[answer_locale={normalized_locale}]"

    @staticmethod
    def _title_from_question(question: str) -> str:
        title = " ".join(question.strip().split())
        if not title:
            return "New chat"
        if len(title) <= 80:
            return title
        return title[:77].rstrip() + "..."
