from __future__ import annotations

import logging
import time
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

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

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _build_extra_body() -> dict[str, object]:
        body: dict[str, object] = {"num_ctx": _CTX_LENGTH}
        if not _LLM_THINK_ENABLE:
            body["enable_thinking"] = False
            body["think"] = False
            body["chat_template_kwargs"] = {"enable_thinking": False}
        return body

    def complete(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> str:
        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt)
        ]
        effective_user_prompt = (
            f"{_NO_THINK_PREFIX}{user_prompt}" if not _LLM_THINK_ENABLE else user_prompt
        )

        history = kwargs.get("history") or []
        if history:
            recent = history[-(_MAX_HISTORY_TURNS * 2) :]
            selected_history: list[dict[str, str]] = []
            total_history_chars = 0
            for msg in reversed(recent):
                role = msg.get("role", "user")
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

            for msg in reversed(selected_history):
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    messages.append(
                        ChatCompletionUserMessageParam(role="user", content=content)
                    )
                elif role == "assistant":
                    messages.append(
                        ChatCompletionAssistantMessageParam(
                            role="assistant",
                            content=cast(str, content),
                        )
                    )

        messages.append(
            ChatCompletionUserMessageParam(role="user", content=effective_user_prompt)
        )

        started_at = time.perf_counter()
        perf_started_at = take_perf_snapshot()
        temperature = kwargs.get("temperature", self._temperature)
        requested_max_tokens = kwargs.get("max_tokens", self._max_tokens)
        if _LLM_THINK_ENABLE:
            max_tokens = max(requested_max_tokens, min(_CTX_LENGTH // 2, 4096))
        else:
            max_tokens = max(1, min(requested_max_tokens, _MAX_COMPLETION_TOKENS))
        history_count = max(0, len(messages) - 2)
        log_event(
            logger,
            logging.INFO,
            "llm_request_started",
            model=self._model,
            history_messages=history_count,
            prompt_chars=len(effective_user_prompt),
            prompt_preview=truncate_for_log(effective_user_prompt, 1200),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=self._build_extra_body(),
            )
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            choice = response.choices[0]
            answer = choice.message.content or ""
            if not answer and _LLM_THINK_ENABLE:
                reasoning = getattr(choice.message, "reasoning_content", "") or ""
                if reasoning:
                    import re

                    cleaned = re.sub(r"<\s*/?\s*think\s*>", "", reasoning)
                    if cleaned.strip():
                        answer = cleaned.strip()
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
                **perf_fields(perf_started_at, "llm"),
            )
            if not answer:
                message_payload = (
                    choice.message.model_dump(exclude_none=False)
                    if hasattr(choice.message, "model_dump")
                    else str(choice.message)
                )
                choice_payload = (
                    choice.model_dump(exclude_none=False)
                    if hasattr(choice, "model_dump")
                    else str(choice)
                )
                response_payload = (
                    response.model_dump(exclude_none=False)
                    if hasattr(response, "model_dump")
                    else str(response)
                )
                log_event(
                    logger,
                    logging.WARNING,
                    "llm_empty_response_payload",
                    model=self._model,
                    finish_reason=finish_reason,
                    duration_ms=duration_ms,
                    prompt_chars=len(effective_user_prompt),
                    history_messages=history_count,
                    choice_index=getattr(choice, "index", 0),
                    message_payload=truncate_for_log(message_payload),
                    choice_payload=truncate_for_log(choice_payload),
                    response_payload=truncate_for_log(response_payload),
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
                **perf_fields(perf_started_at, "llm"),
            )
            raise
