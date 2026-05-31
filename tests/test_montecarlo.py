"""Monte-Carlo equity engine tests (Step 3, sections 3a-3e).

Self-contained suite referenced by ``pytest tests/test_montecarlo.py -v``:

* 3a - published preflop equities (the ground-truth pin).
* 3b - exact-on-complete-board sanity (zero variance, no tolerance).
* 3c - the MC path agrees with the independent exact enumerator.
* 3d - convergence: more iters land closer to the known value.
* 3e - determinism: same seed -> identical dict; different seeds differ.

The dict API under test lives in ``src/mybot/equity.py`` as
``mc_equity_vs_hand`` / ``mc_equity_vs_random``; ``equity_exact_headsup`` is the
independent (exhaustive) verifier.

Do not widen the tolerances to force a pass -- a green report is only meaningful
if the bands are honest. If a published-equity row fails, debug the sampler,
deck handling or win-counting.
"""

from __future__ import annotations

import pytest

from mybot.equity import (
    equity_exact_headsup,
    mc_equity_vs_hand,
    mc_equity_vs_random,
)

# ---------------------------------------------------------------------------
# 3a. Published preflop matchups (heads-up, hand-vs-hand, +/-1.0% @ 100k iters).
#     Published equities from pokerstove / propokertools.
# ---------------------------------------------------------------------------
KNOWN = [
    # name,        hero,            villain,         published
    ("AKs vs QQ", ["As", "Ks"], ["Qh", "Qd"], 0.46),  # ~46.0%
    ("AA vs KK", ["Ah", "Ad"], ["Ks", "Kc"], 0.82),   # ~82.0%
    ("AA vs AKs", ["Ah", "Ad"], ["As", "Ks"], 0.88),  # ~88.0% (dominated)
    ("JJ vs AKs", ["Jh", "Jd"], ["As", "Ks"], 0.54),  # ~53.9% exact/charts (NOT 52%)
    ("AKo vs QQ", ["Ah", "Ks"], ["Qh", "Qd"], 0.43),  # ~43.0%
    ("AA vs 72o", ["Ah", "Ad"], ["7s", "2c"], 0.88),  # ~88.0%
]


@pytest.mark.parametrize("name, hero, villain, published", KNOWN, ids=[m[0] for m in KNOWN])
def test_published_preflop_equity(name, hero, villain, published):
    res = mc_equity_vs_hand(hero, villain, iters=100_000, seed=42)
    assert abs(res["equity"] - published) <= 0.01, (
        f"{name}: got {res['equity']:.4f}, expected {published:.2f} +/- 0.01"
    )
    # The breakdown must be a valid distribution that reconstructs equity.
    assert res["win"] + res["tie"] + res["loss"] == pytest.approx(1.0)
    assert res["equity"] == pytest.approx(res["win"] + res["tie"] / 2, abs=1e-9)


# ---------------------------------------------------------------------------
# 3b. Exact-on-complete-board sanity (full board -> every iter identical -> exact)
# ---------------------------------------------------------------------------
FULL_BOARD = ["Ac", "7h", "2d", "5s", "9c"]  # trip aces for AA; just a pair for KK


def test_complete_board_hero_wins_is_exactly_one():
    res = mc_equity_vs_hand(["As", "Ad"], ["Ks", "Kd"], board=FULL_BOARD, iters=200, seed=1)
    assert res["equity"] == 1.0
    assert (res["win"], res["tie"], res["loss"]) == (1.0, 0.0, 0.0)


def test_complete_board_hero_loses_is_exactly_zero():
    res = mc_equity_vs_hand(["Ks", "Kd"], ["As", "Ad"], board=FULL_BOARD, iters=200, seed=1)
    assert res["equity"] == 0.0
    assert res["loss"] == 1.0


