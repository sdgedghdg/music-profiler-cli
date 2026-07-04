import csv
import os
from typing import Optional

from ..models.playlist import PlaylistEntry
from .base import CsvStore


class PlaylistStore(CsvStore):
    """CRUD store for playlists.csv."""

    def __init__(self, filepath: str):
        super().__init__(filepath, PlaylistEntry.CSV_HEADERS)

    def get_all(self) -> list[PlaylistEntry]:
        return [PlaylistEntry.from_row(r) for r in self._read_rows()]

    def get_by_playlist(self, playlist_name: str) -> list[PlaylistEntry]:
        entries = self.get_all()
        entries = [e for e in entries if e.playlist == playlist_name]
        entries.sort(key=lambda e: e.order)
        return entries

    def get_playlist_names(self) -> list[str]:
        names = set()
        for e in self.get_all():
            names.add(e.playlist)
        return sorted(names)

    def add_entry(self, entry: PlaylistEntry):
        entries = self.get_all()
        entries.append(entry)
        self._write_rows([e.to_row() for e in entries])

    def import_csv(self, csv_path: str) -> int:
        """Import playlist entries from an external CSV file."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            imported = [PlaylistEntry.from_row(r) for r in reader]

        entries = self.get_all()
        entries.extend(imported)
        self._write_rows([e.to_row() for e in entries])
        return len(imported)

    def remove_playlist(self, playlist_name: str):
        entries = [e for e in self.get_all() if e.playlist != playlist_name]
        self._write_rows([e.to_row() for e in entries])
