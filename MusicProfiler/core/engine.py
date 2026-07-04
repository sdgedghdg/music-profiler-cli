import logging
from typing import Optional, Callable

from ..i18n import t
from ..models.song import Song, SongStatus
from ..models.task import Task, TaskStatus
from ..storage.songs import SongStore
from ..storage.tasks import TaskStore
from .pipeline import PipelineStep

logger = logging.getLogger(__name__)


class PipelineEngine:
    """Orchestrates pipeline execution with task tracking."""

    def __init__(self, song_store: SongStore, task_store: TaskStore,
                 workspace: dict[str, str]):
        self.song_store = song_store
        self.task_store = task_store
        self.workspace = workspace

    def run(self, steps: list[PipelineStep], songs: list[Song],
            playlist_name: str = "") -> list[Song]:
        """Execute a pipeline of steps on a batch of songs.

        Args:
            steps: Ordered list of pipeline steps.
            songs: Songs to process.
            playlist_name: Optional playlist identifier for context.

        Returns:
            Processed songs.
        """
        total_steps = len(steps)
        context = {
            "workspace_raw": self.workspace["raw"],
            "workspace_processed": self.workspace["processed"],
            "workspace_output": self.workspace["output"],
            "playlist_name": playlist_name,
        }

        processed = list(songs)

        for step_idx, step in enumerate(steps):
            task = self.task_store.create(
                task_type=step.name,
                input_ref=playlist_name or "batch",
            )

            try:
                self.task_store.set_status(task.task_id, TaskStatus.RUNNING)

                def progress_cb(step_name, current, total):
                    pct = int((current / max(total, 1)) * 100)
                    self.task_store.set_progress(task.task_id, pct)

                context["progress_callback"] = progress_cb

                processed = step.run(processed, context)

                # Persist song state changes after each step
                for song in processed:
                    try:
                        self.song_store.update(song)
                    except KeyError:
                        pass

                self.task_store.set_status(task.task_id, TaskStatus.DONE)
                logger.info(t("engine.step.completed", name=step.name, current=step_idx + 1, total=total_steps))

            except Exception as e:
                self.task_store.set_status(task.task_id, TaskStatus.FAILED, error=str(e))
                logger.error(t("engine.step.failed", name=step.name, error=str(e)))
                # Mark all remaining songs as failed
                for song in processed:
                    if song.status != SongStatus.FAILED:
                        song.status = SongStatus.FAILED
                break

        return processed

    def run_single_step(self, step: PipelineStep, songs: list[Song]) -> list[Song]:
        """Run a single step independently."""
        context = {
            "workspace_raw": self.workspace["raw"],
            "workspace_processed": self.workspace["processed"],
            "workspace_output": self.workspace["output"],
            "playlist_name": "",
        }
        return step.run(songs, context)
