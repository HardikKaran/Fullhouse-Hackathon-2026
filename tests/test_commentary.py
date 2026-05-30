"""Unit tests for the engine-free commentary helpers (harness/commentary.py)."""

import eval7

from harness import commentary


def _c(*strs):
    return [eval7.Card(s) for s in strs]


def test_pretty_card_symbols_and_plain():
    assert commentary.pretty_card(eval7.Card("As"), symbols=True) == "A♠"
    assert commentary.pretty_card(eval7.Card("Td"), symbols=True) == "T♦"
    assert commentary.pretty_card(eval7.Card("As"), symbols=False) == "As"
    assert commentary.pretty_cards([], symbols=True) == "--"


def test_describe_hand_preflop():
    # Pocket pair, only the two hole cards are known.
    assert commentary.describe_hand(_c("As", "Ah"), []).startswith("Pair of Aces")
    # Two unpaired cards -> "<high> high".
    assert commentary.describe_hand(_c("As", "Kd"), []) == "Ace high"


def test_describe_hand_postflop_categories():
    # Trips of Aces on the flop.
    assert commentary.describe_hand(_c("As", "Ah"), _c("Ad", "Kd", "2c")).startswith("Trips")
    assert "Aces" in commentary.describe_hand(_c("As", "Ah"), _c("Ad", "Kd", "2c"))
    # One pair.
    assert commentary.describe_hand(_c("Ks", "Qd"), _c("Kh", "7d", "2c")) == "Pair of Kings"
    # Two pair.
    assert commentary.describe_hand(_c("Ks", "Qd"), _c("Kh", "Qc", "2c")).startswith("Two Pair")


def test_describe_hand_straight_labels_run_top_not_high_card():
    # Board makes an 8-9-T-J-Q straight; the Ace in hand is NOT part of the run,
    # so the label must read "Queen high", not "Ace high".
    assert (
        commentary.describe_hand(_c("As", "Ah"), _c("Tc", "8c", "Jc", "Qh", "9d"))
        == "Straight, Queen high"
    )
    # Wheel: A-2-3-4-5 is a Five-high straight.
    assert (
        commentary.describe_hand(_c("As", "2d"), _c("3c", "4h", "5s", "Kd", "9c"))
        == "Straight, Five high"
    )


def test_describe_hand_flush_uses_flush_suit_high():
    # Five hearts; flush high is the King of hearts, not the Ace of spades.
    assert (
        commentary.describe_hand(_c("As", "Kh"), _c("2h", "7h", "9h", "Th", "3c"))
        == "Flush, King high"
    )


def test_equity_vs_random_strong_hand_high():
    # Flopped trip aces vs one random hand should dominate.
    eq = commentary.equity_vs_random(
        _c("As", "Ah"), _c("Ad", "Kd", "2c"), n_opponents=1, iters=5000, seed=1,
    )
    assert eq > 90.0


def test_equity_vs_random_zero_opponents_is_certain():
    assert commentary.equity_vs_random(_c("2c", "3d"), [], n_opponents=0) == 100.0


def test_equity_vs_random_is_reproducible_with_seed():
    args = (_c("Js", "Jd"), _c("7h", "2c", "9d"), 2)
    a = commentary.equity_vs_random(*args, iters=1000, seed=42)
    b = commentary.equity_vs_random(*args, iters=1000, seed=42)
    assert a == b
