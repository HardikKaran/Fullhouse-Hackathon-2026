"""Thin, deterministic hand-evaluation wrapper around ``eval7``.

Pure functions over the engine's string card format (``"As"``, ``"Kh"`` ...) so
the same strings the engine emits in ``state["your_cards"]`` /
``state["community_cards"]`` can be passed straight in. No engine import, no
randomness, no I/O -- cheap and safe to import from the in-game bot.

Key ``eval7`` facts this module relies on:

* ``eval7.evaluate(cards)`` scores the **best 5-card hand** out of 5, 6 or 7
  cards. **Higher score == stronger hand.**
* ``eval7.handtype(score)`` maps a score to a human label ("Full House" ...).
* Ace plays low in the wheel (``A-2-3-4-5`` is a straight).
"""

from __future__ import annotations

import itertools

import eval7

RANKS = "23456789TJQKA"
SUITS = "shdc"

# All 52 canonical card strings, built ourselves so the deck never depends on
# eval7's internal string formatting.
FULL_DECK: list[str] = [r + s for r in RANKS for s in SUITS]


def _validate_card(c: str) -> None:
    if (
        not isinstance(c, str)
        or len(c) != 2
        or c[0] not in RANKS
        or c[1] not in SUITS
    ):
        raise ValueError(
            f"bad card string: {c!r} (expected <rank><suit>, "
            f"ranks {RANKS!r}, suits {SUITS!r})"
        )


def to_cards(cards: list[str]) -> list[eval7.Card]:
    """Parse engine card strings (``["As", "Kh"]``) into ``eval7.Card`` objects.

    Validates each token's format and rejects duplicate cards within the call.
    """
    if not isinstance(cards, (list, tuple)):
        raise TypeError("cards must be a list/tuple of 2-char strings")
    for c in cards:
        _validate_card(c)
    if len(set(cards)) != len(cards):
        raise ValueError(f"duplicate card(s) in {list(cards)}")
    return [eval7.Card(c) for c in cards]


def score(hole: list[str], board: list[str] | None = None) -> int:
    """``eval7`` score (higher == stronger) for the best 5-card hand.

    Requires exactly 2 hole cards, 0..5 board cards, and >= 5 cards total
    (``eval7`` needs at least five). Duplicate cards across hole+board raise.
    """
    board = list(board or [])
    if len(hole) != 2:
        raise ValueError(f"hole must be exactly 2 cards, got {len(hole)}")
    if not 0 <= len(board) <= 5:
        raise ValueError(f"board must be 0..5 cards, got {len(board)}")
    cards = to_cards(list(hole) + board)  # also catches hole/board overlap
    if len(cards) < 5:
        raise ValueError(
            f"need >= 5 cards to evaluate, got {len(cards)} "
            "(2 hole + at least 3 board)"
        )
    return eval7.evaluate(cards)


def hand_label(hole: list[str], board: list[str] | None = None) -> str:
    """Human-readable hand type ("Full House" ...) for the best 5 cards."""
    return eval7.handtype(score(hole, board))


def compare(hole_a: list[str], hole_b: list[str], board: list[str]) -> int:
    """Compare two hands on a **full 5-card board**.

    Returns ``+1`` if A wins, ``0`` on a tie, ``-1`` if B wins.
    """
    if len(board) != 5:
        raise ValueError(f"compare needs a full 5-card board, got {len(board)}")
    sa = score(hole_a, board)
    sb = score(hole_b, board)
    if sa > sb:
        return 1
    if sa < sb:
        return -1
    return 0


def best_five(hole: list[str], board: list[str]) -> list[str]:
    """Return the 5 card strings forming the best hand (debug/replay aid)."""
    cards = list(hole) + list(board)
    if len(cards) < 5:
        raise ValueError(f"need >= 5 cards, got {len(cards)}")
    to_cards(cards)  # validate format + dupes
    best_score: int | None = None
    best_combo: tuple[str, ...] | None = None
    for combo in itertools.combinations(cards, 5):
        s = eval7.evaluate([eval7.Card(c) for c in combo])
        if best_score is None or s > best_score:
            best_score = s
            best_combo = combo
    assert best_combo is not None
    return list(best_combo)
