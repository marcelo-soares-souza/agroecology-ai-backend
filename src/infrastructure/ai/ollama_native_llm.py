from __future__ import annotations

import logging
import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from src.domain.ports.llm_port import LLMPort
from src.shared.config import (
    LLM_COMPLETION_MAX_TOKENS,
    LLM_CONTEXT_LENGTH,
    LLM_MAX_HISTORY_MESSAGE_CHARS,
    LLM_MAX_HISTORY_TOTAL_CHARS,
    LLM_MAX_HISTORY_TURNS,
    LLM_THINK_ENABLE,
    NO_THINK_PREFIX,
)
from src.shared.logging_utils import (
    log_event,
    perf_fields,
    take_perf_snapshot,
    truncate_for_log,
)

_MAX_COMPLETION_TOKENS = LLM_COMPLETION_MAX_TOKENS
_CTX_LENGTH = LLM_CONTEXT_LENGTH
_MAX_HISTORY_MESSAGE_CHARS = LLM_MAX_HISTORY_MESSAGE_CHARS
_MAX_HISTORY_TOTAL_CHARS = LLM_MAX_HISTORY_TOTAL_CHARS
_MAX_HISTORY_TURNS = LLM_MAX_HISTORY_TURNS
_LLM_THINK_ENABLE = LLM_THINK_ENABLE
_NO_THINK_PREFIX = NO_THINK_PREFIX
logger = logging.getLogger("agroecology.llm")


class OllamaNativeLLM(LLMPort):
    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> None:
        parsed = urlparse(base_url)
        root = f"{parsed.scheme or 'http'}://{parsed.netloc}"
        self._api_url = f"{root}/api/chat"
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = httpx.Client(timeout=httpx.Timeout(300.0))
        self._lock = threading.Lock()

    def close(self) -> None:
        self._client.close()

    def complete(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> str:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        effective_user_prompt = (
            f"{_NO_THINK_PREFIX}{user_prompt}" if not _LLM_THINK_ENABLE else user_prompt
        )

        history = kwargs.get("history") or []
        if history:
            recent = history[-(_MAX_HISTORY_TURNS * 2) :]
            selected_history: list[dict[str, str]] = []
            total_history_chars = 0
            for msg in reversed(recent):
                role = str(msg.get("role", "user"))
                content = str(msg.get("content", "")).strip()
                if not content:
                    continue

                trimmed_content = content[:_MAX_HISTORY_MESSAGE_CHARS].strip()
                if not trimmed_content:
                    continue

                if (
                    selected_history
                    and total_history_chars + len(trimmed_content)
                    > _MAX_HISTORY_TOTAL_CHARS
                ):
                    break

                selected_history.append({"role": role, "content": trimmed_content})
                total_history_chars += len(trimmed_content)

            messages.extend(reversed(selected_history))

        messages.append({"role": "user", "content": effective_user_prompt})

        requested_max_tokens = kwargs.get("max_tokens", self._max_tokens)
        max_tokens = max(1, min(requested_max_tokens, _MAX_COMPLETION_TOKENS))
        temperature = kwargs.get("temperature", self._temperature)
        history_count = max(0, len(messages) - 2)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": _CTX_LENGTH,
                "num_predict": max_tokens,
            },
        }
        if not _LLM_THINK_ENABLE:
            payload["think"] = False
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        log_event(
            logger,
            logging.INFO,
            "llm_request_started",
            model=self._model,
            history_messages=history_count,
            prompt_chars=len(effective_user_prompt),
            temperature=temperature,
            max_tokens=max_tokens,
            transport="ollama_native",
        )

        started_at = time.perf_counter()
        perf_started_at = take_perf_snapshot()
        try:
            with self._lock:
                response = self._client.post(self._api_url, json=payload)
            response.raise_for_status()
            body = response.json()
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            message = body.get("message") or {}
            answer = str(message.get("content") or "")
            finish_reason = str(body.get("done_reason") or "unknown")
            prompt_tokens = body.get("prompt_eval_count")
            completion_tokens = body.get("eval_count")
            log_event(
                logger,
                logging.INFO,
                "llm_request_completed",
                model=self._model,
                duration_ms=duration_ms,
                answer_chars=len(answer),
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                transport="ollama_native",
                **perf_fields(perf_started_at, "llm"),
            )
            if not answer:
                log_event(
                    logger,
                    logging.WARNING,
                    "llm_empty_response_payload",
                    model=self._model,
                    finish_reason=finish_reason,
                    duration_ms=duration_ms,
                    prompt_chars=len(effective_user_prompt),
                    history_messages=history_count,
                    message_payload=truncate_for_log(message),
                    response_payload=truncate_for_log(body),
                    transport="ollama_native",
                )
                logger.warning(
                    "LLM returned empty response: finish_reason=%s model=%s duration_ms=%s",
                    finish_reason,
                    self._model,
                    duration_ms,
                )
            return answer
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                "llm_request_failed",
                model=self._model,
                duration_ms=duration_ms,
                error=exc,
                transport="ollama_native",
                **perf_fields(perf_started_at, "llm"),
            )
            raise
