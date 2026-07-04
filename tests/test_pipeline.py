import pytest
import os
import sys
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from MusicProfiler.models.song import Song, SongStatus
from MusicProfiler.core.pipeline import (
    PipelineStep,
    UnlockStep,
    DecodeStep,
    TranscodeStep,
    DemucsStep,
    NormalizeStep,
    ExportStep,
)
from MusicProfiler.core.engine import PipelineEngine


def make_context():
    return {
        "workspace_raw": "/tmp/ws/raw",
        "workspace_processed": "/tmp/ws/processed",
        "workspace_output": "/tmp/ws/output",
        "playlist_name": "test",
    }


def make_song(**kwargs):
    defaults = {
        "id": "001", "title": "Test Song", "path": "/tmp/test.ncm",
        "format": "ncm", "status": SongStatus.PENDING,
        "is_locked": True, "is_demucs_done": False,
        "is_normalized": False, "duration": 0.0,
    }
    defaults.update(kwargs)
    return Song(**defaults)


class TestUnlockStep:
    def test_unlocks_locked_song(self):
        mock_unlock = MagicMock()
        mock_unlock.unlock.return_value = {
            "success": True, "output_path": "/tmp/ws/raw/test.flac",
            "format": "ncm", "error": "",
        }

        step = UnlockStep(unlock_service=mock_unlock)
        songs = [make_song()]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert result[0].is_locked is False
        assert result[0].format == "flac"
        assert result[0].path == "/tmp/ws/raw/test.flac"
        assert result[0].status == SongStatus.PROCESSING

    def test_unlock_failure_marks_failed(self):
        mock_unlock = MagicMock()
        mock_unlock.unlock.return_value = {
            "success": False, "output_path": "", "format": "ncm",
            "error": "decrypt failed",
        }

        step = UnlockStep(unlock_service=mock_unlock)
        songs = [make_song()]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert result[0].status == SongStatus.FAILED

    def test_skips_unlocked_songs(self):
        mock_unlock = MagicMock()
        step = UnlockStep(unlock_service=mock_unlock)
        songs = [make_song(is_locked=False)]
        ctx = make_context()

        step.run(songs, ctx)
        mock_unlock.unlock.assert_not_called()

    def test_calls_progress_callback(self):
        mock_unlock = MagicMock()
        mock_unlock.unlock.return_value = {
            "success": True, "output_path": "/tmp/out.flac",
            "format": "ncm", "error": "",
        }

        progress_calls = []
        step = UnlockStep(unlock_service=mock_unlock)
        songs = [make_song(id="a"), make_song(id="b")]
        ctx = make_context()
        ctx["progress_callback"] = lambda name, cur, tot: progress_calls.append((name, cur, tot))

        step.run(songs, ctx)
        assert len(progress_calls) == 2


class TestDecodeStep:
    def test_decodes_song(self):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.extract_audio.return_value = {
            "success": True, "output_path": "/tmp/ws/raw/001_decoded.wav", "error": "",
        }
        step = DecodeStep(ffmpeg_service=mock_ffmpeg)
        songs = [make_song(is_locked=False, format="flac", status=SongStatus.PROCESSING)]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert "001_decoded.wav" in result[0].path
        assert result[0].format == "wav"

    def test_decode_failure_marks_failed(self):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.extract_audio.return_value = {
            "success": False, "output_path": "", "error": "codec error",
        }
        step = DecodeStep(ffmpeg_service=mock_ffmpeg)
        songs = [make_song()]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert result[0].status == SongStatus.FAILED

    def test_skips_failed_songs(self):
        mock_ffmpeg = MagicMock()
        step = DecodeStep(ffmpeg_service=mock_ffmpeg)
        songs = [make_song(status=SongStatus.FAILED)]
        ctx = make_context()

        step.run(songs, ctx)
        mock_ffmpeg.extract_audio.assert_not_called()


class TestTranscodeStep:
    def test_transcodes_song(self):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.transcode.return_value = {
            "success": True, "output_path": "/tmp/ws/processed/001.mp3", "error": "",
        }
        step = TranscodeStep(ffmpeg_service=mock_ffmpeg, target_format="mp3")
        songs = [make_song(status=SongStatus.PROCESSING, format="wav")]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert result[0].format == "mp3"

    def test_transcode_failure(self):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.transcode.return_value = {
            "success": False, "output_path": "", "error": "encoder error",
        }
        step = TranscodeStep(ffmpeg_service=mock_ffmpeg)
        songs = [make_song()]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert result[0].status == SongStatus.FAILED


class TestDemucsStep:
    def test_separates_song(self):
        mock_demucs = MagicMock()
        mock_demucs.separate.return_value = {
            "success": True, "stem_dir": "/tmp/ws/processed/htdemucs/001", "error": "",
        }
        step = DemucsStep(demucs_service=mock_demucs)
        songs = [make_song(status=SongStatus.PROCESSING)]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert result[0].is_demucs_done is True

    def test_skips_already_demucs_done(self):
        mock_demucs = MagicMock()
        step = DemucsStep(demucs_service=mock_demucs)
        songs = [make_song(is_demucs_done=True, status=SongStatus.PROCESSING)]
        ctx = make_context()

        step.run(songs, ctx)
        mock_demucs.separate.assert_not_called()

    def test_demucs_failure_does_not_mark_failed(self):
        mock_demucs = MagicMock()
        mock_demucs.separate.return_value = {
            "success": False, "stem_dir": "", "error": "OOM",
        }
        step = DemucsStep(demucs_service=mock_demucs)
        songs = [make_song()]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert result[0].is_demucs_done is False


