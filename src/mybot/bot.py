"""
Fullhouse Hackathon — baseline hero bot (v0).

A deliberately simple but *legal* NLHE bot. Its only job in Step 1 is to give
bb/100 a meaningful baseline (beat the template) and exercise the harness end to
end. Real strategy (equity, opponent model, CFR) lands in later build-order
steps — keep this readable and replaceable.

Strategy in one breath:
  Preflop   raise premium hands, call cheap with playable hands, else fold.
  Postflop  value-bet / call in proportion to made-hand strength; fold air to
            big bets.

Contract: decide(state) -> dict, stdlib + allowed libs only, returns well under
2s. Cards are strings like "As", "Td". Raise `amount` is the TOTAL to raise to;
the engine snaps sub-minimum raises up and converts over-stack raises to all-in.
"""

try:
    import eval7  # allowed sandbox lib; gives a real made-hand category postflop
    _HAS_EVAL7 = True
except Exception:  # pragma: no cover - fall back to a coarse heuristic
    _HAS_EVAL7 = False

BOT_NAME = "Baseline-v0"
BOT_AVATAR = "robot_1"

_RANK_VALUE = {r: i + 2 for i, r in enumerate("23456789TJQKA")}  # 2..14

# Made-hand category -> rough strength in [0, 1]. Coarse on purpose for v0.
_HANDTYPE_STRENGTH = {
    "High Card": 0.15,
    "Pair": 0.35,
    "Two Pair": 0.55,
    "Trips": 0.70,
    "Straight": 0.80,
    "Flush": 0.85,
    "Full House": 0.92,
    "Quads": 0.97,
    "Straight Flush": 1.00,
}


def _preflop_strength(cards) -> float:
    """Map two hole cards to a [0, 1] starting-hand strength."""
    (r1, s1), (r2, s2) = cards[0], cards[1]
    v1, v2 = _RANK_VALUE[r1], _RANK_VALUE[r2]
    hi, lo = max(v1, v2), min(v1, v2)
    suited = s1 == s2

    if v1 == v2:  # pocket pair: 22 -> 0.50, AA -> 1.00
        return 0.50 + 0.50 * (hi - 2) / 12

    score = 0.50 * (hi - 2) / 12 + 0.20 * (lo - 2) / 12
    if suited:
        score += 0.10
    gap = hi - lo
    if gap == 1:
        score += 0.08  # connected
    elif gap == 2:
        score += 0.04
    if hi >= _RANK_VALUE["T"] and lo >= _RANK_VALUE["T"]:
        score += 0.10  # both broadway
    return min(score, 0.95)


def _postflop_strength(hole, board) -> float:
    """Map current made hand to a [0, 1] strength."""
    if _HAS_EVAL7:
        cards = [eval7.Card(c) for c in list(hole) + list(board)]
        category = str(eval7.handtype(eval7.evaluate(cards)))
        return _HANDTYPE_STRENGTH.get(category, 0.15)

    # Fallback: crude pair detection without eval7.
    ranks = [c[0] for c in hole]
    board_ranks = [c[0] for c in board]
    if ranks[0] == ranks[1]:
        return 0.50  # pocket pair
    if any(r in board_ranks for r in ranks):
        return 0.35  # paired the board
    return 0.15


def _raise(target, min_raise_to, all_in_to) -> dict:
    """Clamp a raise-to target into [min_raise_to, all_in_to]; all-in if it
    reaches our stack."""
    target = max(min_raise_to, min(int(target), all_in_to))
    if target >= all_in_to:
        return {"action": "all_in"}
    return {"action": "raise", "amount": target}


def _decide(state) -> dict:
    hole = state["your_cards"]
    board = state.get("community_cards", []) or []
    pot = max(1, state.get("pot", 0))
    owed = state.get("amount_owed", 0)
    can_check = state.get("can_check", owed == 0)
    min_raise_to = state.get("min_raise_to", state.get("current_bet", 0))
    my_stack = state.get("your_stack", 0)
    my_bet = state.get("your_bet_this_street", 0)
    preflop = state.get("street", "preflop") == "preflop"

    strength = _preflop_strength(hole) if preflop else _postflop_strength(hole, board)
    all_in_to = my_stack + my_bet  # our maximum raise-to (total committed)

    # --- nothing to call: check, or take the betting lead with strength -----
    if can_check:
        if preflop:
            if strength >= 0.80:  # premium in the BB option -> raise
                return _raise(min_raise_to + 2 * pot, min_raise_to, all_in_to)
            return {"action": "check"}
        if strength >= 0.55:  # strong made hand -> ~half-pot value bet
            return _raise(min_raise_to + pot // 2, min_raise_to, all_in_to)
        return {"action": "check"}

    # --- facing a bet -------------------------------------------------------
    pot_odds = owed / (pot + owed)
    if preflop:
        if strength >= 0.78:  # premium -> ~3x the min-raise-to
            return _raise(3 * min_raise_to, min_raise_to, all_in_to)
        if strength >= 0.45 and pot_odds <= 0.33:  # playable + cheap -> call
            return {"action": "call"}
        return {"action": "fold"}

    if strength >= 0.85:  # monster -> raise ~pot
        return _raise(min_raise_to + pot, min_raise_to, all_in_to)
    if pot_odds <= strength * 0.60:  # price below a strength-scaled ceiling
        return {"action": "call"}
    return {"action": "fold"}


def decide(game_state: dict) -> dict:
    """Entry point. Defensive wrapper: on any unexpected error, take the free
    check if available, otherwise fold — never propagate (an exception would
    auto-fold anyway, but checking when free is strictly better)."""
    try:
        return _decide(game_state)
    except Exception:  # pragma: no cover - safety net
        if game_state.get("can_check") or game_state.get("amount_owed", 0) == 0:
            return {"action": "check"}
        return {"action": "fold"}
