"""Watch hands play out live, with cards, made-hand labels and equity.

The duel/table commands run tens of thousands of hands and print one bb/100 with
a CI — great for ranking, useless for *seeing* what the bot does. This command
plays a small number of hands (default 10) and narrates each one: every player's
hole cards, the board street by street, the made hand each live player holds, the
equity, every action, and the result.

Why a separate command (not a --commentary flag on duel/table): per-street equity
is a Monte-Carlo sim; running it across a statistical batch would be far too slow
and would bury the signal. Watch is for eyeballing a handful of hands.

We drive the engine's ``PokerEngine`` directly in-process (so we can read *every*
player's real hole cards — bots only ever see their own) and reuse the engine's
``BotProcess`` for the sandboxed subprocess bot protocol. Nothing under
``vendor/fullhouse-engine/`` is modified.

Equity note: it is each live player's win% against the *number of opponents still
in the hand*, each assumed to hold a random hand. These are independent estimates,
so they will NOT sum to 100% across players — that's inherent to "vs random".
"""

import argparse
from pathlib import Path

from harness import paths  # noqa: F401  side effect: puts vendor engine on sys.path
from engine.game import PokerEngine  # noqa: E402
from sandbox.match import BotProcess, _inject_match_log  # noqa: E402
from harness import commentary  # noqa: E402


# ---------------------------------------------------------------------------
# Bot id helpers
# ---------------------------------------------------------------------------

def _unique_id(path, used) -> str:
    """Stable, unique bot_id from a bot path (its parent dir name, deduped)."""
    base = Path(path).parent.name or Path(path).stem
    vid = base
    k = 2
    while vid in used:
        vid = f"{base}_{k}"
        k += 1
    return vid


def _contenders(engine):
    """Live (not-yet-folded) players in seat order — the ones equity applies to."""
    return [p for p in engine.players if not p.is_folded]


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _print_hand_header(engine, hand_num, symbols):
    button = engine.players[engine.dealer_seat].bot_id
    print(f"=== Hand {hand_num + 1}  (button: {button}) ===")
    for p in engine.players:
        cards = commentary.pretty_cards(p.hole_cards, symbols)
        print(f"  seat{p.seat} {p.bot_id:<12} {cards:<8} stack {p.stack}")


def _print_street(engine, iters, symbols):
    board = commentary.pretty_cards(engine.community_cards, symbols)
    print(f"-- {engine.street.upper()}  [{board}]  pot {engine.pot} --")
    live = _contenders(engine)
    n_opp = len(live) - 1
    for p in live:
        made = commentary.describe_hand(p.hole_cards, engine.community_cards)
        eq = commentary.equity_vs_random(
            p.hole_cards, engine.community_cards, n_opp, iters=iters,
        )
        print(f"  {p.bot_id:<12} {made:<28} equity {eq:5.1f}%")


def _print_action(bot_id, action, engine):
    act = action.get("action", "?")
    amount = action.get("amount")
    label = f"{act} {amount}" if amount else act
    print(f"    {bot_id} {label}  (pot {engine.pot})")


def _print_result(result, symbols):
    # Sum awards per winner across main/side pots.
    won = {}
    for w in result.get("winners", []):
        won[w["bot_id"]] = won.get(w["bot_id"], 0) + w["amount"]
    summary = ", ".join(f"{bid} +{amt}" for bid, amt in won.items()) or "(none)"
    print(f"** RESULT: {summary} **")

    if result.get("showdown"):
        strengths = result.get("hand_strengths", {})
        reveals = []
        for bid, cards in result.get("revealed_cards", {}).items():
            pretty = commentary.pretty_str_cards(cards, symbols)
            label = strengths.get(bid, "")
            reveals.append(f"{bid} {pretty}" + (f" ({label})" if label else ""))
        if reveals:
            print("   showdown: " + "   ".join(reveals))

    stacks = result.get("final_stacks", {})
    print("   stacks: " + "  ".join(f"{bid} {s}" for bid, s in stacks.items()))


# ---------------------------------------------------------------------------
# Play loop (commentated mirror of sandbox.match._play_hand)
# ---------------------------------------------------------------------------

