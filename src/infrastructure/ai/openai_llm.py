from __future__ import annotations

import logging
import os
import time
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionAssistantMessageParam
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat import ChatCompletionSystemMessageParam
from openai.types.chat import ChatCompletionUserMessageParam

from src.domain.ports.llm_port import LLMPort
from src.shared.logging_utils import log_event

_MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "6"))
logger = logging.getLogger("agroecology.llm")


class OpenAILLM(LLMPort):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def complete(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> str:
        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt)
        ]

        history = kwargs.get("history") or []
        if history:
            recent = history[-(_MAX_HISTORY_TURNS * 2) :]
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user" and content:
                    messages.append(
                        ChatCompletionUserMessageParam(role="user", content=content)
                    )
                elif role == "assistant" and content:
                    messages.append(
                        ChatCompletionAssistantMessageParam(
                            role="assistant",
                            content=cast(str, content),
                        )
                    )

        messages.append(
            ChatCompletionUserMessageParam(role="user", content=user_prompt)
        )

        started_at = time.perf_counter()
        temperature = kwargs.get("temperature", self._temperature)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)
        history_count = max(0, len(messages) - 2)
        log_event(
            logger,
            logging.INFO,
            "llm_request_started",
            model=self._model,
            history_messages=history_count,
            prompt_chars=len(user_prompt),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            choice = response.choices[0]
            answer = choice.message.content or ""
            finish_reason = choice.finish_reason or "unknown"
            usage = response.usage
            log_event(
                logger,
                logging.INFO,
                "llm_request_completed",
                model=self._model,
                duration_ms=duration_ms,
                answer_chars=len(answer),
                finish_reason=finish_reason,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
            )
            if not answer:
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
            )
            raise
