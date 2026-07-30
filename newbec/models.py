from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceMatch:
    source: str
    title: str
    composer: str | None = None
    score_url: str | None = None
    download_url: str | None = None
    file_format: str | None = None
    license: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NoteEvent:
    pitch: int
    start: float
    duration: float
    velocity: int = 80
    channel: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
