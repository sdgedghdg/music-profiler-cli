import csv
import os
from typing import Optional


class CsvStore:
    """Base class for CSV-backed stores."""

    def __init__(self, filepath: str, headers: list[str]):
        self.filepath = filepath
        self.headers = headers
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)

    def _read_rows(self) -> list[dict]:
        with open(self.filepath, "r", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _write_rows(self, rows: list[dict]):
        with open(self.filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
            writer.writerows(rows)