class TestNormalizeStep:
    def test_normalizes_song(self):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.loudnorm.return_value = {
            "success": True, "output_path": "/tmp/ws/processed/001_norm.mp3", "error": "",
        }
        step = NormalizeStep(ffmpeg_service=mock_ffmpeg)
        songs = [make_song(status=SongStatus.PROCESSING, format="mp3")]
        ctx = make_context()

        result = step.run(songs, ctx)
        assert result[0].is_normalized is True

    def test_skips_already_normalized(self):
        mock_ffmpeg = MagicMock()
        step = NormalizeStep(ffmpeg_service=mock_ffmpeg)
        songs = [make_song(is_normalized=True, status=SongStatus.PROCESSING)]
        ctx = make_context()

        step.run(songs, ctx)
        mock_ffmpeg.loudnorm.assert_not_called()


class TestExportStep:
    def test_exports_single_song(self):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.transcode.return_value = {
            "success": True, "output_path": "/tmp/ws/output/test.mp3", "error": "",
        }
        step = ExportStep(ffmpeg_service=mock_ffmpeg, target_format="mp3")
        songs = [make_song(status=SongStatus.PROCESSING)]
        ctx = make_context()

        result = step.run(songs, ctx)
        mock_ffmpeg.transcode.assert_called_once()

    def test_exports_multiple_songs_via_concat(self):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.concat.return_value = {
            "success": True, "output_path": "/tmp/ws/output/test.mp3", "error": "",
        }
        step = ExportStep(ffmpeg_service=mock_ffmpeg)
        songs = [
            make_song(id="a", status=SongStatus.PROCESSING),
            make_song(id="b", status=SongStatus.PROCESSING),
        ]
        ctx = make_context()

        step.run(songs, ctx)
        mock_ffmpeg.concat.assert_called_once()

    def test_skips_failed_songs_in_concat(self):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.concat.return_value = {
            "success": True, "output_path": "/tmp/ws/output/test.mp3", "error": "",
        }
        mock_ffmpeg.transcode.return_value = {
            "success": True, "output_path": "/tmp/out.mp3", "error": "",
        }
        step = ExportStep(ffmpeg_service=mock_ffmpeg)
        songs = [
            make_song(id="ok1", status=SongStatus.PROCESSING),
            make_song(id="bad", status=SongStatus.FAILED),
            make_song(id="ok2", status=SongStatus.PROCESSING),
        ]
        ctx = make_context()

        step.run(songs, ctx)
        call_args = mock_ffmpeg.concat.call_args[0][0]
        assert len(call_args) == 2

    def test_empty_export(self):
        mock_ffmpeg = MagicMock()
        step = ExportStep(ffmpeg_service=mock_ffmpeg)
        ctx = make_context()
        result = step.run([], ctx)
        assert result == []


class TestPipelineEngine:
    def make_engine(self) -> tuple[PipelineEngine, MagicMock, MagicMock]:
        mock_song_store = MagicMock()
        mock_task_store = MagicMock()
        mock_task_store.create.return_value = MagicMock(task_id="task_1")
        workspace = {
            "raw": "/tmp/ws/raw",
            "processed": "/tmp/ws/processed",
            "output": "/tmp/ws/output",
        }
        engine = PipelineEngine(mock_song_store, mock_task_store, workspace)
        return engine, mock_song_store, mock_task_store

    def test_runs_all_steps_in_order(self):
        engine, song_store, task_store = self.make_engine()
        songs = [make_song(is_locked=False, status=SongStatus.PENDING)]

        call_order = []

        class StepA(PipelineStep):
            name = "a"
            def run(self, songs, ctx):
                call_order.append("a")
                return songs

        class StepB(PipelineStep):
            name = "b"
            def run(self, songs, ctx):
                call_order.append("b")
                return songs

        result = engine.run([StepA(), StepB()], songs)
        assert call_order == ["a", "b"]
        assert task_store.create.call_count == 2

    def test_engine_stops_on_step_failure(self):
        engine, song_store, task_store = self.make_engine()
        songs = [make_song()]

        class FailingStep(PipelineStep):
            name = "fail"
            def run(self, songs, ctx):
                raise RuntimeError("boom")

        class NeverRunStep(PipelineStep):
            name = "never"
            def run(self, songs, ctx):
                pytest.fail("Should not be called")
                return songs

        result = engine.run([FailingStep(), NeverRunStep()], songs)
        assert result[0].status == SongStatus.FAILED
        task_store.set_status.assert_called()

    def test_run_single_step(self):
        engine, song_store, task_store = self.make_engine()
        songs = [make_song(is_locked=False, status=SongStatus.PENDING)]

        mock_step = MagicMock()
        mock_step.name = "test_step"
        mock_step.run.return_value = songs

        result = engine.run_single_step(mock_step, songs)
        mock_step.run.assert_called_once()
