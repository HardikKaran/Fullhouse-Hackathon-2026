---
name: equity-engine-api
description: Real names/locations of the Monte-Carlo equity engine API (differ from build-plan names)
metadata:
  type: project
---

The equity engine is a **flat module** `src/mybot/equity.py` (there is no
`equity/` package — don't create one, it would collide). Public API:

- `mc_equity_vs_hand(hero, villain, board=None, iters=100_000, seed=None) -> dict`
- `mc_equity_vs_random(hero, board=None, n_opponents=1, iters=50_000, seed=None, deadline=None) -> dict`
  (dict = `{equity, win, tie, loss, iters[, n_opponents]}`)
- `equity_mc(...) -> float` — legacy thin wrapper over the two above.
- `equity_exact_headsup(hero, villain, board=None) -> float` — exhaustive offline oracle.

eval7 primitives (`score`, `to_cards`, `hand_label`, `compare`, `best_five`, `FULL_DECK`)
live in `src/mybot/hand_eval.py`.

**Why:** The Step-3 build plan referred to these as `mc_equity_vs_*` in a package
`src/mybot/equity/montecarlo.py` (+ `cards.py`/`evaluate.py`). That layout never existed;
the names were added to the existing flat module instead. eval7 0.1.x has **no** built-in
Monte-Carlo/equity helper to cross-check against — the exhaustive `equity_exact_headsup` is
the oracle.

**How to apply:** Import from `mybot.equity`. Recommended ~50,000 iters/decision to stay
under the 2 s / 0.5 CPU budget (measured: ~0.004 ms/iter heads-up on this machine). Verify
with `pytest tests/test_montecarlo.py -v` and `python bench/equity_report.py`. Note: the
plan's published "JJ vs AKs ~52%" was wrong — it's ~54%. Related: [[equity-overestimate-random]].
