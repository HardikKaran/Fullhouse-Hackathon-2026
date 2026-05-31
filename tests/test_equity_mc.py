"""Monte-Carlo equity: convergence to the exact enumerator + determinism.

This validates the foundation Step 3 scales into the in-game engine -- the MC
path (independent tie handling: split 1/k) must agree with the exact path.
"""

import pytest

from mybot.equity import equity_exact_headsup, equity_mc

# A subset of the published matchups, MC vs the exact path.
_MC_MATCHUPS = [
    ("AA vs KK", ["Ah", "Ad"], ["Kh", "Kd"]),
    ("AKs vs QQ", ["As", "Ks"], ["Qh", "Qd"]),
    ("AKo vs 22", ["As", "Kh"], ["2c", "2d"]),
]


@pytest.mark.slow
@pytest.mark.parametrize(
    "name,hero,villain", _MC_MATCHUPS, ids=[m[0] for m in _MC_MATCHUPS]
)
def test_mc_converges_to_exact(name, hero, villain):
    exact = equity_exact_headsup(hero, villain)
    mc = equity_mc(hero, villain=villain, iters=200_000, seed=0)
    assert abs(mc - exact) < 0.004, f"{name}: mc {mc:.4f} vs exact {exact:.4f}"


def test_mc_is_deterministic_with_seed():
    kw = dict(villain=["Qh", "Qd"], iters=20_000, seed=42)
    assert equity_mc(["As", "Ks"], **kw) == equity_mc(["As", "Ks"], **kw)


def test_mc_different_seeds_differ_but_both_close():
    exact = equity_exact_headsup(["As", "Ks"], ["Qh", "Qd"])
    a = equity_mc(["As", "Ks"], villain=["Qh", "Qd"], iters=50_000, seed=1)
    b = equity_mc(["As", "Ks"], villain=["Qh", "Qd"], iters=50_000, seed=2)
    assert a != b
    assert abs(a - exact) < 0.01
    assert abs(b - exact) < 0.01


def test_mc_overpair_on_dry_board_vs_random():
    # A set-less overpair on a dry, disconnected board crushes one random hand.
    eq = equity_mc(["Ah", "Ad"], board=["Kd", "7c", "2s"], iters=50_000, seed=0)
    assert eq > 0.85
