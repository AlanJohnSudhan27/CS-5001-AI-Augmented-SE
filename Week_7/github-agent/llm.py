"""
LLM Client — supports Groq (cloud) and Ollama (local).

If GROQ_API_KEY is set, uses the Groq API.
Otherwise falls back to the local Ollama instance.

Both clients expose the same interface:
  async chat(messages, tools?) -> dict   (returns message with 'content' and optional 'tool_calls')
  async simple(prompt) -> str            (single-shot, returns text only)
"""
from __future__ import annotations

import httpx

from config import (
    OLLAMA_HOST, OLLAMA_MODEL,
    GROQ_API_KEY, GROQ_MODEL,
    LLM_PROVIDER,
)


# ---------------------------------------------------------------------------
# Ollama (local)
# ---------------------------------------------------------------------------

class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST, model: str = OLLAMA_MODEL) -> None:
        self.host  = host
        self.model = model

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None,
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.host}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]

    async def simple(self, prompt: str) -> str:
        msg = await self.chat([{"role": "user", "content": prompt}])
        return msg.get("content", "")


# ---------------------------------------------------------------------------
# Groq (cloud)
# ---------------------------------------------------------------------------

class GroqClient:
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str = GROQ_API_KEY, model: str = GROQ_MODEL) -> None:
        self.api_key = api_key
        self.model   = model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None,
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
        resp.raise_for_status()
        choice = resp.json()["choices"][0]["message"]
        # Normalise to same shape as Ollama: {content, tool_calls?}
        result: dict = {"content": choice.get("content", "")}
        if choice.get("tool_calls"):
            result["tool_calls"] = [
                {
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"]
                            if isinstance(tc["function"]["arguments"], dict)
                            else __import__("json").loads(tc["function"]["arguments"]),
                    }
                }
                for tc in choice["tool_calls"]
            ]
        return result

    async def simple(self, prompt: str) -> str:
        msg = await self.chat([{"role": "user", "content": prompt}])
        return msg.get("content", "")


# ---------------------------------------------------------------------------
# Factory — returns the right client based on config
# ---------------------------------------------------------------------------

def get_llm_client() -> OllamaClient | GroqClient:
    if LLM_PROVIDER == "groq":
        return GroqClient()
    return OllamaClient()
