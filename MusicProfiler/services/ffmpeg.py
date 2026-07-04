import subprocess
import os
from typing import Optional


class FFmpegService:
    """Wraps FFmpeg subprocess calls. Returns structured dicts only."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
        self.ffmpeg = ffmpeg_bin
        self.ffprobe = ffprobe_bin

    def _run(self, args: list[str], timeout: int = 600) -> dict:
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

    def probe(self, filepath: str) -> dict:
        """Get audio file metadata via ffprobe."""
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
            import json
            try:
                result["metadata"] = json.loads(result["stdout"])
            except json.JSONDecodeError:
                result["metadata"] = {}
        return result

    def get_duration(self, filepath: str) -> dict:
        """Get audio duration in seconds."""
        probe_result = self.probe(filepath)
        if not probe_result["success"]:
            return probe_result

        metadata = probe_result.get("metadata", {})
        fmt = metadata.get("format", {})
        duration = float(fmt.get("duration", 0))
        return {"success": True, "duration": duration, "error": ""}

    def transcode(self, input_path: str, output_path: str,
                  codec: str = "libmp3lame", bitrate: str = "320k",
                  sample_rate: int = 44100) -> dict:
        """Transcode audio to target format."""
        if not os.path.exists(input_path):
            return {"success": False, "error": f"Input not found: {input_path}"}

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        args = [
            self.ffmpeg,
            "-y",
            "-i", input_path,
            "-acodec", codec,
            "-b:a", bitrate,
            "-ar", str(sample_rate),
            output_path,
        ]
        result = self._run(args)
        result["output_path"] = output_path if result["success"] else ""
        return result

    def loudnorm(self, input_path: str, output_path: str,
                 target_lufs: float = -14.0, true_peak: float = -1.0) -> dict:
        """Apply EBU R128 loudness normalization."""
        if not os.path.exists(input_path):
            return {"success": False, "error": f"Input not found: {input_path}"}

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        args = [
            self.ffmpeg,
            "-y",
            "-i", input_path,
            "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11:linear=true:print_format=json",
            output_path,
        ]
        result = self._run(args)
        result["output_path"] = output_path if result["success"] else ""
        return result

    def concat(self, input_paths: list[str], output_path: str) -> dict:
        """Concatenate multiple audio files using the concat demuxer."""
        if not input_paths:
            return {"success": False, "error": "No input files provided"}

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        concat_list = output_path + ".concat.txt"
        try:
            with open(concat_list, "w") as f:
                for p in input_paths:
                    f.write(f"file '{os.path.abspath(p)}'\n")

            args = [
                self.ffmpeg,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                output_path,
            ]
            result = self._run(args)
            result["output_path"] = output_path if result["success"] else ""
            return result
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)

    def extract_audio(self, input_path: str, output_path: str,
                      codec: str = "pcm_s16le") -> dict:
        """Extract raw audio stream."""
        if not os.path.exists(input_path):
            return {"success": False, "error": f"Input not found: {input_path}"}

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        args = [
            self.ffmpeg,
            "-y",
            "-i", input_path,
            "-acodec", codec,
            "-vn",
            output_path,
        ]
        result = self._run(args)
        result["output_path"] = output_path if result["success"] else ""
        return result
