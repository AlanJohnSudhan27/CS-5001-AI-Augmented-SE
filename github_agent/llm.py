from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class OllamaLLM:
    model: str
    host: str = "http://localhost:11434"
    temperature: float = 0.0
    timeout_s: int = 60
    num_predict: int = 96

    def generate(self, prompt: str) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": float(self.temperature),
                "num_predict": int(self.num_predict),
            },
        }
        last_error: Exception | None = None
        for attempt in range(2):
            timeout = self.timeout_s if attempt == 0 else int(self.timeout_s * 1.5)
            try:
                response = requests.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                return (data.get("response") or "").strip()
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if attempt == 0:
                    continue
                break

        raise RuntimeError(f"Failed to call Ollama at {url}: {last_error}") from last_error


def create_llm(
    model: str = "",
    host: str = "http://localhost:11434",
    temperature: float = 0.0,
    timeout_s: int = 60,
) -> OllamaLLM:
    """Create an Ollama LLM instance."""
    return OllamaLLM(model=model or "llama3.1:8b", host=host, temperature=temperature, timeout_s=timeout_s)
