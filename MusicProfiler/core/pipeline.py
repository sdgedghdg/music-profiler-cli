from abc import ABC, abstractmethod
import os
import logging
from typing import Optional

from ..i18n import t
from ..models.song import Song, SongStatus
from ..services.ffmpeg import FFmpegService
from ..services.demucs import DemucsService
from ..services.unlock import UnlockService
from ..services.metadata import MetadataService

logger = logging.getLogger(__name__)


class PipelineStep(ABC):
    """Base class for all pipeline steps. Each step does exactly one thing."""

    name: str = "base"

    @abstractmethod
    def run(self, songs: list[Song], context: dict) -> list[Song]:
        """Process a batch of songs. Returns the modified list.

        Args:
            songs: Input songs to process.
            context: Shared context dict with paths, config, etc.
                Expected keys:
                - workspace_raw: path to raw workspace
                - workspace_processed: path to processed workspace
                - workspace_output: path to output workspace
                - progress_callback: optional callable(step_name, current, total)

        Returns:
            Modified list of songs after this step.
        """
        ...

    def report_progress(self, context: dict, current: int, total: int):
        cb = context.get("progress_callback")
        if cb:
            cb(self.name, current, total)


class UnlockStep(PipelineStep):
    """Decrypt locked audio files (ncm/qmc/kgm)."""

    name = "unlock"

    def __init__(self, unlock_service: Optional[UnlockService] = None):
        self.unlock = unlock_service or UnlockService()

    def run(self, songs: list[Song], context: dict) -> list[Song]:
        raw_dir = context["workspace_raw"]
        locked = [s for s in songs if s.is_locked]

        for i, song in enumerate(locked):
            self.report_progress(context, i + 1, len(locked))
            result = self.unlock.unlock(song.path, raw_dir)

            if result["success"]:
                out_path = result["output_path"]
                out_ext = os.path.splitext(out_path)[1].lstrip(".")
                song.path = out_path
                song.format = out_ext
                song.is_locked = False
                song.status = SongStatus.PROCESSING
                logger.info(t("pipeline.unlock.success", title=song.title, path=out_path))
            else:
                song.status = SongStatus.FAILED
                logger.error(t("pipeline.unlock.failed", title=song.title, error=result['error']))

        return songs


class DecodeStep(PipelineStep):
    """Decode audio to a standard PCM intermediate format."""

    name = "decode"

    def __init__(self, ffmpeg_service: Optional[FFmpegService] = None):
        self.ffmpeg = ffmpeg_service or FFmpegService()

    def run(self, songs: list[Song], context: dict) -> list[Song]:
        raw_dir = context["workspace_raw"]
        to_decode = [s for s in songs if s.status != SongStatus.FAILED]

        for i, song in enumerate(to_decode):
            self.report_progress(context, i + 1, len(to_decode))
            out_path = os.path.join(raw_dir, f"{song.id}_decoded.wav")

            result = self.ffmpeg.extract_audio(song.path, out_path, codec="pcm_s16le")
            if result["success"]:
                song.path = out_path
                song.format = "wav"
                logger.info(t("pipeline.decode.success", title=song.title, path=out_path))
            else:
                song.status = SongStatus.FAILED
                logger.error(t("pipeline.decode.failed", title=song.title, error=result['error']))

        return songs


class TranscodeStep(PipelineStep):
    """Transcode audio to target format (e.g. mp3)."""

    name = "transcode"

    def __init__(self, ffmpeg_service: Optional[FFmpegService] = None,
                 target_format: str = "mp3", bitrate: str = "320k"):
        self.ffmpeg = ffmpeg_service or FFmpegService()
        self.target_format = target_format
        self.bitrate = bitrate

    def run(self, songs: list[Song], context: dict) -> list[Song]:
        processed_dir = context["workspace_processed"]
        to_transcode = [s for s in songs if s.status != SongStatus.FAILED]

        for i, song in enumerate(to_transcode):
            self.report_progress(context, i + 1, len(to_transcode))
            out_path = os.path.join(processed_dir, f"{song.id}.{self.target_format}")

            codec_map = {"mp3": "libmp3lame", "aac": "aac", "flac": "flac", "wav": "pcm_s16le"}
            codec = codec_map.get(self.target_format, "libmp3lame")

            result = self.ffmpeg.transcode(
                song.path, out_path, codec=codec, bitrate=self.bitrate,
            )
            if result["success"]:
                song.path = out_path
                song.format = self.target_format
                logger.info(t("pipeline.transcode.success", title=song.title, path=out_path))
            else:
                song.status = SongStatus.FAILED
                logger.error(t("pipeline.transcode.failed", title=song.title, error=result['error']))

        return songs


