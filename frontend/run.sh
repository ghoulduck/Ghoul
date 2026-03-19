#!/usr/bin/env bash
# run.sh — Compile and launch the Ghoul Java Swing frontend.
#
# Usage:
#   cd frontend/
#   ./run.sh
#
# Or from the project root:
#   bash frontend/run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Compiling GhoulUI.java…"
javac GhoulUI.java

echo "Launching Ghoul UI…"
java GhoulUI
