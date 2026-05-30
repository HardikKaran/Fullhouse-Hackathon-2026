"""Pure commentary helpers for the live-watch harness.

Engine-free on purpose: this module imports only ``eval7`` and ``random`` so it
can be unit-tested without spinning up bot subprocesses or the game engine. It
turns ``eval7.Card`` objects into human-readable strings, labels the made hand,
and estimates equity.

eval7 facts these helpers rely on (verified against the installed lib):
  * ``str(eval7.Card("As")) == "As"``
  * ``card.rank`` is 0..12 for ranks 2..A
  * ``card.suit`` is c=0, d=1, h=2, s=3
  * ``eval7.handtype(eval7.evaluate(cards))`` returns one of:
    High Card / Pair / Two Pair / Trips / Straight / Flush / Full House /
    Quads / Straight Flush  (needs 5..7 cards)
"""

import random
from collections import Counter

import eval7

# rank index (0..12) -> display char / English name
_RANK_CHARS = "23456789TJQKA"
_RANK_NAME = {
    0: "Deuce", 1: "Three", 2: "Four", 3: "Five", 4: "Six", 5: "Seven",
    6: "Eight", 7: "Nine", 8: "Ten", 9: "Jack", 10: "Queen", 11: "King", 12: "Ace",
}
_RANK_PLURAL = {
    0: "Deuces", 1: "Threes", 2: "Fours", 3: "Fives", 4: "Sixes", 5: "Sevens",
    6: "Eights", 7: "Nines", 8: "Tens", 9: "Jacks", 10: "Queens", 11: "Kings", 12: "Aces",
}
# suit index (0..3) -> unicode pip
_SUIT_SYMBOL = {0: "♣", 1: "♦", 2: "♥", 3: "♠"}  # c d h s


# ---------------------------------------------------------------------------
# Card pretty-printing
# ---------------------------------------------------------------------------

def pretty_card(card, symbols=True) -> str:
    """One ``eval7.Card`` -> ``"A♠"`` (symbols) or its plain ``"As"`` form."""
    if not symbols:
        return str(card)
    try:
        return _RANK_CHARS[card.rank] + _SUIT_SYMBOL[card.suit]
    except Exception:  # pragma: no cover - defensive, never break commentary
        return str(card)


def pretty_cards(cards, symbols=True) -> str:
    """Space-joined ``pretty_card`` over a list; ``"--"`` for an empty board."""
    if not cards:
        return "--"
    return " ".join(pretty_card(c, symbols) for c in cards)


def pretty_str_cards(card_strs, symbols=True) -> str:
    """Like ``pretty_cards`` but takes plain card strings (e.g. ``["As", "Kd"]``),
    as found in engine result dicts such as ``revealed_cards``."""
    if not card_strs:
        return "--"
    return " ".join(pretty_card(eval7.Card(c), symbols) for c in card_strs)


# ---------------------------------------------------------------------------
# Made-hand description
# ---------------------------------------------------------------------------

def _high_name(cards) -> str:
    """English name of the highest rank present."""
    return _RANK_NAME[max(c.rank for c in cards)]


def _straight_top_rank(ranks) -> int:
    """Top rank of the best straight in ``ranks`` (a set of 0..12), or -1 if none.

    Ace plays high or low: the wheel (A-2-3-4-5) is detected by adding a -1
    pseudo-rank when an Ace (12) is present, so a 5-high straight returns 3 (Five).
    """
    present = set(ranks)
    if 12 in present:
        present.add(-1)  # Ace can sit below the Deuce for the wheel
    for top in range(12, 2, -1):  # 5-card runs top out at index 4 (a Six-high min)
        if all((top - i) in present for i in range(5)):
            return top
    return -1


def _flush_suit_cards(cards):
    """Cards of the most-represented suit when that suit has >=5 cards, else []."""
    suit_counts = Counter(c.suit for c in cards)
    suit, n = max(suit_counts.items(), key=lambda kv: kv[1])
    return [c for c in cards if c.suit == suit] if n >= 5 else []


