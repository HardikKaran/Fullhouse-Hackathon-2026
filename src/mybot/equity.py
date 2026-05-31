"""Hero equity computation built on :mod:`mybot.hand_eval`.

Two methods, two jobs:

``equity_exact_headsup``
    Exhaustive board enumeration vs a **known** villain hand. Deterministic and
    exact -- this is the *verifier*. Preflop it evaluates ``C(48, 5) =
    1,712,304`` boards: a few seconds, fine offline, far too slow for
    ``decide()``. **Never call it in-game.**

``equity_mc``
    Monte-Carlo sampling of random villain hand(s) and/or board runouts. Fast,
    approximate, scales to multiway. This is the seed of the in-game equity
    engine (Step 3 makes the iteration count a function of the time budget).

Tie convention (matches published preflop equity tables): a tie is **half a
win**. ``equity_exact_headsup`` adds ``0.5`` per tie; ``equity_mc`` splits the
pot ``1/k`` among the ``k`` players sharing the best hand.
"""

from __future__ import annotations

import itertools
import random
import time

import eval7

from .hand_eval import FULL_DECK, to_cards


def _remaining_deck(known: list[str]) -> list[str]:
    """52-card deck minus ``known``; errors on dupes/bad cards in ``known``."""
    to_cards(known)  # validates format + intra-call duplicates
    known_set = set(known)
    return [c for c in FULL_DECK if c not in known_set]


def equity_exact_headsup(
    hero: list[str],
    villain: list[str],
    board: list[str] | None = None,
) -> float:
    """Exact hero equity vs a known villain hand (tie = half).

    Enumerates every completion of the remaining board to 5 cards. Offline /
    verification use only -- see module docstring. Returns hero equity in
    ``[0, 1]``.
    """
    board = list(board or [])
    if len(hero) != 2 or len(villain) != 2:
        raise ValueError("hero and villain must each have exactly 2 cards")
    if len(board) > 5:
        raise ValueError(f"board already has {len(board)} cards (max 5)")
    deck_strs = _remaining_deck(list(hero) + list(villain) + board)

    # Same semantics as compare() on every completed board, but we parse the
    # fixed cards + deck into eval7.Card *once* and call eval7.evaluate directly
    # in the hot loop -- re-parsing strings on each of up to C(48,5)=1.7M boards
    # is what makes the naive version several times slower.
    hero_c = [eval7.Card(c) for c in hero]
    vill_c = [eval7.Card(c) for c in villain]
    board_c = [eval7.Card(c) for c in board]
    deck_c = [eval7.Card(c) for c in deck_strs]
    need = 5 - len(board)
    evaluate = eval7.evaluate

    wins = ties = total = 0
    for extra in itertools.combinations(deck_c, need):
        full = board_c + list(extra)
        hero_score = evaluate(hero_c + full)
        villain_score = evaluate(vill_c + full)
        if hero_score > villain_score:
            wins += 1
        elif hero_score == villain_score:
            ties += 1
        total += 1
    return (wins + 0.5 * ties) / total


def equity_mc(
    hero: list[str],
    board: list[str] | None = None,
    villain: list[str] | None = None,
    n_villains: int = 1,
    iters: int = 100_000,
    seed: int | None = None,
) -> float:
    """Monte-Carlo hero equity in ``[0, 1]``.

    If ``villain`` is given, every iteration plays hero vs that exact hand (a
    variance check against the exact enumerator). Otherwise ``n_villains``
    random hands are dealt from the remaining deck each iteration. The board is
    completed to 5 cards. Ties split equity ``1/k`` among the ``k`` winners.

    Deterministic when ``seed`` is set (required for repeatable tests).
    """
    # Thin wrapper over the dict-returning API below; returns just the equity
    # float for legacy callers (tests, CLI). Behaviour is identical -- same deck
    # order, same RNG seeding -> same numbers.
    if iters <= 0:
        raise ValueError("iters must be positive")
    if villain is not None:
        return mc_equity_vs_hand(hero, villain, board=board, iters=iters, seed=seed)[
            "equity"
        ]
    return mc_equity_vs_random(
        hero, board=board, n_opponents=n_villains, iters=iters, seed=seed
    )["equity"]


def _mc_simulate(
    hero: list[str],
    fixed_villains: list[list[str]],
    n_random: int,
    board: list[str],
    iters: int,
    seed: int | None,
    deadline: float | None = None,
) -> tuple[float, int, int, int, int]:
    """Core Monte-Carlo loop shared by the dict-returning equity functions.

    Plays ``hero`` against ``fixed_villains`` (known hands) plus ``n_random``
    uniformly-random opponents, completing the board each iteration. A tie at
    the top splits equity ``1/k`` among the ``k`` players sharing the best hand.

    Returns ``(equity_sum, win, tie, loss, completed)``: ``win``/``tie``/``loss``
    count iterations where hero is sole-best / shares the top / is beaten, and
    ``equity_sum`` is the summed fractional pot share (``equity_sum / completed``
    is hero equity). ``completed`` may be < ``iters`` if ``deadline`` (a
    ``time.monotonic()`` value) is reached.
    """
    if len(hero) != 2:
        raise ValueError("hero must have exactly 2 cards")
    for v in fixed_villains:
        if len(v) != 2:
            raise ValueError("each villain hand must have exactly 2 cards")
    if not 0 <= len(board) <= 5:
        raise ValueError(f"board must be 0..5 cards, got {len(board)}")
    if iters <= 0:
        raise ValueError("iters must be positive")

    known = list(hero) + list(board)
    for v in fixed_villains:
        known += list(v)
    deck = [eval7.Card(c) for c in _remaining_deck(known)]

    hero_cards = [eval7.Card(c) for c in hero]
    board_cards = [eval7.Card(c) for c in board]
    fixed_cards = [[eval7.Card(c) for c in v] for v in fixed_villains]

    need_board = 5 - len(board)
    draw = need_board + 2 * n_random
    if draw > len(deck):
        raise ValueError("not enough cards left in the deck for this request")

    rng = random.Random(seed)
    sample = rng.sample  # local alias (hot loop)
    evaluate = eval7.evaluate
    monotonic = time.monotonic

    equity_sum = 0.0
    win = tie = loss = completed = 0
    for i in range(iters):
        # Check the clock every 1024 iters (not every iter -- monotonic() isn't
        # free), and never on i==0 so at least one iteration always completes.
        if deadline is not None and i and (i & 0x3FF) == 0 and monotonic() >= deadline:
            break
        drawn = sample(deck, draw)
        runout = board_cards + drawn[:need_board]
        rest = drawn[need_board:]

        hero_score = evaluate(hero_cards + runout)
        villain_scores = [evaluate(fc + runout) for fc in fixed_cards]
        for v in range(n_random):
            villain_scores.append(evaluate(rest[2 * v : 2 * v + 2] + runout))

        best_villain = max(villain_scores) if villain_scores else -1
        if hero_score > best_villain:
            equity_sum += 1.0
            win += 1
        elif hero_score == best_villain:
            k = 1 + sum(1 for s in villain_scores if s == hero_score)
            equity_sum += 1.0 / k
            tie += 1
        else:
            loss += 1
        completed += 1

    return equity_sum, win, tie, loss, completed


