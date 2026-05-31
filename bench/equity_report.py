#!/usr/bin/env python3
"""Human-readable verification + latency report for the Monte-Carlo equity engine.

Run it::

    source .venv/bin/activate
    python bench/equity_report.py

Prints two tables to stdout:

* **Table A** - verifies the engine against published preflop equities. A row is
  PASS only if the Monte-Carlo estimate lands within ``TOLERANCE`` of the
  published number. The process exits ``0`` only if every row passes.
* **Table B** - measured latency of :func:`mc_equity_vs_random` across iteration
  counts / opponent counts, with a recommended per-decision default.

The Table-A numbers are independently published equities (pokerstove /
propokertools); do **not** widen ``TOLERANCE`` to force a green report -- if a
row fails, the sampler / deck / win-counting is wrong.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make ``src`` importable without an install step (mirrors tests/conftest.py).
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from mybot.equity import mc_equity_vs_hand, mc_equity_vs_random  # noqa: E402

ITERS = 100_000
SEED = 42
TOLERANCE = 0.01  # +/- 1.0 percentage points

# (label, hero_desc, hero, villain, published_equity)
MATCHUPS = [
    ("AsKs vs QhQd", "AKs", ["As", "Ks"], ["Qh", "Qd"], 0.46),
    ("AhAd vs KsKc", "AA", ["Ah", "Ad"], ["Ks", "Kc"], 0.82),
    ("AhAd vs AsKs", "AA", ["Ah", "Ad"], ["As", "Ks"], 0.88),
    ("JhJd vs AsKs", "JJ", ["Jh", "Jd"], ["As", "Ks"], 0.54),
    ("AhKs vs QhQd", "AKo", ["Ah", "Ks"], ["Qh", "Qd"], 0.43),
    ("AhAd vs 7s2c", "AA", ["Ah", "Ad"], ["7s", "2c"], 0.88),
]

# Latency grid.
LAT_ITERS = [1_000, 5_000, 10_000, 25_000, 50_000, 100_000]
LAT_OPPS = [1, 2, 5]
LAT_RUNS = 5

# Tournament runs at 0.5 CPU, so wall-clock throughput is ~half this machine's
# single-thread number. We size the recommendation against that handicap.
CPU_HANDICAP = 2.0
DECISION_BUDGET_S = 2.0
SAFETY_FRACTION = 0.6  # leave headroom in the 2s budget for the rest of decide()


def verify_table() -> bool:
    """Print Table A; return True iff every matchup passes."""
    print(f"=== Monte-Carlo Equity Verification (iters={ITERS:,}, seed={SEED}) ===")
    header = (
        f"{'Matchup':<20}{'Hero':<6}{'MC equity':>10}{'Published':>12}"
        f"{'Diff':>8}   {'Status'}"
    )
    print(header)
    n_pass = 0
    for label, hero_desc, hero, villain, published in MATCHUPS:
        eq = mc_equity_vs_hand(hero, villain, iters=ITERS, seed=SEED)["equity"]
        diff = eq - published
        ok = abs(diff) <= TOLERANCE
        n_pass += ok
        print(
            f"{label:<20}{hero_desc:<6}{eq * 100:>9.1f}%{published * 100:>11.1f}%"
            f"{diff * 100:>+7.1f}%   {'PASS' if ok else 'FAIL'}"
        )
    print("-" * len(header))
    print(f"{n_pass}/{len(MATCHUPS)} PASS  (tolerance +/-{TOLERANCE * 100:.1f}%)")
    return n_pass == len(MATCHUPS)


def _time_call(iters: int, opp: int) -> float:
    """Mean wall-clock ms for mc_equity_vs_random over LAT_RUNS runs."""
    times = []
    for run in range(LAT_RUNS):
        t0 = time.perf_counter()
        mc_equity_vs_random(["As", "Ks"], n_opponents=opp, iters=iters, seed=run)
        times.append((time.perf_counter() - t0) * 1000.0)
    return sum(times) / len(times)


def latency_table() -> dict:
    """Print Table B; return the measured grid keyed by (iters, opp)."""
    print()
    print(f"=== Latency (mean ms over {LAT_RUNS} runs) ===")
    print(f"{'iters':>8}" + "".join(f"{f'{o} opp':>10}" for o in LAT_OPPS))
    grid: dict = {}
    for iters in LAT_ITERS:
        row = f"{iters:>8,}"
        for opp in LAT_OPPS:
            ms = _time_call(iters, opp)
            grid[(iters, opp)] = ms
            row += f"{ms:>10.1f}"
        print(row)
    return grid


def recommend(grid: dict) -> None:
    """Print a per-decision iters recommendation derived from the measured grid.

    Per-iter cost is dominated by the 7-card score() call and is essentially
    street-independent (a finished board just draws fewer cards), so one budget
    applies to every street.
    """
    per_iter_ms = grid[(100_000, 1)] / 100_000.0
    budget_ms = DECISION_BUDGET_S * 1000.0 * SAFETY_FRACTION / CPU_HANDICAP
    max_iters = int(budget_ms / per_iter_ms)

    def tidy(n: int) -> int:
        for step in (50_000, 25_000, 20_000, 10_000, 5_000, 2_000, 1_000):
            if n >= step:
                return step
        return 1_000

    safe = tidy(max_iters)
    print("-" * 38)
    print(
        f"Per-iter (1 opp, this machine): {per_iter_ms:.4f} ms/iter  |  "
        f"budget @ 0.5 CPU w/ {int(SAFETY_FRACTION * 100)}% safety: {budget_ms:.0f} ms "
        f"=> ~{max_iters:,} iters max"
    )
    print(
        f"Recommended default: {safe:,} iters/decision (all streets)  "
        f"(keeps decide() < {DECISION_BUDGET_S:.0f}s at 0.5 CPU)"
    )


def main() -> int:
    ok = verify_table()
    grid = latency_table()
    recommend(grid)
    print()
    if not ok:
        print("RESULT: verification FAILED - do not trust the engine until green.")
        return 1
    print("RESULT: all published-equity rows PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
