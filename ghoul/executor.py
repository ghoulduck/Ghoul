"""
ghoul/executor.py — Code Executor.

Executes generated Python code in a subprocess.
Captures stdout, stderr, return code, and execution time.
No sandboxing, no restrictions.
"""

import subprocess
import tempfile
import time
from pathlib import Path


def execute_code(code: str) -> dict:
    """
    Execute a Python code string.

    Writes the code to a temporary file, runs it with the system Python
    interpreter, and returns a result dict with keys:
        stdout      (str)
        stderr      (str)
        returncode  (int)
        duration    (float)  — seconds
        success     (bool)
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    return execute_file(tmp_path, cleanup=True)


def execute_file(path: str | Path, cleanup: bool = False) -> dict:
    """
    Execute a Python file at *path*.

    Returns a result dict identical to :func:`execute_code`.
    """
    path = str(path)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            ["python", path],
            capture_output=True,
            text=True,
        )
        duration = time.monotonic() - start
        result = {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
            "duration": round(duration, 4),
            "success": proc.returncode == 0,
        }
    except Exception as exc:
        duration = time.monotonic() - start
        result = {
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "duration": round(duration, 4),
            "success": False,
        }
    finally:
        if cleanup:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

    return result
