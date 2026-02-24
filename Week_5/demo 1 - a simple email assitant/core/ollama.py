"""
core/ollama.py
Ollama API client for local LLM inference.
Supports chat completions, model listing, and health checks.
"""

import requests
from typing import List, Optional
from core.config import Config
from core.logger import get_logger

log = get_logger("ollama")


class OllamaClient:
    """
    Client for the local Ollama inference server.

    Usage:
        client = OllamaClient(cfg)
        reply  = client.chat("Write a haiku about lobsters.")
    """

    def __init__(self, cfg: Config):
        self.base_url = cfg.OLLAMA_BASE_URL.rstrip("/")
        self.model    = cfg.OLLAMA_MODEL
        self.system   = cfg.SYSTEM_PROMPT

    # ── Health ────────────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            resp = requests.get(f"{self.base_url}/", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Return a list of locally available model names."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            log.error("Could not list Ollama models: %s", e)
            return []

    def model_exists(self, model: Optional[str] = None) -> bool:
        """Check if a specific model is available locally."""
        target = model or self.model
        return target in self.list_models()

    # ── Inference ─────────────────────────────────────────────────────────────

    def chat(
        self,
        user_message: str,
        system: Optional[str] = None,
        history: Optional[List[dict]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a chat message to Ollama and return the assistant's reply.

        Args:
            user_message: The user's input message.
            system:       System prompt (overrides cfg default if provided).
            history:      Optional list of prior messages [{"role":..,"content":..}].
            model:        Override the default model for this call.
            temperature:  Sampling temperature (0.0–1.0).
            max_tokens:   Maximum tokens to generate.

        Returns:
            The assistant's reply as a string, or an error message.
        """
        messages = []

        # System prompt
        sys_prompt = system if system is not None else self.system
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})

        # Prior conversation history
        if history:
            messages.extend(history)

        # Current user message
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model":   model or self.model,
            "messages": messages,
            "stream":  False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()

        except requests.exceptions.ConnectionError:
            msg = (
                "Cannot reach Ollama. Is it running?\n"
                "Start it with: ollama serve"
            )
            log.error(msg)
            return f"[Error] {msg}"

        except requests.exceptions.Timeout:
            log.error("Ollama request timed out.")
            return "[Error] The AI model took too long to respond."

        except requests.exceptions.HTTPError as e:
            log.error("Ollama HTTP error: %s", e)
            return f"[Error] Ollama returned an error: {e}"

        except KeyError:
            log.error("Unexpected Ollama response format.")
            return "[Error] Unexpected response from Ollama."

        except Exception as e:
            log.error("Unexpected Ollama error: %s", e)
            return f"[Error] {e}"

    def complete(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Raw completion (non-chat) via the /api/generate endpoint.

        Args:
            prompt: The full prompt string.
            model:  Override the default model.

        Returns:
            Generated text as a string.
        """
        payload = {
            "model":  model or self.model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            log.error("Ollama complete() error: %s", e)
            return f"[Error] {e}"