class DemucsStep(PipelineStep):
    """Source separation via Demucs."""

    name = "demucs"

    def __init__(self, demucs_service: Optional[DemucsService] = None, model: str = "htdemucs"):
        self.demucs = demucs_service or DemucsService(model=model)

    def run(self, songs: list[Song], context: dict) -> list[Song]:
        processed_dir = context["workspace_processed"]
        to_separate = [s for s in songs
                       if s.status != SongStatus.FAILED and not s.is_demucs_done]

        for i, song in enumerate(to_separate):
            self.report_progress(context, i + 1, len(to_separate))
            result = self.demucs.separate(song.path, processed_dir, two_stems="vocals")

            if result["success"]:
                song.is_demucs_done = True
                logger.info(t("pipeline.demucs.success", title=song.title, path=result.get('stem_dir', '')))
            else:
                logger.error(t("pipeline.demucs.failed", title=song.title, error=result['error']))

        return songs


class NormalizeStep(PipelineStep):
    """EBU R128 loudness normalization."""

    name = "normalize"

    def __init__(self, ffmpeg_service: Optional[FFmpegService] = None,
                 target_lufs: float = -14.0):
        self.ffmpeg = ffmpeg_service or FFmpegService()
        self.target_lufs = target_lufs

    def run(self, songs: list[Song], context: dict) -> list[Song]:
        processed_dir = context["workspace_processed"]
        to_normalize = [s for s in songs
                        if s.status != SongStatus.FAILED and not s.is_normalized]

        for i, song in enumerate(to_normalize):
            self.report_progress(context, i + 1, len(to_normalize))
            base, ext = os.path.splitext(os.path.basename(song.path))
            out_path = os.path.join(processed_dir, f"{song.id}_norm{ext}")

            result = self.ffmpeg.loudnorm(song.path, out_path, target_lufs=self.target_lufs)
            if result["success"]:
                song.path = out_path
                song.is_normalized = True
                logger.info(t("pipeline.normalize.success", title=song.title, path=out_path))
            else:
                logger.error(t("pipeline.normalize.failed", title=song.title, error=result['error']))

        return songs


class ExportStep(PipelineStep):
    """Export songs: concatenate playlist into a single export file."""

    name = "export"

    def __init__(self, ffmpeg_service: Optional[FFmpegService] = None,
                 target_format: str = "mp3"):
        self.ffmpeg = ffmpeg_service or FFmpegService()
        self.target_format = target_format

    def run(self, songs: list[Song], context: dict) -> list[Song]:
        output_dir = context["workspace_output"]
        playlist_name = context.get("playlist_name", "export")
        to_export = [s for s in songs if s.status != SongStatus.FAILED]

        if not to_export:
            logger.warning(t("pipeline.export.empty"))
            return songs

        # If only one song, just copy/transcode it
        if len(to_export) == 1:
            song = to_export[0]
            out_path = os.path.join(output_dir, f"{playlist_name}.{self.target_format}")
            result = self.ffmpeg.transcode(song.path, out_path)
            if result["success"]:
                logger.info(t("pipeline.export.success", path=out_path))
            else:
                logger.error(t("pipeline.export.failed", error=result['error']))
            return songs

        # Multiple songs: concatenate
        input_paths = [s.path for s in to_export]
        out_path = os.path.join(output_dir, f"{playlist_name}.{self.target_format}")

        result = self.ffmpeg.concat(input_paths, out_path)
        if result["success"]:
            logger.info(t("pipeline.export.concat_success", path=out_path))
        else:
            logger.error(t("pipeline.export.concat_failed", error=result['error']))

        return songs
