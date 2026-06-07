from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class AdapterError(RuntimeError):
    pass


class ComplianceBlocked(AdapterError):
    pass


@dataclass(slots=True)
class AdapterResult:
    records: list[dict]
    provider: str
    source_url: str | None = None
    raw: dict = field(default_factory=dict)


class CreatorIngestionAdapter(Protocol):
    provider: str

    def discover(self, query: str, limit: int = 10) -> AdapterResult:
        raise NotImplementedError

    def fetch_profile(self, profile_url: str) -> AdapterResult:
        raise NotImplementedError

