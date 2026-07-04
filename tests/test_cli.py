import pytest
import os
import sys
import tempfile
import csv
from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from MusicProfiler.cli.main import main
from MusicProfiler.models.song import Song
from MusicProfiler.models.playlist import PlaylistEntry


class TestCLIImport:
    def test_import_csv(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            # Create a source CSV
            src_csv = os.path.join(tmp, "source.csv")
            with open(src_csv, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()
                w.writerow({
                    "id": "cli001", "title": "CLI Song", "path": "/tmp/cli.ncm",
                    "format": "ncm", "status": "pending", "is_locked": "True",
                    "is_demucs_done": "False", "is_normalized": "False", "duration": "0",
                })

            store_path = os.path.join(tmp, "songs.csv")
            result = runner.invoke(main, ["import", src_csv, "--store", store_path])
            assert result.exit_code == 0
            assert "Imported 1 songs" in result.output

    def test_import_nonexistent_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ["import", "/nonexistent/path.csv"])
        assert result.exit_code != 0


class TestCLIList:
    def test_list_empty_store(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            store_path = os.path.join(tmp, "songs.csv")
            # Create empty store
            with open(store_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()

            result = runner.invoke(main, ["list", "--store", store_path])
            assert result.exit_code == 0
            assert "No songs found" in result.output

    def test_list_with_songs(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            store_path = os.path.join(tmp, "songs.csv")
            with open(store_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()
                w.writerow({
                    "id": "s1", "title": "Song One", "path": "/tmp/s1.mp3",
                    "format": "mp3", "status": "pending", "is_locked": "False",
                    "is_demucs_done": "False", "is_normalized": "False", "duration": "120.5",
                })

            result = runner.invoke(main, ["list", "--store", store_path])
            assert result.exit_code == 0
            assert "Song One" in result.output

    def test_list_filter_by_status(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            store_path = os.path.join(tmp, "songs.csv")
            with open(store_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()
                w.writerow({
                    "id": "ok", "title": "OK Song", "path": "/tmp/ok.mp3",
                    "format": "mp3", "status": "done", "is_locked": "False",
                    "is_demucs_done": "True", "is_normalized": "True", "duration": "60",
                })
                w.writerow({
                    "id": "bad", "title": "Bad Song", "path": "/tmp/bad.mp3",
                    "format": "mp3", "status": "failed", "is_locked": "False",
                    "is_demucs_done": "False", "is_normalized": "False", "duration": "30",
                })

            result = runner.invoke(main, ["list", "--store", store_path, "--status", "done"])
            assert result.exit_code == 0
            assert "OK Song" in result.output
            assert "Bad Song" not in result.output

    def test_list_invalid_status(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            store_path = os.path.join(tmp, "songs.csv")
            with open(store_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()

            result = runner.invoke(main, ["list", "--store", store_path, "--status", "invalid"])
            assert result.exit_code != 0


class TestCLITasks:
    def test_tasks_empty(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            task_path = os.path.join(tmp, "tasks.csv")
            with open(task_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "type", "status", "progress", "input", "output", "error"])
                w.writeheader()

            result = runner.invoke(main, ["tasks", "--store", task_path])
            assert result.exit_code == 0
            assert "No tasks found" in result.output

    def test_tasks_with_data(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            task_path = os.path.join(tmp, "tasks.csv")
            with open(task_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "type", "status", "progress", "input", "output", "error"])
                w.writeheader()
                w.writerow({
                    "task_id": "abc123", "type": "demucs", "status": "done",
                    "progress": "100", "input": "song_01", "output": "", "error": "",
                })

            result = runner.invoke(main, ["tasks", "--store", task_path])
            assert result.exit_code == 0
            assert "demucs" in result.output
            assert "done" in result.output


class TestCLIProcess:
    def test_process_no_songs(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            songs_path = os.path.join(tmp, "songs.csv")
            with open(songs_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()

            tasks_path = os.path.join(tmp, "tasks.csv")
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "type", "status", "progress", "input", "output", "error"])
                w.writeheader()

            playlists_path = os.path.join(tmp, "playlists.csv")
            with open(playlists_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=PlaylistEntry.CSV_HEADERS)
                w.writeheader()

            result = runner.invoke(main, [
                "process", "--song-store", songs_path,
                "--playlist", playlists_path,
            ])
            # Should exit cleanly even with no songs
            assert "No songs" in result.output

    def test_process_with_step_flag(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            songs_path = os.path.join(tmp, "songs.csv")
            with open(songs_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()
                w.writerow({
                    "id": "s1", "title": "Test", "path": "/tmp/test.mp3",
                    "format": "mp3", "status": "pending", "is_locked": "False",
                    "is_demucs_done": "False", "is_normalized": "False", "duration": "100",
                })

            tasks_path = os.path.join(tmp, "tasks.csv")
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "type", "status", "progress", "input", "output", "error"])
                w.writeheader()

            result = runner.invoke(main, [
                "process", "--song-store", songs_path,
                "--step", "normalize",
            ])
            assert result.exit_code == 0

    def test_process_unknown_step(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            songs_path = os.path.join(tmp, "songs.csv")
            with open(songs_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()
                w.writerow({
                    "id": "s1", "title": "Test", "path": "/tmp/test.mp3",
                    "format": "mp3", "status": "pending", "is_locked": "False",
                    "is_demucs_done": "False", "is_normalized": "False", "duration": "0",
                })

            tasks_path = os.path.join(tmp, "tasks.csv")
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "type", "status", "progress", "input", "output", "error"])
                w.writeheader()

            result = runner.invoke(main, [
                "process", "--song-store", songs_path,
                "--step", "nonexistent",
            ])
            assert result.exit_code != 0


class TestCLIDemucs:
    def test_demucs_no_songs(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            songs_path = os.path.join(tmp, "songs.csv")
            with open(songs_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()

            tasks_path = os.path.join(tmp, "tasks.csv")
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "type", "status", "progress", "input", "output", "error"])
                w.writeheader()

            result = runner.invoke(main, [
                "demucs", "--song-store", songs_path,
            ])
            assert "No songs found" in result.output


class TestCLINormalize:
    def test_normalize_no_songs(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            songs_path = os.path.join(tmp, "songs.csv")
            with open(songs_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()

            tasks_path = os.path.join(tmp, "tasks.csv")
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "type", "status", "progress", "input", "output", "error"])
                w.writeheader()

            result = runner.invoke(main, [
                "normalize", "--song-store", songs_path,
            ])
            assert "No songs found" in result.output


class TestCLIExport:
    def test_export_empty_playlist(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            songs_path = os.path.join(tmp, "songs.csv")
            with open(songs_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=Song.CSV_HEADERS)
                w.writeheader()

            tasks_path = os.path.join(tmp, "tasks.csv")
            with open(tasks_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["task_id", "type", "status", "progress", "input", "output", "error"])
                w.writeheader()

            pl_path = os.path.join(tmp, "playlists.csv")
            with open(pl_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=PlaylistEntry.CSV_HEADERS)
                w.writeheader()

            result = runner.invoke(main, [
                "export", "--playlist", pl_path, "--song-store", songs_path,
            ])
            assert "No songs found" in result.output
