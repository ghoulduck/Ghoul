#!/usr/bin/env python3
"""
build.py — Master build orchestration script for Ghoul.

Builds:
  1. Python standalone executable via PyInstaller.
  2. Java Swing frontend fat JAR via Gradle Shadow.
  3. (Optional) Native installer via jpackage.

Usage:
    python build.py                  # build everything
    python build.py --python-only    # build only the Python EXE
    python build.py --java-only      # build only the Java JAR
    python build.py --installer      # also run jpackage for native installer
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent


def run(cmd: list[str], cwd: Path | None = None, label: str = "") -> bool:
    """Run a command, print status, and return True on success."""
    display = " ".join(cmd)
    print(f"\n{'='*60}")
    print(f"[Build] {label or display}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    if result.returncode != 0:
        print(f"[Build] ✗ FAILED (rc={result.returncode}): {display}")
        return False
    print(f"[Build] ✓ {label or 'Done'}")
    return True


def check_tool(name: str) -> bool:
    """Check if a command-line tool is available."""
    return shutil.which(name) is not None


# ---------------------------------------------------------------------------
# Python build
# ---------------------------------------------------------------------------

def build_python() -> bool:
    """Build a standalone Python executable with PyInstaller."""
    if not check_tool("pyinstaller"):
        print("[Build] pyinstaller not found. Install with: pip install pyinstaller")
        return False

    return run(
        ["pyinstaller", "ghoul.spec", "--noconfirm"],
        label="Building Python executable with PyInstaller",
    )


# ---------------------------------------------------------------------------
# Java build
# ---------------------------------------------------------------------------

def build_java_jar() -> bool:
    """Build the Java Swing frontend as a fat JAR using Gradle Shadow."""
    gradle_cmd = "gradlew" if check_tool("gradlew") else "gradle"
    if not check_tool(gradle_cmd):
        # Try the wrapper
        wrapper = ROOT / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
        if wrapper.exists():
            gradle_cmd = str(wrapper)
        else:
            print("[Build] Gradle not found. Install Gradle or add a Gradle wrapper.")
            return False

    return run(
        [gradle_cmd, "shadowJar"],
        label="Building Java fat JAR with Gradle Shadow",
    )


def build_native_installer() -> bool:
    """Build a native installer using jpackage (requires JDK 14+)."""
    gradle_cmd = "gradlew" if check_tool("gradlew") else "gradle"
    if not check_tool(gradle_cmd):
        wrapper = ROOT / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
        if wrapper.exists():
            gradle_cmd = str(wrapper)
        else:
            print("[Build] Gradle not found.")
            return False

    return run(
        [gradle_cmd, "jpackageImage"],
        label="Building native installer with jpackage",
    )


# ---------------------------------------------------------------------------
# Direct Java compilation (fallback if Gradle is not available)
# ---------------------------------------------------------------------------

def build_java_direct() -> bool:
    """Compile GhoulUI.java directly with javac (no Gradle needed)."""
    if not check_tool("javac"):
        print("[Build] javac not found. Install a JDK (11+).")
        return False

    frontend_dir = ROOT / "frontend"
    return run(
        ["javac", "GhoulUI.java"],
        cwd=frontend_dir,
        label="Compiling GhoulUI.java with javac",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ghoul master build script.",
    )
    parser.add_argument(
        "--python-only", action="store_true", help="Build only the Python executable."
    )
    parser.add_argument(
        "--java-only", action="store_true", help="Build only the Java frontend."
    )
    parser.add_argument(
        "--installer", action="store_true", help="Also build a native installer."
    )
    parser.add_argument(
        "--no-gradle",
        action="store_true",
        help="Compile Java directly with javac instead of using Gradle.",
    )
    args = parser.parse_args()

    success = True

    if not args.java_only:
        if not build_python():
            success = False

    if not args.python_only:
        if args.no_gradle:
            if not build_java_direct():
                success = False
        else:
            if not build_java_jar():
                success = False

        if args.installer:
            if not build_native_installer():
                success = False

    print(f"\n{'='*60}")
    if success:
        print("[Build] All builds completed successfully ✓")
    else:
        print("[Build] Some builds failed — see output above.")
    print(f"{'='*60}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
