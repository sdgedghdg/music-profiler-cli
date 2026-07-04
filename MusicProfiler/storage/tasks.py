import uuid
from typing import Optional

from ..models.task import Task, TaskStatus
from .base import CsvStore


class TaskStore(CsvStore):
    """CRUD store for tasks.csv."""

    def __init__(self, filepath: str):
        super().__init__(filepath, Task.CSV_HEADERS)

    def get_all(self) -> list[Task]:
        return [Task.from_row(r) for r in self._read_rows()]

    def get_by_id(self, task_id: str) -> Optional[Task]:
        for t in self.get_all():
            if t.task_id == task_id:
                return t
        return None

    def get_by_status(self, status: TaskStatus) -> list[Task]:
        return [t for t in self.get_all() if t.status == status]

    def create(self, task_type: str, input_ref: str = "", output_ref: str = "") -> Task:
        task = Task(
            task_id=uuid.uuid4().hex[:12],
            type=task_type,
            status=TaskStatus.PENDING,
            input=input_ref,
            output=output_ref,
        )
        rows = self._read_rows()
        rows.append(task.to_row())
        self._write_rows(rows)
        return task

    def update(self, task: Task):
        tasks = self.get_all()
        for i, t in enumerate(tasks):
            if t.task_id == task.task_id:
                tasks[i] = task
                self._write_rows([t.to_row() for t in tasks])
                return
        raise KeyError(f"Task with id '{task.task_id}' not found")

    def set_progress(self, task_id: str, progress: int):
        task = self.get_by_id(task_id)
        if task:
            task.progress = max(0, min(100, progress))
            self.update(task)

    def set_status(self, task_id: str, status: TaskStatus, error: str = ""):
        task = self.get_by_id(task_id)
        if task:
            task.status = status
            if error:
                task.error = error
            if status == TaskStatus.DONE:
                task.progress = 100
            self.update(task)

    def get_pending(self) -> list[Task]:
        return self.get_by_status(TaskStatus.PENDING)
