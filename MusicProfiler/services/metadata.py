import subprocess
import os
import json
from typing import Optional


class MetadataService:
    """Reads/writes audio metadata via ffprobe/ffmpeg."""

    def __init__(self, ffprobe_bin: str = "ffprobe", ffmpeg_bin: str = "ffmpeg"):
        self.ffprobe = ffprobe_bin
        self.ffmpeg = ffmpeg_bin

    def _run(self, args: list[str], timeout: int = 60) -> dict:
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": result.stderr if result.returncode != 0 else "",
            }
        except FileNotFoundError:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "error": f"Executable not found: {args[0]}",
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "error": f"Timeout after {timeout}s",
            }

    def read(self, filepath: str) -> dict:
        """Read audio file metadata as a structured dict."""
        if not os.path.exists(filepath):
            return {"success": False, "error": f"File not found: {filepath}"}

        args = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            filepath,
        ]
        result = self._run(args)
        if result["success"]:
            try:
                data = json.loads(result["stdout"])
                result["metadata"] = self._flatten_metadata(data)
            except json.JSONDecodeError:
                result["metadata"] = {}
        return result

    def _flatten_metadata(self, raw: dict) -> dict:
        """Extract key fields from ffprobe JSON output."""
        fmt = raw.get("format", {})
        streams = raw.get("streams", [])
        audio_stream = None
        for s in streams:
            if s.get("codec_type") == "audio":
                audio_stream = s
                break

        return {
            "duration": float(fmt.get("duration", 0)),
            "bitrate": int(fmt.get("bit_rate", 0) or 0),
            "format_name": fmt.get("format_name", ""),
            "codec": audio_stream.get("codec_name", "") if audio_stream else "",
            "sample_rate": int(audio_stream.get("sample_rate", 0) or 0) if audio_stream else 0,
            "channels": int(audio_stream.get("channels", 0) or 0) if audio_stream else 0,
            "tags": fmt.get("tags", {}),
        }

    def write_tags(self, filepath: str, tags: dict[str, str], output_path: Optional[str] = None) -> dict:
        """Write metadata tags to an audio file. Writes to a new file if output_path given."""
        if not os.path.exists(filepath):
            return {"success": False, "error": f"File not found: {filepath}"}

        target = output_path or filepath
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)

        args = [self.ffmpeg, "-y", "-i", filepath]
        for key, value in tags.items():
            args.extend(["-metadata", f"{key}={value}"])
        args.extend(["-acodec", "copy", target])

        result = self._run(args)
        result["output_path"] = target if result["success"] else ""
        return result
