import subprocess
import os
from typing import Optional


class DemucsService:
    """Wraps Demucs (source separation) subprocess calls."""

    def __init__(self, demucs_bin: str = "demucs", model: str = "htdemucs"):
        self.demucs = demucs_bin
        self.model = model

    def _run(self, args: list[str], timeout: int = 3600) -> dict:
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
                "error": f"Executable not found: demucs",
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "error": f"Timeout after {timeout}s",
            }

    def separate(self, input_path: str, output_dir: str,
                 model: Optional[str] = None,
                 two_stems: Optional[str] = None) -> dict:
        """Run Demucs source separation on an audio file.

        Args:
            input_path: Path to input audio file.
            output_dir: Directory for separated output.
            model: Override the default model.
            two_stems: If set (e.g. 'vocals'), outputs only two stems.
        """
        if not os.path.exists(input_path):
            return {"success": False, "error": f"Input not found: {input_path}"}

        os.makedirs(output_dir, exist_ok=True)

        args = [
            self.demucs,
            "-n", model or self.model,
            "-o", output_dir,
        ]
        if two_stems:
            args.extend(["--two-stems", two_stems])

        args.append(input_path)
        result = self._run(args)

        stem_dir = os.path.join(
            output_dir, model or self.model,
            os.path.splitext(os.path.basename(input_path))[0],
        )
        result["stem_dir"] = stem_dir if result["success"] and os.path.isdir(stem_dir) else ""
        return result

    def separate_batch(self, input_paths: list[str], output_dir: str,
                       model: Optional[str] = None) -> dict:
        """Run Demucs on multiple files."""
        results = []
        for path in input_paths:
            results.append(self.separate(path, output_dir, model))

        all_ok = all(r["success"] for r in results)
        return {
            "success": all_ok,
            "results": results,
            "error": "" if all_ok else "One or more separations failed",
        }
