import csv
import os
from typing import Optional

from ..models.song import Song, SongStatus
from .base import CsvStore


class SongStore(CsvStore):
    """CRUD store for songs.csv."""

    def __init__(self, filepath: str):
        super().__init__(filepath, Song.CSV_HEADERS)

    def get_all(self) -> list[Song]:
        return [Song.from_row(r) for r in self._read_rows()]

    def get_by_id(self, song_id: str) -> Optional[Song]:
        for song in self.get_all():
            if song.id == song_id:
                return song
        return None

    def get_by_ids(self, song_ids: list[str]) -> list[Song]:
        all_songs = {s.id: s for s in self.get_all()}
        return [all_songs[sid] for sid in song_ids if sid in all_songs]

    def add(self, song: Song):
        songs = self.get_all()
        existing = {s.id for s in songs}
        if song.id in existing:
            raise ValueError(f"Song with id '{song.id}' already exists")
        songs.append(song)
        self._write_rows([s.to_row() for s in songs])

    def add_batch(self, new_songs: list[Song]):
        songs = self.get_all()
        existing = {s.id for s in songs}
        for song in new_songs:
            if song.id in existing:
                raise ValueError(f"Song with id '{song.id}' already exists")
        songs.extend(new_songs)
        self._write_rows([s.to_row() for s in songs])

    def update(self, song: Song):
        songs = self.get_all()
        for i, s in enumerate(songs):
            if s.id == song.id:
                songs[i] = song
                self._write_rows([s.to_row() for s in songs])
                return
        raise KeyError(f"Song with id '{song.id}' not found")

    def update_batch(self, updated_songs: list[Song]):
        song_map = {s.id: s for s in updated_songs}
        songs = self.get_all()
        for i, s in enumerate(songs):
            if s.id in song_map:
                songs[i] = song_map[s.id]
        self._write_rows([s.to_row() for s in songs])

    def import_csv(self, csv_path: str):
        """Import songs from an external CSV file."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            imported = [Song.from_row(r) for r in reader]

        self.add_batch(imported)
        return len(imported)
