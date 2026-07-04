import pytest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from MusicProfiler.models.song import Song, SongStatus
from MusicProfiler.models.playlist import PlaylistEntry
from MusicProfiler.models.task import Task, TaskStatus


class TestSong:
    def test_create_song(self):
        s = Song(id="001", title="Test Song", path="/tmp/test.ncm", format="ncm")
        assert s.id == "001"
        assert s.title == "Test Song"
        assert s.status == SongStatus.PENDING
        assert s.is_locked is False
        assert s.is_demucs_done is False
        assert s.is_normalized is False
        assert s.duration == 0.0

    def test_to_row_and_from_row_roundtrip(self):
        s = Song(
            id="002", title="Round Trip", path="/tmp/rt.mp3",
            format="mp3", status=SongStatus.DONE,
            is_locked=False, is_demucs_done=True, is_normalized=True,
            duration=180.5,
        )
        row = s.to_row()
        s2 = Song.from_row(row)
        assert s2.id == s.id
        assert s2.title == s.title
        assert s2.status == s.status
        assert s2.is_locked == s.is_locked
        assert s2.is_demucs_done == s.is_demucs_done
        assert s2.is_normalized == s.is_normalized
        assert s2.duration == s.duration

    def test_from_row_defaults(self):
        row = {"id": "003", "title": "Defaults", "path": "/tmp/d.mp3"}
        s = Song.from_row(row)
        assert s.format == ""
        assert s.status == SongStatus.PENDING
        assert s.is_locked is False
        assert s.duration == 0.0

    def test_csv_headers_match_to_row_keys(self):
        s = Song(id="x", title="x", path="x")
        row = s.to_row()
        for h in Song.CSV_HEADERS:
            assert h in row


class TestPlaylistEntry:
    def test_create_entry(self):
        e = PlaylistEntry(playlist="monday", song_id="001", order=1)
        assert e.playlist == "monday"
        assert e.song_id == "001"
        assert e.order == 1

    def test_to_row_and_from_row_roundtrip(self):
        e = PlaylistEntry(playlist="favorites", song_id="abc123", order=5)
        row = e.to_row()
        e2 = PlaylistEntry.from_row(row)
        assert e2.playlist == e.playlist
        assert e2.song_id == e.song_id
        assert e2.order == e.order


class TestTask:
    def test_create_task(self):
        t = Task(task_id="t1", type="demucs", input="song_01")
        assert t.task_id == "t1"
        assert t.type == "demucs"
        assert t.status == TaskStatus.PENDING
        assert t.progress == 0

    def test_to_row_and_from_row_roundtrip(self):
        t = Task(
            task_id="t2", type="normalize", status=TaskStatus.RUNNING,
            progress=50, input="in.wav", output="out.wav", error="",
        )
        row = t.to_row()
        t2 = Task.from_row(row)
        assert t2.task_id == t.task_id
        assert t2.status == t.status
        assert t2.progress == 50

    def test_task_lifecycle(self):
        t = Task(task_id="t3", type="export")
        assert t.status == TaskStatus.PENDING
        t.status = TaskStatus.RUNNING
        t.progress = 50
        assert t.status == TaskStatus.RUNNING
        t.status = TaskStatus.DONE
        t.progress = 100
        assert t.status == TaskStatus.DONE
        t.status = TaskStatus.FAILED
        t.error = "Something went wrong"
        assert t.status == TaskStatus.FAILED
