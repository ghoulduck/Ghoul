"""
ghoul/backup.py — Timestamped ZIP snapshots of source and sessions.

Creates ZIP archives of the Ghoul source code and session data before
any self-modification or on demand. Backups are stored in a ``backups/``
directory at the project root.
"""

import time
import zipfile
from pathlib import Path

from ghoul.config import CFG


_ROOT = Path(__file__).parent.parent  # project root


def _default_backup_dir() -> Path:
    """Return (and create) the default backup directory."""
    backup_dir = _ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_backup(
    label: str = "manual",
    include_source: bool = True,
    include_sessions: bool = True,
    backup_dir: Path | None = None,
) -> Path:
    """
    Create a timestamped ZIP snapshot.

    Parameters
    ----------
    label:            Short label included in the filename (e.g. ``pre_improve``).
    include_source:   Include ``ghoul/`` Python source files.
    include_sessions: Include session data from the configured data directory.
    backup_dir:       Override the backup destination directory.

    Returns
    -------
    Path to the newly created ZIP file.
    """
    backup_dir = backup_dir or _default_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    zip_name = f"ghoul_backup_{label}_{timestamp}.zip"
    zip_path = backup_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if include_source:
            _add_source(zf)
        if include_sessions:
            _add_sessions(zf)

    return zip_path


def _add_source(zf: zipfile.ZipFile) -> None:
    """Add all Python source files from the ``ghoul/`` package."""
    ghoul_dir = _ROOT / "ghoul"
    for py_file in ghoul_dir.glob("*.py"):
        arcname = f"ghoul/{py_file.name}"
        zf.write(py_file, arcname)

    # Also include main.py
    main_py = _ROOT / "main.py"
    if main_py.exists():
        zf.write(main_py, "main.py")


def _add_sessions(zf: zipfile.ZipFile) -> None:
    """Add all session JSON files from the data directory."""
    data_dir: Path = CFG["data_dir"]
    if not data_dir.exists():
        return
    for json_file in data_dir.glob("*.json"):
        arcname = f"data/{json_file.name}"
        zf.write(json_file, arcname)


def list_backups(backup_dir: Path | None = None) -> list[Path]:
    """List all backup ZIP files, sorted newest first."""
    backup_dir = backup_dir or _default_backup_dir()
    if not backup_dir.exists():
        return []
    backups = sorted(backup_dir.glob("ghoul_backup_*.zip"), reverse=True)
    return backups
