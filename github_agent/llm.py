from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class OllamaLLM:
    model: str
    host: str = "http://localhost:11434"
    temperature: float = 0.0
    timeout_s: int = 120

    def generate(self, prompt: str) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": float(self.temperature)},
        }
        try:
            response = requests.post(url, json=payload, timeout=self.timeout_s)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Failed to call Ollama at {url}: {exc}") from exc

        data = response.json()
        return (data.get("response") or "").strip()


def create_llm(
    model: str = "",
    host: str = "http://localhost:11434",
    temperature: float = 0.0,
) -> OllamaLLM:
    """Create an Ollama LLM instance."""
    return OllamaLLM(model=model or "llama3.1:8b", host=host, temperature=temperature)
