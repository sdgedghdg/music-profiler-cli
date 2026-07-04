#!/usr/bin/env python3
"""MusicProfiler CLI — Audio batch processing workflow engine."""

import os
import sys
import logging
import click

from ..i18n import t, set_locale
from ..models.song import Song, SongStatus
from ..models.task import TaskStatus
from ..storage.songs import SongStore
from ..storage.playlists import PlaylistStore
from ..storage.tasks import TaskStore
from ..core.pipeline import (
    UnlockStep, DecodeStep, TranscodeStep,
    DemucsStep, NormalizeStep, ExportStep,
)
from ..core.engine import PipelineEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("musicprofiler")


def _get_base_dir():
    """Get the MusicProfiler package base directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_default_path(filename: str) -> str:
    return os.path.join(_get_base_dir(), "storage", filename)


def _get_workspace() -> dict[str, str]:
    base = os.path.join(_get_base_dir(), "workspace")
    return {
        "raw": os.path.join(base, "raw"),
        "processed": os.path.join(base, "processed"),
        "output": os.path.join(base, "output"),
    }


def _set_lang(ctx, param, value):
    """Eager callback that switches locale before any sub-command runs."""
    if value:
        set_locale(value)


@click.group()
@click.version_option(version="0.1.0", prog_name="musicprofiler")
@click.option(
    "--lang", "-l", default=None, is_eager=True,
    expose_value=False, callback=_set_lang,
    help=t("cli.main.lang_help"),
)
def main():
    """MusicProfiler — CLI audio batch processing workflow engine.
    \b
    CSV-driven pipeline for audio unlock, decode, transcode,
    demucs separation, loudness normalization, and export.
    """
    pass


@main.command(name="import")
@click.argument("csv_path", type=click.Path(exists=True))
@click.option("--store", default=None,
              help=t("cli.import.store_help"))
def import_cmd(csv_path, store):
    """Import songs from a CSV file into the song store."""
    store_path = store or _get_default_path("songs.csv")
    song_store = SongStore(store_path)

    try:
        count = song_store.import_csv(csv_path)
        click.echo(t("cli.import.success", count=count, path=csv_path))
        click.echo(t("cli.import.store", path=store_path))
    except Exception as e:
        click.echo(t("cli.import.error", error=e), err=True)
        sys.exit(1)


@main.command(name="list")
@click.argument("csv_path", type=click.Path(exists=True), required=False)
@click.option("--store", default=None,
              help=t("cli.list.store_help"))
@click.option("--status", default=None,
              help=t("cli.list.status_help"))
def list_cmd(csv_path, store, status):
    """List songs from the store or a CSV file."""
    source = csv_path or store or _get_default_path("songs.csv")
    song_store = SongStore(source)
    songs = song_store.get_all()

    if status:
        try:
            st = SongStatus(status)
            songs = [s for s in songs if s.status == st]
        except ValueError:
            click.echo(t("cli.list.invalid_status", status=status), err=True)
            sys.exit(1)

    if not songs:
        click.echo(t("cli.list.empty"))
        return

    hid = t("cli.list.header_id")
    hti = t("cli.list.header_title")
    hfm = t("cli.list.header_format")
    hst = t("cli.list.header_status")
    hlo = t("cli.list.header_locked")
    hde = t("cli.list.header_demucs")
    hno = t("cli.list.header_norm")
    hdu = t("cli.list.header_duration")

    click.echo(f"{hid:<14} {hti:<30} {hfm:<8} {hst:<12} {hlo:<8} {hde:<8} {hno:<6} {hdu}")
    click.echo("-" * 100)
    for s in songs:
        click.echo(
            f"{s.id:<14} {s.title[:28]:<30} {s.format:<8} {s.status.value:<12} "
            f"{str(s.is_locked):<8} {str(s.is_demucs_done):<8} "
            f"{str(s.is_normalized):<6} {s.duration:.1f}s"
        )
    click.echo(t("cli.list.total", count=len(songs)))


@main.command()
@click.option("--playlist", type=click.Path(exists=True),
              help=t("cli.process.playlist_help"))
@click.option("--step", default=None,
              help=t("cli.process.step_help"))
@click.option("--song-store", default=None,
              help=t("cli.process.song_store_help"))
@click.option("--target-format", default="mp3",
              help=t("cli.process.target_format_help"))
def process(playlist, step, song_store, target_format):
    """Run the pipeline on a playlist."""
    song_path = song_store or _get_default_path("songs.csv")
    pl_path = playlist or _get_default_path("playlists.csv")
    workspace = _get_workspace()

    song_store_obj = SongStore(song_path)
    pl_store = PlaylistStore(pl_path)
    task_store = TaskStore(_get_default_path("tasks.csv"))

    # Determine which songs to process
    if playlist:
        playlist_name = os.path.splitext(os.path.basename(playlist))[0]
        entries = pl_store.get_by_playlist(playlist_name)
        song_ids = [e.song_id for e in entries]
        songs = song_store_obj.get_by_ids(song_ids)
        click.echo(t("cli.process.playlist_info", name=playlist_name, count=len(songs)))
    else:
        songs = song_store_obj.get_all()
        playlist_name = "all"
        click.echo(t("cli.process.all_songs", count=len(songs)))

    if not songs:
        click.echo(t("cli.process.no_songs"))
        return

    # Build pipeline
    all_steps = {
        "unlock": UnlockStep(),
        "decode": DecodeStep(),
        "transcode": TranscodeStep(target_format=target_format),
        "demucs": DemucsStep(),
        "normalize": NormalizeStep(),
        "export": ExportStep(target_format=target_format),
    }

    if step:
        if step not in all_steps:
            click.echo(
                t("cli.process.unknown_step", step=step,
                  available=", ".join(all_steps.keys())),
                err=True,
            )
            sys.exit(1)
        steps = [all_steps[step]]
    else:
        steps = [
            all_steps["unlock"],
            all_steps["decode"],
            all_steps["transcode"],
            all_steps["demucs"],
            all_steps["normalize"],
            all_steps["export"],
        ]

    engine = PipelineEngine(song_store_obj, task_store, workspace)
    click.echo(t("cli.process.running", count=len(steps)))
    result = engine.run(steps, songs, playlist_name=playlist_name)

    done = sum(1 for s in result if s.status == SongStatus.DONE or s.status == SongStatus.PROCESSING)
    failed = sum(1 for s in result if s.status == SongStatus.FAILED)
    click.echo(t("cli.process.done_failed", done=done, failed=failed))


@main.command()
@click.option("--input", "input_csv", type=click.Path(exists=True),
              help=t("cli.demucs.input_help"))
@click.option("--song-store", default=None,
              help=t("cli.demucs.song_store_help"))
def demucs(input_csv, song_store):
    """Run Demucs source separation on songs."""
    song_path = song_store or _get_default_path("songs.csv")
    song_store_obj = SongStore(song_path)
    task_store = TaskStore(_get_default_path("tasks.csv"))

    songs = _load_songs(input_csv, song_store_obj)
    if not songs:
        click.echo(t("cli.list.empty"))
        return

    engine = PipelineEngine(song_store_obj, task_store, _get_workspace())
    step = DemucsStep()
    click.echo(t("cli.demucs.running", count=len(songs)))
    result = engine.run_single_step(step, songs)
    click.echo(t("cli.demucs.processed", count=len(result)))


@main.command()
@click.option("--input", "input_csv", type=click.Path(exists=True),
              help=t("cli.normalize.input_help"))
@click.option("--song-store", default=None,
              help=t("cli.normalize.song_store_help"))
@click.option("--lufs", default=-14.0, type=float,
              help=t("cli.normalize.lufs_help"))
def normalize(input_csv, song_store, lufs):
    """Run loudness normalization on songs."""
    song_path = song_store or _get_default_path("songs.csv")
    song_store_obj = SongStore(song_path)
    task_store = TaskStore(_get_default_path("tasks.csv"))

    songs = _load_songs(input_csv, song_store_obj)
    if not songs:
        click.echo(t("cli.list.empty"))
        return

    engine = PipelineEngine(song_store_obj, task_store, _get_workspace())
    step = NormalizeStep(target_lufs=lufs)
    click.echo(t("cli.normalize.running", count=len(songs), lufs=lufs))
    result = engine.run_single_step(step, songs)
    click.echo(t("cli.normalize.processed", count=len(result)))


@main.command()
@click.option("--playlist", type=click.Path(exists=True),
              help=t("cli.export.playlist_help"))
@click.option("--format", "output_format", default="mp3",
              help=t("cli.export.format_help"))
@click.option("--song-store", default=None,
              help=t("cli.export.song_store_help"))
def export(playlist, output_format, song_store):
    """Export a playlist to a single audio file."""
    song_path = song_store or _get_default_path("songs.csv")
    pl_path = playlist or _get_default_path("playlists.csv")
    workspace = _get_workspace()

    song_store_obj = SongStore(song_path)
    pl_store = PlaylistStore(pl_path)
    task_store = TaskStore(_get_default_path("tasks.csv"))

    playlist_name = os.path.splitext(os.path.basename(pl_path))[0]
    entries = pl_store.get_by_playlist(playlist_name)
    song_ids = [e.song_id for e in entries]
    songs = song_store_obj.get_by_ids(song_ids)

    if not songs:
        click.echo(t("cli.export.no_songs", name=playlist_name))
        return

    engine = PipelineEngine(song_store_obj, task_store, workspace)
    step = ExportStep(target_format=output_format)
    click.echo(t("cli.export.exporting", name=playlist_name, count=len(songs),
                 format=output_format))
    engine.run_single_step(step, songs)
    click.echo(t("cli.export.complete", name=playlist_name, format=output_format))


@main.command()
@click.option("--store", default=None, help=t("cli.tasks.store_help"))
@click.option("--status", default=None,
              help=t("cli.tasks.status_help"))
def tasks(store, status):
    """List tasks and their statuses."""
    task_path = store or _get_default_path("tasks.csv")
    task_store = TaskStore(task_path)

    if status:
        try:
            st = TaskStatus(status)
            tasks_list = task_store.get_by_status(st)
        except ValueError:
            click.echo(t("cli.tasks.invalid_status", status=status), err=True)
            sys.exit(1)
    else:
        tasks_list = task_store.get_all()

    if not tasks_list:
        click.echo(t("cli.tasks.empty"))
        return

    hid = t("cli.tasks.header_id")
    hty = t("cli.tasks.header_type")
    hst = t("cli.tasks.header_status")
    hpr = t("cli.tasks.header_progress")
    her = t("cli.tasks.header_error")

    click.echo(f"{hid:<14} {hty:<16} {hst:<10} {hpr:<10} {her}")
    click.echo("-" * 80)
    for tk in tasks_list:
        err = tk.error[:40] if tk.error else "-"
        click.echo(f"{tk.task_id:<14} {tk.type:<16} {tk.status.value:<10} {tk.progress}%{'':<6} {err}")
    click.echo(t("cli.tasks.total", count=len(tasks_list)))


def _load_songs(csv_path, song_store):
    if csv_path:
        temp_store = SongStore(csv_path)
        return temp_store.get_all()
    return song_store.get_all()


if __name__ == "__main__":
    main()
