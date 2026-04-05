#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export COPYFILE_DISABLE=1

echo "=== skill-facets runtime bootstrap ==="
echo "Project .claude: $SCRIPT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: cannot find Python interpreter: $PYTHON_BIN" >&2
  exit 2
fi

if [ ! -f "$REQ_FILE" ]; then
  echo "ERROR: missing requirements file: $REQ_FILE" >&2
  exit 2
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "[1/3] Creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  echo "[1/3] Reusing existing virtual environment at $VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python"

echo "[1.5/3] Cleaning macOS metadata files inside virtualenv"
find "$VENV_DIR" -name '._*' -delete

echo "[2/3] Upgrading pip/setuptools/wheel"
"$VENV_PY" -m pip install --upgrade pip setuptools wheel

echo "[3/3] Installing runtime dependencies"
"$VENV_PY" -m pip install -r "$REQ_FILE"

echo
echo "Bootstrap complete."
echo "Project Python: $VENV_PY"
echo "Next steps:"
echo "  1. Run: $VENV_PY $SCRIPT_DIR/scripts/doctor.py"
echo "  2. Register the hook with this interpreter in .claude/settings.local.json"