def describe_hand(hole_cards, board) -> str:
    """Human label for the best current made hand, e.g. ``"Trips (three Aces)"``.

    Preflop (fewer than 5 cards total) is special-cased with pure rank counting
    since ``eval7.evaluate`` wants 5..7 cards. Any unexpected error falls back to
    the bare category so a watch session never crashes on commentary.
    """
    cards = list(hole_cards) + list(board)
    try:
        counts = Counter(c.rank for c in cards)

        if len(cards) < 5:
            # Preflop: only the two hole cards are meaningful.
            pair = [r for r, n in counts.items() if n >= 2]
            if pair:
                return "Pair of " + _RANK_PLURAL[pair[0]]
            return _high_name(cards) + " high"

        category = str(eval7.handtype(eval7.evaluate(cards)))

        if category == "Pair":
            r = max(r for r, n in counts.items() if n == 2)
            return "Pair of " + _RANK_PLURAL[r]
        if category == "Two Pair":
            pairs = sorted((r for r, n in counts.items() if n >= 2), reverse=True)[:2]
            return f"Two Pair ({_RANK_PLURAL[pairs[0]]} and {_RANK_PLURAL[pairs[1]]})"
        if category == "Trips":
            r = max(r for r, n in counts.items() if n == 3)
            return f"Trips (three {_RANK_PLURAL[r]})"
        if category == "Full House":
            trip = max((r for r, n in counts.items() if n >= 3), default=None)
            pair = max((r for r, n in counts.items() if n >= 2 and r != trip), default=None)
            if trip is not None and pair is not None:
                return f"Full House ({_RANK_PLURAL[trip]} full of {_RANK_PLURAL[pair]})"
            return "Full House"
        if category == "Quads":
            r = max(r for r, n in counts.items() if n == 4)
            return f"Quads (four {_RANK_PLURAL[r]})"
        if category == "Straight Flush":
            flush = _flush_suit_cards(cards)
            top = _straight_top_rank(c.rank for c in flush)
            return f"Straight Flush, {_RANK_NAME[top]} high" if top >= 0 else category
        if category == "Straight":
            top = _straight_top_rank(c.rank for c in cards)
            return f"Straight, {_RANK_NAME[top]} high" if top >= 0 else category
        if category == "Flush":
            flush = _flush_suit_cards(cards)
            high = _RANK_NAME[max(c.rank for c in flush)] if flush else _high_name(cards)
            return f"Flush, {high} high"
        if category == "High Card":
            return f"{_high_name(cards)} high"
        return category
    except Exception:  # pragma: no cover - defensive fallback
        try:
            return str(eval7.handtype(eval7.evaluate(cards)))
        except Exception:
            return "?"


# ---------------------------------------------------------------------------
# Equity (Monte Carlo, vs random opponents)
# ---------------------------------------------------------------------------

def _full_deck():
    return [eval7.Card(r + s) for r in _RANK_CHARS for s in "cdhs"]


def equity_vs_random(hole, board, n_opponents, iters=2000, seed=None) -> float:
    """Win% of ``hole`` against ``n_opponents`` random hands, sampling both the
    opponents' hole cards and the remaining board.

    These are independent per-player estimates (each opponent is assumed random),
    so across several live players they will *not* sum to 100% — that is inherent
    to "vs random" and expected.

    Ties split credit. Returns a percentage in [0, 100].
    """
    hole = list(hole)
    board = list(board)
    if n_opponents <= 0:
        return 100.0

    known = {str(c) for c in hole} | {str(c) for c in board}
    deck = [c for c in _full_deck() if str(c) not in known]
    need_board = 5 - len(board)
    draw_n = n_opponents * 2 + need_board

    rng = random.Random(seed)
    wins = 0.0
    for _ in range(iters):
        drawn = rng.sample(deck, draw_n)
        opp_cards = drawn[: n_opponents * 2]
        extra_board = drawn[n_opponents * 2:]
        full_board = board + extra_board

        my_score = eval7.evaluate(hole + full_board)
        best_opp = -1
        tied = 0
        for i in range(n_opponents):
            opp = opp_cards[2 * i: 2 * i + 2]
            s = eval7.evaluate(opp + full_board)
            if s > best_opp:
                best_opp = s
                tied = 1
            elif s == best_opp:
                tied += 1

        if my_score > best_opp:
            wins += 1.0
        elif my_score == best_opp:
            wins += 1.0 / (tied + 1)  # split with the tied opponents

    return wins / iters * 100.0
