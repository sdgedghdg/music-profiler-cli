import pytest
import tempfile
import os
import sys
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from MusicProfiler.models.song import Song, SongStatus
from MusicProfiler.models.playlist import PlaylistEntry
from MusicProfiler.models.task import Task, TaskStatus
from MusicProfiler.storage.songs import SongStore
from MusicProfiler.storage.playlists import PlaylistStore
from MusicProfiler.storage.tasks import TaskStore


class TestSongStore:
    def make_store(self) -> tuple[SongStore, str]:
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "songs.csv")
        return SongStore(path), tmp

    def test_empty_store(self):
        store, _ = self.make_store()
        assert store.get_all() == []

    def test_add_and_get(self):
        store, _ = self.make_store()
        s = Song(id="001", title="Test", path="/tmp/test.mp3", format="mp3")
        store.add(s)
        songs = store.get_all()
        assert len(songs) == 1
        assert songs[0].id == "001"

    def test_add_duplicate_raises(self):
        store, _ = self.make_store()
        s = Song(id="001", title="Test", path="/tmp/test.mp3")
        store.add(s)
        with pytest.raises(ValueError, match="already exists"):
            store.add(s)

    def test_get_by_id(self):
        store, _ = self.make_store()
        store.add(Song(id="a", title="A", path="/tmp/a.mp3"))
        store.add(Song(id="b", title="B", path="/tmp/b.mp3"))
        assert store.get_by_id("a").title == "A"
        assert store.get_by_id("nonexistent") is None

    def test_get_by_ids(self):
        store, _ = self.make_store()
        store.add(Song(id="a", title="A", path="/tmp/a.mp3"))
        store.add(Song(id="b", title="B", path="/tmp/b.mp3"))
        store.add(Song(id="c", title="C", path="/tmp/c.mp3"))
        result = store.get_by_ids(["a", "c"])
        assert len(result) == 2
        assert {s.id for s in result} == {"a", "c"}

    def test_update(self):
        store, _ = self.make_store()
        s = Song(id="001", title="Test", path="/tmp/test.mp3")
        store.add(s)
        s.status = SongStatus.DONE
        s.duration = 42.0
        store.update(s)
        updated = store.get_by_id("001")
        assert updated.status == SongStatus.DONE
        assert updated.duration == 42.0

    def test_update_nonexistent_raises(self):
        store, _ = self.make_store()
        s = Song(id="ghost", title="Ghost", path="/tmp/g.mp3")
        with pytest.raises(KeyError):
            store.update(s)

    def test_update_batch(self):
        store, _ = self.make_store()
        s1 = Song(id="a", title="A", path="/tmp/a.mp3")
        s2 = Song(id="b", title="B", path="/tmp/b.mp3")
        store.add(s1)
        store.add(s2)
        s1.status = SongStatus.DONE
        s2.status = SongStatus.FAILED
        store.update_batch([s1, s2])
        assert store.get_by_id("a").status == SongStatus.DONE
        assert store.get_by_id("b").status == SongStatus.FAILED

    def test_import_csv(self):
        store, tmp = self.make_store()
        ext_csv = os.path.join(tmp, "external.csv")
        with open(ext_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
            w.writeheader()
            w.writerow({"id": "imp1", "title": "Imported1", "path": "/tmp/i1.mp3", "format": "mp3",
                        "status": "pending", "is_locked": "False", "is_demucs_done": "False",
                        "is_normalized": "False", "duration": "0"})
            w.writerow({"id": "imp2", "title": "Imported2", "path": "/tmp/i2.mp3", "format": "mp3",
                        "status": "pending", "is_locked": "False", "is_demucs_done": "False",
                        "is_normalized": "False", "duration": "0"})

        count = store.import_csv(ext_csv)
        assert count == 2
        assert len(store.get_all()) == 2


class TestPlaylistStore:
    def make_store(self) -> tuple[PlaylistStore, str]:
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "playlists.csv")
        return PlaylistStore(path), tmp

    def test_empty_store(self):
        store, _ = self.make_store()
        assert store.get_all() == []

    def test_add_entry(self):
        store, _ = self.make_store()
        store.add_entry(PlaylistEntry(playlist="monday", song_id="001", order=1))
        assert len(store.get_all()) == 1

    def test_get_by_playlist_returns_sorted(self):
        store, _ = self.make_store()
        store.add_entry(PlaylistEntry(playlist="monday", song_id="c", order=3))
        store.add_entry(PlaylistEntry(playlist="monday", song_id="a", order=1))
        store.add_entry(PlaylistEntry(playlist="monday", song_id="b", order=2))
        store.add_entry(PlaylistEntry(playlist="tuesday", song_id="x", order=1))

        monday = store.get_by_playlist("monday")
        assert len(monday) == 3
        assert [e.order for e in monday] == [1, 2, 3]

    def test_get_playlist_names(self):
        store, _ = self.make_store()
        store.add_entry(PlaylistEntry(playlist="a", song_id="1", order=1))
        store.add_entry(PlaylistEntry(playlist="b", song_id="2", order=1))
        store.add_entry(PlaylistEntry(playlist="a", song_id="3", order=2))
        assert store.get_playlist_names() == ["a", "b"]

    def test_remove_playlist(self):
        store, _ = self.make_store()
        store.add_entry(PlaylistEntry(playlist="keep", song_id="1", order=1))
        store.add_entry(PlaylistEntry(playlist="remove", song_id="2", order=1))
        store.remove_playlist("remove")
        assert store.get_playlist_names() == ["keep"]
        assert len(store.get_all()) == 1

    def test_import_csv(self):
        store, tmp = self.make_store()
        ext_csv = os.path.join(tmp, "ext_pl.csv")
        with open(ext_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=PlaylistEntry.CSV_HEADERS)
            w.writeheader()
            w.writerow({"playlist": "imported", "song_id": "s1", "order": "1"})
            w.writerow({"playlist": "imported", "song_id": "s2", "order": "2"})
        count = store.import_csv(ext_csv)
        assert count == 2
        assert len(store.get_by_playlist("imported")) == 2


