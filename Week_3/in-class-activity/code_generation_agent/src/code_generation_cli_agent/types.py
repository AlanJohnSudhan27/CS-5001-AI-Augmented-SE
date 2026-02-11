from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    repo: str
    model: str
    host: str
    temperature: float
    verbose: bool = False


@dataclass(frozen=True)
class RunResult:
    ok: bool
    details: str