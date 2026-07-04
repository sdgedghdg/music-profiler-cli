import subprocess
import os
import glob
from typing import Optional


class UnlockService:
    """Wraps the ``um`` (Unlock Music) CLI binary for decrypting encrypted
    audio formats from Chinese music platforms.

    Supported formats (all handled by a single ``um`` call):
    ncm, qmc0/qmc3/qmcflac/qmcogg, kgm/kgg, kwm, tm, xm, x2m/x3m

    Download: https://git.unlock-music.dev/um/cli/releases
    """

    SUPPORTED_EXTENSIONS = {
        "ncm", "qmc0", "qmc3", "qmcflac", "qmcogg", "qmcmp3",
        "kgm", "kgg", "kwm", "tm", "xm", "x2m", "x3m",
    }

    def __init__(self, um_bin: str = "um"):
        self.um_bin = um_bin

    def _run(self, args: list[str], timeout: int = 300) -> dict:
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

    def detect_format(self, filepath: str) -> str:
        """Detect encrypted format from file extension."""
        ext = os.path.splitext(filepath)[1].lower().lstrip(".")
        return ext if ext in self.SUPPORTED_EXTENSIONS else ""

    def is_locked(self, filepath: str) -> bool:
        """Check if a file appears to be an encrypted format."""
        return self.detect_format(filepath) != ""

    def unlock(self, input_path: str, output_dir: str) -> dict:
        """Decrypt a single audio file using ``um``.

        Args:
            input_path: Path to the encrypted file.
            output_dir: Directory to write the decrypted file into.
                ``um`` auto-names the output based on the original filename
                with the correct audio extension (detected via header sniff).

        Returns:
            dict with keys: success, output_path, error, format
        """
        if not os.path.exists(input_path):
            return {
                "success": False,
                "error": f"Input not found: {input_path}",
                "output_path": "",
                "format": "",
            }

        fmt = self.detect_format(input_path)
        if not fmt:
            return {
                "success": False,
                "error": f"Unsupported encrypted format: {input_path}",
                "output_path": "",
                "format": "",
            }

        os.makedirs(output_dir, exist_ok=True)
        args = [self.um_bin, "-i", input_path, "-o", output_dir, "--overwrite"]

        result = self._run(args)
        result["format"] = fmt

        if result["success"]:
            # um strips the encrypted suffix and replaces it with the sniffed
            # audio extension. Find the output file.
            base = os.path.splitext(os.path.basename(input_path))[0]
            actual_path = self._find_output(output_dir, base)
            result["output_path"] = actual_path
            if not actual_path:
                result["success"] = False
                result["error"] = "Unlock succeeded but output file not found"
        else:
            result["output_path"] = ""

        return result

    def _find_output(self, output_dir: str, basename: str) -> str:
        """Find the output file produced by ``um`` in *output_dir*.

        ``um`` produces: ``<basename>.<audio_ext>`` where audio_ext is sniffed
        from the decrypted header (flac, mp3, ogg, wav, etc.).
        """
        for ext in ("flac", "mp3", "ogg", "wav", "m4a", "wma", "ape"):
            candidate = os.path.join(output_dir, f"{basename}.{ext}")
            if os.path.exists(candidate):
                return candidate
        # fallback: glob for anything starting with the basename
        pattern = os.path.join(output_dir, f"{basename}.*")
        matches = glob.glob(pattern)
        return matches[0] if matches else ""
