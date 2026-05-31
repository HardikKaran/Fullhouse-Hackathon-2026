"""Test bootstrap for the mybot package + custom marks.

The repo-root conftest.py only puts the repo root on sys.path (so `import
harness` works). The bot package lives under ``src/mybot``, so add ``src`` here
too -- this is the single place tests need for ``from mybot.hand_eval import``.
``mybot`` has no ``__init__.py`` on purpose (the engine loads bot.py by path); it
resolves fine as a namespace package once ``src`` is importable.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: exhaustive enumeration / large Monte-Carlo equity checks "
        "(deselect with -m 'not slow')",
    )
