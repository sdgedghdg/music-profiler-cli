from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Task:
    task_id: str
    type: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    input: str = ""
    output: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)

    CSV_HEADERS = [
        "task_id", "type", "status", "progress", "input", "output", "error",
    ]

    def to_row(self) -> dict:
        return {
            "task_id": self.task_id,
            "type": self.type,
            "status": self.status.value,
            "progress": str(self.progress),
            "input": self.input,
            "output": self.output,
            "error": self.error,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Task":
        return cls(
            task_id=row["task_id"],
            type=row["type"],
            status=TaskStatus(row.get("status", "pending")),
            progress=int(row.get("progress", 0) or 0),
            input=row.get("input", ""),
            output=row.get("output", ""),
            error=row.get("error", ""),
        )
