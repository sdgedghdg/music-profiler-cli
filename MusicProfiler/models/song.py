from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SongStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Song:
    id: str
    title: str
    path: str
    format: str = ""
    status: SongStatus = SongStatus.PENDING
    is_locked: bool = False
    is_demucs_done: bool = False
    is_normalized: bool = False
    duration: float = 0.0

    CSV_HEADERS = [
        "id", "title", "path", "format", "status",
        "is_locked", "is_demucs_done", "is_normalized", "duration",
    ]

    def to_row(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "path": self.path,
            "format": self.format,
            "status": self.status.value,
            "is_locked": str(self.is_locked),
            "is_demucs_done": str(self.is_demucs_done),
            "is_normalized": str(self.is_normalized),
            "duration": str(self.duration),
        }

    @classmethod
    def from_row(cls, row: dict) -> "Song":
        return cls(
            id=row["id"],
            title=row["title"],
            path=row["path"],
            format=row.get("format", ""),
            status=SongStatus(row.get("status", "pending")),
            is_locked=row.get("is_locked", "False").lower() in ("true", "1"),
            is_demucs_done=row.get("is_demucs_done", "False").lower() in ("true", "1"),
            is_normalized=row.get("is_normalized", "False").lower() in ("true", "1"),
            duration=float(row.get("duration", 0) or 0),
        )
