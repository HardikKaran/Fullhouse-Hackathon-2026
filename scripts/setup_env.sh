#!/usr/bin/env bash
#
# One-shot dev-environment setup for the Fullhouse poker-bot harness.
# Produces a CPython 3.10 .venv with the engine's runtime deps + eval7.
#
# Why 3.10 (not the system 3.11/3.12): eval7==0.1.7 ships pre-generated Cython
# C that references longintrepr.h, removed in CPython 3.11. It only builds on
# 3.10. The tournament sandbox pins python:3.10-slim, so we match it.
#
# Why uv (resolves PLAN §10): this machine has no python3.10 and no passwordless
# sudo to apt-get the CPython build deps (libffi/sqlite/...). A source build via
# pyenv would yield a crippled interpreter (no _ctypes/sqlite3). uv downloads a
# *prebuilt* standalone 3.10 with every stdlib C module intact — no compiler,
# no sudo. If you instead have a system python3.10 on PATH, this script uses it.
#
# eval7 needs a two-step install: Cython<3 first, then eval7 with
# --no-build-isolation so it compiles against that Cython (not Cython 3).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY_VERSION="3.10"
VENV=".venv"

# --- locate uv (preferred) or a system python3.10 ---------------------------
find_uv() {
    if command -v uv >/dev/null 2>&1; then command -v uv; return 0; fi
    for c in "$HOME/.local/bin/uv" "$HOME"/snap/code/*/.local/bin/uv; do
        [ -x "$c" ] && { echo "$c"; return 0; }
    done
    return 1
}

if UV="$(find_uv)"; then
    echo ">> Using uv at: $UV"
    "$UV" python install "$PY_VERSION"
    # --seed installs pip/setuptools so the eval7 two-step works with plain pip.
    "$UV" venv --python "$PY_VERSION" --seed "$VENV"
elif command -v python3.10 >/dev/null 2>&1; then
    echo ">> Using system python3.10 ($(command -v python3.10))"
    python3.10 -m venv "$VENV"
else
    echo "ERROR: need Python 3.10. Install uv (https://astral.sh/uv) or python3.10." >&2
    exit 1
fi

# --- install deps into the venv ---------------------------------------------
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip
pip install "Cython<3"
pip install --no-build-isolation eval7==0.1.7
pip install -r requirements-dev.txt

echo ""
echo ">> done. activate with:  source $VENV/bin/activate"
python -c "import eval7; print('eval7 OK', eval7.__file__)"
python -c "import numpy, scipy, treys, sklearn; print('deps OK')"
