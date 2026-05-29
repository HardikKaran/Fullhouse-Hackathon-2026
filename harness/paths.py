"""Engine bootstrap for the harness.

Puts the vendored Fullhouse engine on sys.path so `from engine.game import ...`
and `from sandbox.match import run_match` resolve, then re-exports the engine's
own constants and the canonical bot file paths. Import this module before any
direct `engine` / `sandbox` import — callers should never need PYTHONPATH hacks.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR = REPO_ROOT / "vendor" / "fullhouse-engine"

if not VENDOR.exists():
    raise RuntimeError(
        f"Vendored engine not found at {VENDOR}.\n"
        "Run: git submodule update --init --recursive"
    )

# Vendor the *whole* repo (not just engine/): sandbox/match.py launches each bot
# by file path via a sibling sandbox/runner.py, so runner.py must stay next to it.
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

# Pull constants from the engine — never hardcode blind sizes here.
from engine.game import BIG_BLIND, SMALL_BLIND, STARTING_STACK  # noqa: E402
from sandbox.match import run_match  # noqa: E402,F401  (re-exported)

# Hero (our bot) and the reference bots, by absolute path.
HERO = REPO_ROOT / "src" / "mybot" / "bot.py"

_BOTS_DIR = VENDOR / "bots"
REFERENCE_BOTS = {
    name: _BOTS_DIR / name / "bot.py"
    for name in ("template", "aggressor", "mathematician", "shark", "ref_bot_2")
}


def run_match_check():
    """Acceptance probe: prove the engine is importable from the submodule and
    that every bot path resolves. Prints the engine constants and raises if
    anything is missing."""
    print(
        f"engine import OK — SMALL_BLIND={SMALL_BLIND}, BIG_BLIND={BIG_BLIND}, "
        f"STARTING_STACK={STARTING_STACK}"
    )
    print(f"run_match resolved: {run_match.__module__}.{run_match.__name__}")
    print(f"HERO: {HERO}  (exists={HERO.exists()})")
    missing = [n for n, p in REFERENCE_BOTS.items() if not p.exists()]
    print(f"reference bots: {len(REFERENCE_BOTS)}  missing={missing}")
    if not HERO.exists():
        raise RuntimeError(f"Hero bot not found at {HERO}")
    if missing:
        raise RuntimeError(f"Missing reference bots: {missing}")