class TestTaskStore:
    def make_store(self) -> tuple[TaskStore, str]:
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "tasks.csv")
        return TaskStore(path), tmp

    def test_empty_store(self):
        store, _ = self.make_store()
        assert store.get_all() == []

    def test_create_task(self):
        store, _ = self.make_store()
        t = store.create("demucs", input_ref="song_01")
        assert t.task_id
        assert t.type == "demucs"
        assert t.status == TaskStatus.PENDING
        assert len(store.get_all()) == 1

    def test_set_progress(self):
        store, _ = self.make_store()
        t = store.create("normalize")
        store.set_progress(t.task_id, 75)
        updated = store.get_by_id(t.task_id)
        assert updated.progress == 75

    def test_set_progress_clamped(self):
        store, _ = self.make_store()
        t = store.create("transcode")
        store.set_progress(t.task_id, 150)
        assert store.get_by_id(t.task_id).progress == 100
        store.set_progress(t.task_id, -10)
        assert store.get_by_id(t.task_id).progress == 0

    def test_set_status(self):
        store, _ = self.make_store()
        t = store.create("export")
        store.set_status(t.task_id, TaskStatus.RUNNING)
        assert store.get_by_id(t.task_id).status == TaskStatus.RUNNING
        store.set_status(t.task_id, TaskStatus.DONE)
        updated = store.get_by_id(t.task_id)
        assert updated.status == TaskStatus.DONE
        assert updated.progress == 100

    def test_set_status_with_error(self):
        store, _ = self.make_store()
        t = store.create("demucs")
        store.set_status(t.task_id, TaskStatus.FAILED, error="OOM killed")
        updated = store.get_by_id(t.task_id)
        assert updated.status == TaskStatus.FAILED
        assert updated.error == "OOM killed"

    def test_get_by_status(self):
        store, _ = self.make_store()
        t1 = store.create("a")
        t2 = store.create("b")
        store.set_status(t2.task_id, TaskStatus.DONE)
        pending = store.get_by_status(TaskStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].task_id == t1.task_id

    def test_get_pending(self):
        store, _ = self.make_store()
        store.create("a")
        store.create("b")
        assert len(store.get_pending()) == 2
