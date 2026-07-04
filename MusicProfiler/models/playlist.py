from dataclasses import dataclass


@dataclass
class PlaylistEntry:
    playlist: str
    song_id: str
    order: int

    CSV_HEADERS = ["playlist", "song_id", "order"]

    def to_row(self) -> dict:
        return {
            "playlist": self.playlist,
            "song_id": self.song_id,
            "order": str(self.order),
        }

    @classmethod
    def from_row(cls, row: dict) -> "PlaylistEntry":
        return cls(
            playlist=row["playlist"],
            song_id=row["song_id"],
            order=int(row["order"]),
        )