def play_hand(engine, procs, bot_ids, match_action_log, hand_num, iters, symbols):
    state = _inject_match_log(engine.start_hand(), match_action_log)

    _print_hand_header(engine, hand_num, symbols)

    last_street = None
    steps = 0
    while state.get("type") == "action_request":
        if state["street"] != last_street:
            _print_street(engine, iters, symbols)
            last_street = state["street"]

        seat = state["seat_to_act"]
        bot_id = bot_ids[seat]
        action = procs[bot_id].act(state)

        match_action_log.append({
            "hand_num": hand_num,
            "seat": seat,
            "bot_id": bot_id,
            "action": action.get("action"),
            "amount": action.get("amount"),
        })

        state = _inject_match_log(engine.apply_action(seat, action), match_action_log)
        _print_action(bot_id, action, engine)

        steps += 1
        if steps > 1000:
            raise RuntimeError("Hand exceeded 1000 steps: " + engine.hand_id)

    # All-in run-outs jump to showdown with no action_request for the final
    # streets — show the final board + equity once before the result.
    if engine.street != last_street:
        _print_street(engine, iters, symbols)
    _print_result(state, symbols)
    return state


# ---------------------------------------------------------------------------
# Match driver (one match, in-process; mirrors run_match's skeleton)
# ---------------------------------------------------------------------------

def watch(hero_path, villain_paths, hands=10, base_seed=0, iters=2000, symbols=True):
    bot_paths = {"hero": str(hero_path)}
    used = {"hero"}
    for vp in villain_paths:
        vid = _unique_id(vp, used)
        used.add(vid)
        bot_paths[vid] = str(vp)
    bot_ids = list(bot_paths.keys())

    procs = {bid: BotProcess(bid, p) for bid, p in bot_paths.items()}
    stacks = {bid: paths.STARTING_STACK for bid in bot_ids}
    match_action_log = []
    dealer = 0

    # Warm up bots (heavy imports / lookup tables) before hand 1, same as run_match.
    for p in procs.values():
        p.warmup()

    try:
        for hand_num in range(hands):
            alive = [bid for bid in bot_ids if stacks[bid] > 0]
            if len(alive) < 2:
                print("(only one bot has chips left — match over)")
                break

            engine = PokerEngine(
                hand_id=f"watch_h{hand_num:04d}",
                bot_ids=alive,
                dealer_seat=dealer % len(alive),
                starting_stacks={bid: stacks[bid] for bid in alive},
                seed=base_seed * 1000003 + hand_num,
            )
            result = play_hand(engine, procs, alive, match_action_log, hand_num, iters, symbols)
            for bid, s in result["final_stacks"].items():
                stacks[bid] = s
            dealer += 1
            print()
    finally:
        for p in procs.values():
            p.stop()

    print("=== final stacks ===")
    for bid, s in sorted(stacks.items(), key=lambda x: -x[1]):
        delta = s - paths.STARTING_STACK
        print(f"  {bid:<12} {s:>7}  ({delta:+d})")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Watch hands play out live with cards, made-hand and equity commentary."
    )
    ap.add_argument("--hero", default=str(paths.HERO))
    ap.add_argument(
        "--villains",
        nargs="*",
        default=[str(paths.REFERENCE_BOTS["aggressor"])],
        help="One or more villain bot paths (default: the aggressor reference bot).",
    )
    ap.add_argument(
        "--villain",
        default=None,
        help="Convenience alias for a single villain (matches harness.duel).",
    )
    ap.add_argument("--hands", type=int, default=10)
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--equity-iters", type=int, default=2000,
                    help="Monte-Carlo samples per equity estimate (default 2000 ≈ ±1%%).")
    ap.add_argument("--no-symbols", action="store_true",
                    help="Print plain 'As' instead of A♠ (terminals without unicode).")
    args = ap.parse_args(argv)

    villains = [args.villain] if args.villain else args.villains
    watch(
        args.hero, villains,
        hands=args.hands,
        base_seed=args.base_seed,
        iters=args.equity_iters,
        symbols=not args.no_symbols,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
