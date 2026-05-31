"""Tests for mybot.hand_eval: category rankings, 7-card best-of, the wheel, and
malformed-input handling. Scores are eval7's (higher == stronger); category
labels are eval7's own strings ("Quads", "Trips", "Two Pair", ...)."""

import pytest

from mybot.hand_eval import best_five, compare, hand_label, score, to_cards

# One 5-card hand per category (hole + 3 board), strongest -> weakest.
_HANDS = [
    ("straight_flush", ["As", "Ks"], ["Qs", "Js", "Ts"]),
    ("quads", ["Ah", "Ad"], ["Ac", "As", "Kd"]),
    ("full_house", ["Kh", "Kd"], ["Kc", "Qh", "Qd"]),
    ("flush", ["Ah", "Th"], ["7h", "5h", "2h"]),
    ("straight", ["9c", "8d"], ["7h", "6s", "5c"]),
    ("trips", ["Qh", "Qd"], ["Qc", "8s", "2h"]),
    ("two_pair", ["Jh", "Jd"], ["9c", "9d", "2s"]),
    ("pair", ["Th", "Td"], ["8c", "5d", "2s"]),
    ("high_card", ["Ah", "Qd"], ["9c", "5s", "2h"]),
]


def test_category_scores_strictly_decreasing():
    scored = [(name, score(hole, board)) for name, hole, board in _HANDS]
    for (name_a, sa), (name_b, sb) in zip(scored, scored[1:]):
        assert sa > sb, f"{name_a} ({sa}) should outscore {name_b} ({sb})"


def test_hand_labels():
    assert hand_label(["As", "Ks"], ["Qs", "Js", "Ts"]) == "Straight Flush"
    assert hand_label(["Ah", "Ad"], ["Ac", "As", "Kd"]) == "Quads"
    assert hand_label(["Kh", "Kd"], ["Kc", "Qh", "Qd"]) == "Full House"
    assert hand_label(["Th", "Td"], ["8c", "5d", "2s"]) == "Pair"


def test_seven_card_best_of():
    # 2 hole + 5 board: the best 5 of 7 is the royal flush in spades.
    assert hand_label(["As", "Ks"], ["Qs", "Js", "Ts", "2c", "3d"]) == "Straight Flush"


def test_wheel_is_a_straight_with_ace_low():
    wheel = score(["Ah", "2d"], ["3c", "4s", "5h"])
    assert hand_label(["Ah", "2d"], ["3c", "4s", "5h"]) == "Straight"
    # Ace plays LOW: the wheel is the weakest straight, below 2-3-4-5-6 ...
    assert wheel < score(["6c", "2h"], ["3c", "4s", "5h"])
    # ... but still beats a non-straight (here, ace high).
    assert wheel > score(["Ah", "Kd"], ["Qc", "2s", "7h"])


def test_compare_straight_flush_beats_set():
    board = ["Qs", "Js", "Ts", "7d", "2c"]
    assert compare(["As", "Ks"], ["7h", "7c"], board) == 1  # royal flush > set of 7s
    assert compare(["7h", "7c"], ["As", "Ks"], board) == -1  # symmetric


def test_compare_identical_hands_tie():
    # Both make the board's Broadway straight with A-K -> exact tie.
    board = ["Qh", "Js", "Ts", "2c", "7d"]
    assert compare(["Ah", "Kh"], ["Ad", "Kd"], board) == 0


def test_best_five_selects_the_flush():
    five = best_five(["Ah", "Th"], ["7h", "5h", "2h", "Kd", "Qc"])
    assert set(five) == {"Ah", "Th", "7h", "5h", "2h"}


def test_malformed_card_raises():
    with pytest.raises(ValueError):
        to_cards(["Xx", "Kh"])  # bad rank/suit
    with pytest.raises(ValueError):
        to_cards(["As", "As"])  # duplicate within the call


def test_arity_and_overlap_errors():
    with pytest.raises(ValueError):
        score(["As", "Kh", "Qd"], ["2c", "3d", "4h"])  # 3 hole cards
    with pytest.raises(ValueError):
        score(["As", "Kh"], [])  # < 5 cards total
    with pytest.raises(ValueError):
        score(["As", "Ah"], ["As", "3d", "4h"])  # As duplicated across hole+board


def test_compare_requires_full_board():
    with pytest.raises(ValueError):
        compare(["As", "Kh"], ["Qd", "Jc"], ["2c", "3d", "4h"])  # 3-card board
