from __future__ import annotations

import asyncio
import logging

from src.application.ask_question import AskQuestion
from src.application.manage_documents import ManageDocuments
from src.bootstrap.task_manager import TaskManager
from src.domain.dto.answer_result import TaskSubmissionResult
from src.domain.dto.document_metadata import DocumentMetadataMap
from src.domain.ports.cache_port import CachePort
from src.shared.logging_utils import log_event, perf_fields, take_perf_snapshot

logger = logging.getLogger("agroecology.bootstrap")


class AskTaskService:
    def __init__(
        self,
        ask_question: AskQuestion,
        task_manager: TaskManager,
        cache: CachePort,
        manage_documents: ManageDocuments,
    ) -> None:
        self._ask_question = ask_question
        self._task_manager = task_manager
        self._cache = cache
        self._manage_documents = manage_documents

    async def submit(
        self,
        question: str,
        top_k: int,
        history: list[dict],
    ) -> TaskSubmissionResult:
        should_use_cache = not history
        cached = self._cache.get(question, top_k) if should_use_cache else None

        task_id = self._task_manager.create(question, top_k)
        if cached:
            self._task_manager.update(
                task_id,
                status="done",
                answer=cached.answer,
                sources=cached.to_source_dicts(),
            )
            log_event(
                logger,
                logging.INFO,
                "ask_completed_from_cache",
                task_id=task_id,
                top_k=top_k,
                history_messages=len(history),
            )
            return TaskSubmissionResult(task_id=task_id, status="done")

        log_event(
            logger,
            logging.INFO,
            "ask_task_created",
            task_id=task_id,
            top_k=top_k,
            history_messages=len(history),
        )

        document_metadata_map = await self._manage_documents.get_metadata_map()
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            None,
            self._process_task,
            task_id,
            question,
            top_k,
            document_metadata_map,
            history,
            should_use_cache,
        )
        return TaskSubmissionResult(task_id=task_id, status="processing")

    def _process_task(
        self,
        task_id: str,
        question: str,
        top_k: int,
        document_metadata_map: DocumentMetadataMap,
        history: list[dict],
        should_cache: bool,
    ) -> None:
        started_at = take_perf_snapshot()
        try:
            result = self._ask_question.execute(
                question,
                top_k,
                document_metadata_map,
                history=history,
            )
            self._task_manager.update(
                task_id,
                status="done",
                answer=result.answer,
                sources=result.to_source_dicts(),
            )
            if should_cache and result.answer.strip():
                self._cache.set(question, result, top_k)
            log_event(
                logger,
                logging.INFO,
                "ask_task_completed",
                task_id=task_id,
                retrieved_sources=len(result.sources),
                answer_chars=len(result.answer),
                cached=should_cache,
                **perf_fields(started_at, "task"),
            )
        except Exception as exc:
            self._task_manager.update(task_id, status="error", error=str(exc))
            log_event(
                logger,
                logging.ERROR,
                "ask_task_failed",
                task_id=task_id,
                error=exc,
                **perf_fields(started_at, "task"),
            )
