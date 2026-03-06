"""
BaseAgent — shared Ollama chat interface for all Code Review Orchestra agents.

Architecture difference from an Anthropic tool-use agent:
  llama3.2:3b is not reliable for autonomous tool calling, so the pattern is:
    1. Python gathers all file context by calling tool functions directly
    2. All context is baked into a single, comprehensive prompt
    3. One LLM call with format="json" returns structured output
    4. BaseAgent parses the JSON and returns it to the subclass

The emit callback (optional) is called with (agent_name, message) for every
log event — used by the CLI (Rich) and the web UI (SSE).
"""
import json
import re
from typing import Any, Callable, Dict, List, Optional

import httpx

import config


class BaseAgent:
    """
    Abstract base for all pipeline agents.

    Subclasses must define:
      name          — displayed in logs (e.g. "Analyzer")
      system_prompt — sent as the system message to Ollama

    Subclasses call self.chat(messages, emit) which returns the raw response
    text, then self._parse_json(text) to extract a dict.
    """

    name: str = "Agent"
    system_prompt: str = "You are a helpful assistant. Always respond with valid JSON."

    def chat(
        self,
        messages: List[Dict[str, str]],
        emit: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """
        Send messages to Ollama and return the raw response text.

        Args:
            messages: list of {"role": "user"|"assistant", "content": "..."}
                      (the system prompt is prepended automatically)
            emit: optional callback(agent_name, message)

        Returns:
            Raw text from the model response.
        """
        if emit:
            emit(self.name, f"Calling {config.MODEL} via Ollama…")

        payload = {
            "model": config.MODEL,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                *messages,
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": config.MAX_TOKENS,
            },
        }

        try:
            response = httpx.post(
                f"{config.OLLAMA_HOST}/api/chat",
                json=payload,
                timeout=180.0,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {config.OLLAMA_HOST}. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama HTTP error: {exc.response.status_code} — {exc.response.text}")

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from the model's response text.
        Tries three strategies in order:
          1. Fenced ```json ... ``` block
          2. Entire text as-is
          3. Largest {...} substring
        Returns {} if all strategies fail.
        """
        # Strategy 1: fenced block
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            candidate = m.group(1).strip()
            try:
                result = json.loads(candidate)
                if isinstance(result, list) and len(result) == 1:
                    result = result[0]
                return result if isinstance(result, dict) else {}
            except json.JSONDecodeError:
                pass

        # Strategy 2: whole text
        try:
            result = json.loads(text.strip())
            if isinstance(result, list) and len(result) == 1:
                result = result[0]
            return result if isinstance(result, dict) else {}
        except json.JSONDecodeError:
            pass

        # Strategy 3: largest {...} substring
        best: Dict[str, Any] = {}
        for match in re.finditer(r"\{", text):
            start = match.start()
            for end in range(len(text), start, -1):
                candidate = text[start:end]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict) and len(result) > len(best):
                        best = result
                    break
                except json.JSONDecodeError:
                    continue
        return best
