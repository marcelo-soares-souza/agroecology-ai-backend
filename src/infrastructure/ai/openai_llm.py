from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from src.domain.ports.llm_port import LLMPort

_MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "6"))


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
        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        history = kwargs.get("history") or []
        if history:
            recent = history[-(_MAX_HISTORY_TURNS * 2) :]
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
        )
        return response.choices[0].message.content or ""
