"""Verification: exact heads-up equities vs confirmed published preflop matchups.

The exact enumerator is itself an exact source, and these targets were each
cross-checked against published preflop equity charts (PokerStove / Equilab-class
exact enumeration). Tie counts as half a win. Suits are chosen the way charts
define the generic matchup -- no unintended shared suits/blockers unless the
matchup intends them (e.g. AA vs AKs: hero's two red aces force villain's ace to
the remaining suit).

Two rows correct the original plan's rounded table after confirming the source:
  * AA vs 22  -> ~0.82  (a lower pair beats AA only ~18% of the time), not ~0.80.
  * AKo vs 22 -> AK ~0.47 (the underpair is the slight favourite ~0.53), not ~0.52.

Tight +/-0.005 band: a wider miss means a bug -- usually tie handling or a known
card left in the deck -- not sampling noise, because this path is exact.
"""

import pytest

from mybot.equity import equity_exact_headsup

TOL = 0.005

# (name, hero, villain, hero-equity target)
MATCHUPS = [
    ("AA vs KK", ["Ah", "Ad"], ["Kh", "Kd"], 0.826),
    ("AA vs AKs", ["Ah", "Ad"], ["As", "Ks"], 0.879),
    ("AA vs 22", ["Ah", "Ad"], ["2c", "2d"], 0.822),
    ("AKs vs QQ", ["As", "Ks"], ["Qh", "Qd"], 0.462),
    ("AKo vs QQ", ["As", "Kh"], ["Qc", "Qd"], 0.428),
    ("AKo vs 22", ["As", "Kh"], ["2c", "2d"], 0.470),
    ("AsKs vs QhJh", ["As", "Ks"], ["Qh", "Jh"], 0.627),
]


@pytest.mark.slow
@pytest.mark.parametrize(
    "name,hero,villain,target", MATCHUPS, ids=[m[0] for m in MATCHUPS]
)
def test_exact_equity_matches_published(name, hero, villain, target):
    eq = equity_exact_headsup(hero, villain)
    assert abs(eq - target) < TOL, f"{name}: got {eq:.4f}, expected ~{target}"
