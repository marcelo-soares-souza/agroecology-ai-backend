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
_CTX_LENGTH = int(os.getenv("LLM_CONTEXT_LENGTH", "4096"))
_MAX_HISTORY_MESSAGE_CHARS = int(os.getenv("MAX_HISTORY_MESSAGE_CHARS", "1000"))
_MAX_HISTORY_TOTAL_CHARS = int(os.getenv("MAX_HISTORY_TOTAL_CHARS", "4000"))
_MAX_COMPLETION_TOKENS = int(os.getenv("LLM_COMPLETION_MAX_TOKENS", "768"))
_LLM_THINK_ENABLE = os.getenv("LLM_THINK_ENABLE", "true").lower() not in (
    "0",
    "false",
    "no",
)
_NO_THINK_PREFIX = (
    "/no_think\n"
    "Return only the final answer in message.content. "
    "Do not include reasoning, analysis, thinking steps, or scratchpad output.\n\n"
)
logger = logging.getLogger("agroecology.llm")


def _truncate_for_log(value: Any, limit: int = 3000) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated {len(text) - limit} chars>"


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
            prompt_preview=_truncate_for_log(effective_user_prompt, 1200),
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
                    message_payload=_truncate_for_log(message_payload),
                    choice_payload=_truncate_for_log(choice_payload),
                    response_payload=_truncate_for_log(response_payload),
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
            )
            raise