def mc_equity_vs_hand(
    hero: list[str],
    villain: list[str],
    board: list[str] | None = None,
    iters: int = 100_000,
    seed: int | None = None,
) -> dict:
    """Monte-Carlo hero equity vs a **specific** villain hand.

    Samples the remaining board cards ``iters`` times and counts win / tie /
    loss; a tie is half a win (heads-up), matching published preflop equity
    tables. Deterministic when ``seed`` is set.

    Returns ``{"equity", "win", "tie", "loss", "iters"}`` -- the first four as
    fractions in ``[0, 1]``, ``iters`` the number actually completed. On a full
    5-card board every iteration is identical, so the result is exact.
    """
    board = list(board or [])
    if len(villain) != 2:
        raise ValueError("villain must have exactly 2 cards")
    eq, win, tie, loss, n = _mc_simulate(hero, [villain], 0, board, iters, seed)
    return {
        "equity": eq / n,
        "win": win / n,
        "tie": tie / n,
        "loss": loss / n,
        "iters": n,
    }


def mc_equity_vs_random(
    hero: list[str],
    board: list[str] | None = None,
    n_opponents: int = 1,
    iters: int = 50_000,
    seed: int | None = None,
    deadline: float | None = None,
) -> dict:
    """Monte-Carlo hero equity vs ``n_opponents`` **uniformly-random** hands.

    Each iteration deals 2 cards to every opponent from the remaining deck,
    completes the board, and credits hero ``1`` for a sole win or ``1/k`` for a
    ``k``-way chop at the top. Returns ``{"equity", "win", "tie", "loss",
    "iters", "n_opponents"}``.

    ``deadline`` (an optional ``time.monotonic()`` timestamp) hard-stops the
    loop and returns the estimate so far, so a caller can stay inside the 2 s
    decision budget; ``iters`` in the result reports how many were completed.

    .. warning::
       Uniformly-random opponents **overestimate** hero equity. Real opponents
       fold trash, so a villain still in the pot holds a stronger-than-random
       hand. Treat this as a building block / verification target, not a number
       strategy should trust raw -- switch to a weighted range (e.g.
       :func:`mc_equity_vs_hand` per range hand) once the opponent model exists.
    """
    board = list(board or [])
    if n_opponents < 0:
        raise ValueError("n_opponents must be >= 0")
    eq, win, tie, loss, n = _mc_simulate(
        hero, [], n_opponents, board, iters, seed, deadline
    )
    return {
        "equity": eq / n,
        "win": win / n,
        "tie": tie / n,
        "loss": loss / n,
        "iters": n,
        "n_opponents": n_opponents,
    }


# --------------------------------------------------------------------------- #
# Tiny CLI probe:  python -m mybot.equity --hero AhAd --villain KhKd
# --------------------------------------------------------------------------- #
def _split_cards(arg: str) -> list[str]:
    """Accept concatenated ("AhAd") or spaced ("Ah Ad") card input."""
    compact = arg.replace(" ", "")
    if len(compact) % 2 != 0:
        raise ValueError(f"odd number of characters in card string: {arg!r}")
    return [compact[i : i + 2] for i in range(0, len(compact), 2)]


def _main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m mybot.equity",
        description="Print exact (heads-up, known villain) and Monte-Carlo "
        "hero equity side by side.",
    )
    parser.add_argument("--hero", required=True, help="hero hole cards, e.g. AhAd")
    parser.add_argument("--villain", help="villain hole cards, e.g. KhKd")
    parser.add_argument("--board", default="", help="board cards, e.g. Kd7c2s")
    parser.add_argument("--iters", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    hero = _split_cards(args.hero)
    villain = _split_cards(args.villain) if args.villain else None
    board = _split_cards(args.board) if args.board else []

    if villain is not None:
        exact = equity_exact_headsup(hero, villain, board)
        print(f"exact (vs {''.join(villain)}) : {exact:.4f}")
    label = f"vs {''.join(villain)}" if villain else f"vs {args.iters:,} random"
    mc = equity_mc(hero, board=board, villain=villain, iters=args.iters, seed=args.seed)
    print(f"mc    ({label}) : {mc:.4f}  [iters={args.iters:,}, seed={args.seed}]")


if __name__ == "__main__":
    _main()