def test_complete_board_tie_is_exactly_half():
    # Royal flush on the board: both players "play the board" -> chop.
    board = ["As", "Ks", "Qs", "Js", "Ts"]
    res = mc_equity_vs_hand(["2h", "3d"], ["4c", "5d"], board=board, iters=200, seed=1)
    assert res["equity"] == 0.5
    assert res["tie"] == 1.0


# ---------------------------------------------------------------------------
# 3c. The MC path agrees with the independent exact enumerator (proves the
#     sampler/deck/counting reproduce a known-correct number).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "hero, villain",
    [(["As", "Ks"], ["Qh", "Qd"]), (["Ah", "Ad"], ["Ks", "Kc"])],
)
def test_mc_agrees_with_exact_enumerator(hero, villain):
    exact = equity_exact_headsup(hero, villain)
    mc = mc_equity_vs_hand(hero, villain, iters=80_000, seed=11)["equity"]
    assert abs(mc - exact) <= 0.01, f"mc {mc:.4f} vs exact {exact:.4f}"


def test_vs_random_one_opponent_is_in_unit_interval():
    res = mc_equity_vs_random(["As", "Ks"], n_opponents=1, iters=20_000, seed=3)
    assert 0.0 <= res["equity"] <= 1.0
    assert res["n_opponents"] == 1
    # vs a single random hand AKs is a comfortable favourite.
    assert res["equity"] > 0.60


# ---------------------------------------------------------------------------
# 3d. Convergence: the finest estimate beats the coarsest and lands in-band.
#     Guards a biased sampler that would converge to the wrong value.
# ---------------------------------------------------------------------------
def test_convergence_tightens_toward_known_value():
    import statistics

    # AKs vs QQ = 46.2% (exact enumeration / published charts; see test_equity_known).
    hero, villain, known = ["As", "Ks"], ["Qh", "Qd"], 0.462

    def mean_abs_err(iters, seeds):
        return statistics.mean(
            abs(mc_equity_vs_hand(hero, villain, iters=iters, seed=s)["equity"] - known)
            for s in seeds
        )

    # Per-seed MC error is noisy and non-monotonic, but the *mean* absolute error
    # scales ~1/sqrt(iters): averaged over several seeds, 100k must be clearly
    # tighter than 1k. (Asserting per-seed monotonicity would be flaky.)
    coarse = mean_abs_err(1_000, range(6))
    fine = mean_abs_err(100_000, range(3))
    assert fine < coarse, f"100k mean err {fine:.4f} not below 1k mean err {coarse:.4f}"
    assert fine <= 0.01, f"100k mean err {fine:.4f} not in-band"


# ---------------------------------------------------------------------------
# 3e. Determinism.
# ---------------------------------------------------------------------------
def test_same_seed_identical():
    kw = dict(iters=5_000, seed=7)
    assert mc_equity_vs_hand(["As", "Ks"], ["Qh", "Qd"], **kw) == mc_equity_vs_hand(
        ["As", "Ks"], ["Qh", "Qd"], **kw
    )


def test_different_seeds_differ_but_both_in_band():
    a = mc_equity_vs_hand(["As", "Ks"], ["Qh", "Qd"], iters=20_000, seed=1)
    b = mc_equity_vs_hand(["As", "Ks"], ["Qh", "Qd"], iters=20_000, seed=2)
    assert a["equity"] != b["equity"]
    assert abs(a["equity"] - 0.46) <= 0.02
    assert abs(b["equity"] - 0.46) <= 0.02


# ---------------------------------------------------------------------------
# Deadline: mc_equity_vs_random stops early and still returns a usable estimate.
# ---------------------------------------------------------------------------
def test_deadline_stops_early():
    import time

    res = mc_equity_vs_random(
        ["As", "Ks"], n_opponents=2, iters=10_000_000,
        seed=5, deadline=time.monotonic() + 0.25,
    )
    assert res["iters"] < 10_000_000  # bailed out before finishing
    assert res["iters"] >= 1
    assert 0.0 <= res["equity"] <= 1.0
