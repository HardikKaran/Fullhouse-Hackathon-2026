"""In-process leak diagnosis for the hero bot (PLAN_maximize_chip_delta §A).

Runs matches by driving the vendored `PokerEngine` DIRECTLY (no subprocess),
replicating `sandbox/match.py`'s hand loop exactly — including the per-match
rolling `match_action_log` injection — so the hero sees the real game-state
contract. The hero's `decide()` is called in-process, which lets us instrument
every decision with zero changes to the shipped `bot.py`.

We tally, over a run:
  * preflop steal frequency (open-raise vs fold when first-in),
  * c-bet behaviour as the preflop aggressor (bet vs check when checked to),
  * postflop check-backs and their equity (chips left on the table),
  * facing-a-bet folds bucketed by (raw_eq - pot_odds) (the +cEV-fold leak),
  * chips won/lost bucketed by hero's preflop posture,
  * how the bot's own model classifies each villain (sanity).

This measures DECISION LOGIC, not latency: in-process MC runs at full CPU, so we
lower POSTFLOP_ITERS for speed (equity precision is plenty for leak diagnosis).

Usage:
    python -m harness.diagnose --layout table --matches 40 --base-seed 9000
    python -m harness.diagnose --layout duel --villain aggressor --matches 40
"""

import argparse
import importlib.util
from collections import defaultdict

from harness import paths
from engine.game import PokerEngine, STARTING_STACK
from sandbox.match import MATCH_LOG_MAX_ENTRIES


def _load(path, modname):
    spec = importlib.util.spec_from_file_location(modname, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _inject(state, match_log):
    if state.get("type") == "action_request":
        state["match_action_log"] = match_log[-MATCH_LOG_MAX_ENTRIES:]
    return state


class Tally:
    def __init__(self):
        # preflop
        self.pf_firstin_spots = 0      # unraised pot, hero first voluntary actor
        self.pf_firstin_open = 0       # ... and hero open-raised
        self.pf_firstin_limpcheck = 0  # ... and hero checked/limped
        self.pf_firstin_fold = 0       # ... and hero folded
        # c-bet (hero was preflop raiser, checked to postflop)
        self.cbet_spots = defaultdict(int)   # street -> count
        self.cbet_bet = defaultdict(int)      # street -> hero bet/raised
        self.cbet_check = defaultdict(int)    # street -> hero checked
        # check-backs (can_check, NOT necessarily pf aggressor): eq distribution
        self.checkback_eq = []
        self.bet_eq = []
        # facing a bet
        self.face_fold = 0
        self.face_call = 0
        self.face_raise = 0
        self.fold_surplus = []   # (raw_eq - pot_odds) on folds; >0 means folded +cEV-by-raw
        # chips by posture
        self.delta_pf_raise = 0.0
        self.n_pf_raise = 0
        self.delta_pf_passive = 0.0   # limp/call/check into flop
        self.n_pf_passive = 0
        self.delta_pf_fold = 0.0
        self.n_pf_fold = 0
        # classification sanity: villain bot_id -> archetype histogram (end of match)
        self.arch = defaultdict(lambda: defaultdict(int))
        self.n_decisions = 0


def diagnose(hero_path, villain_paths, matches, n_hands, base_seed, iters):
    hero = _load(hero_path, "hero_bot")
    hero.POSTFLOP_ITERS = iters
    hero.BUDGET_S = 5.0  # never hit the wall-clock cap in-process; iters is the cap

    # stash last computed equity so the loop can read it after decide()
    _last = {"eq": None}
    _orig_rand = hero._equity_vs_random
    _orig_rng = hero._equity_vs_ranges

    def _wrap_rand(*a, **k):
        v = _orig_rand(*a, **k)
        _last["eq"] = v
        return v

    def _wrap_rng(*a, **k):
        v = _orig_rng(*a, **k)
        _last["eq"] = v
        return v

    hero._equity_vs_random = _wrap_rand
    hero._equity_vs_ranges = _wrap_rng

    villains = {name: _load(p, f"v_{name}") for name, p in villain_paths}

    T = Tally()

    for m in range(matches):
        seed = base_seed + m
        # rotate hero seat across matches (mirrors table_jobs)
        names = [n for n, _ in villain_paths]
        n_seats = len(names) + 1
        seat = m % n_seats
        order = list(names)
        order.insert(seat, "hero")
        stacks = {bid: STARTING_STACK for bid in order}
        match_log = []
        dealer = 0

        for hand_num in range(n_hands):
            alive = [bid for bid in order if stacks[bid] > 0]
            if len(alive) < 2:
                break
            engine = PokerEngine(
                hand_id=f"d{m}_h{hand_num}",
                bot_ids=alive,
                dealer_seat=dealer % len(alive),
                starting_stacks={bid: stacks[bid] for bid in alive},
                seed=seed * 1000003 + hand_num,
            )
            hero_start = stacks.get("hero", 0)
            hero_alive = "hero" in alive
            hero_pf_raised = False
            hero_folded_pf = False  # hero folded preflop (out of the hand)

            state = _inject(engine.start_hand(), match_log)
            while state.get("type") == "action_request":
                s = state["seat_to_act"]
                bid = alive[s]
                if bid == "hero":
                    action = _instrument_hero(hero, state, engine, _last, T,
                                              hero_pf_raised)
                    act = action.get("action")
                    if engine.street == "preflop":
                        if act in ("raise", "all_in"):
                            hero_pf_raised = True
                        elif act == "fold":
                            hero_folded_pf = True
                else:
                    action = villains[bid].decide(state)
                match_log.append({
                    "hand_num": hand_num, "seat": s, "bot_id": bid,
                    "action": action.get("action"), "amount": action.get("amount"),
                })
                state = _inject(engine.apply_action(s, action), match_log)

            for b, sv in state["final_stacks"].items():
                stacks[b] = sv
            dealer += 1

            if hero_alive:
                d = stacks.get("hero", 0) - hero_start
                if hero_pf_raised:
                    T.delta_pf_raise += d
                    T.n_pf_raise += 1
                elif hero_folded_pf:
                    T.delta_pf_fold += d
                    T.n_pf_fold += 1
                else:  # called, checked the BB option, or limped — saw a flop passively
                    T.delta_pf_passive += d
                    T.n_pf_passive += 1

        # end-of-match classification snapshot
        try:
            fake = {"players": [{"seat": i, "bot_id": b} for i, b in enumerate(order)],
                    "seat_to_act": order.index("hero") if "hero" in order else -1,
                    "match_action_log": match_log}
            model = hero._build_model(fake)
            for b in names:
                p = model.get(b)
                if p:
                    T.arch[b][p["archetype"]] += 1
        except Exception:
            pass

    return T


def _instrument_hero(hero, state, engine, _last, T, hero_pf_raised):
    T.n_decisions += 1
    street = engine.street
    can_check = state.get("can_check", state.get("amount_owed", 0) == 0)
    _last["eq"] = None
    action = hero.decide(state)
    act = action.get("action")
    eq = _last["eq"]

    if street == "preflop":
        # "first-in" = unopened pot (no raise beyond the BB yet this street)
        current_bet = state.get("current_bet", 0)
        bb = hero._big_blind(state)
        raised = current_bet > bb
        owed = state.get("amount_owed", 0)
        if not raised:
            T.pf_firstin_spots += 1
            if act in ("raise", "all_in"):
                T.pf_firstin_open += 1
            elif act in ("check", "call"):
                T.pf_firstin_limpcheck += 1
            else:
                T.pf_firstin_fold += 1
        return action

    # postflop
    if can_check:
        if hero_pf_raised:
            T.cbet_spots[street] += 1
            if act in ("raise", "all_in"):
                T.cbet_bet[street] += 1
            else:
                T.cbet_check[street] += 1
        if act in ("check",) and eq is not None:
            T.checkback_eq.append(eq)
        elif act in ("raise", "all_in") and eq is not None:
            T.bet_eq.append(eq)
    else:
        pot = max(1, state.get("pot", 0))
        owed = state.get("amount_owed", 0)
        pot_odds = owed / (pot + owed) if (pot + owed) > 0 else 1.0
        if act == "fold":
            T.face_fold += 1
            if eq is not None:
                T.fold_surplus.append(eq - pot_odds)
        elif act == "call":
            T.face_call += 1
        elif act in ("raise", "all_in"):
            T.face_raise += 1
    return action


def _pct(a, b):
    return f"{(100.0 * a / b):.0f}%" if b else "n/a"


def _hist(vals, edges):
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        c = sum(1 for v in vals if lo <= v < hi)
        out.append(f"[{lo:+.2f},{hi:+.2f}): {c}")
    return "  ".join(out)


def report(T):
    print("\n================ HERO DECISION DIAGNOSTIC ================")
    print(f"total hero decisions: {T.n_decisions}")

    print("\n-- Preflop, unopened pot (steal opportunities) --")
    s = T.pf_firstin_spots
    print(f"  first-in spots: {s}")
    print(f"  open-raised : {T.pf_firstin_open}  ({_pct(T.pf_firstin_open, s)})")
    print(f"  limp/check  : {T.pf_firstin_limpcheck}  ({_pct(T.pf_firstin_limpcheck, s)})")
    print(f"  folded      : {T.pf_firstin_fold}  ({_pct(T.pf_firstin_fold, s)})")

    print("\n-- C-bet as preflop aggressor (checked to us) --")
    for st in ("flop", "turn", "river"):
        sp = T.cbet_spots[st]
        if sp:
            print(f"  {st:5s}: spots={sp:4d}  bet={T.cbet_bet[st]} ({_pct(T.cbet_bet[st], sp)})  "
                  f"check={T.cbet_check[st]} ({_pct(T.cbet_check[st], sp)})")

    print("\n-- Check-backs vs bets (raw vs-random eq distribution) --")
    if T.checkback_eq:
        cb = T.checkback_eq
        print(f"  checked back: n={len(cb)}  mean_eq={sum(cb)/len(cb):.2f}  "
              f"eq>=0.55: {sum(1 for e in cb if e >= 0.55)}  eq>=0.65: {sum(1 for e in cb if e >= 0.65)}")
    if T.bet_eq:
        be = T.bet_eq
        print(f"  bet/raised : n={len(be)}  mean_eq={sum(be)/len(be):.2f}")

    print("\n-- Facing a bet --")
    tot = T.face_fold + T.face_call + T.face_raise
    print(f"  fold={T.face_fold} ({_pct(T.face_fold, tot)})  "
          f"call={T.face_call} ({_pct(T.face_call, tot)})  "
          f"raise={T.face_raise} ({_pct(T.face_raise, tot)})")
    if T.fold_surplus:
        fs = T.fold_surplus
        pos = [x for x in fs if x > 0]
        print(f"  folds with raw_eq>pot_odds (optimistic +cEV-fold flag): "
              f"{len(pos)}/{len(fs)} ({_pct(len(pos), len(fs))})")
        print(f"  fold (raw_eq - pot_odds) histogram:")
        print("    " + _hist(fs, [-1.0, -0.3, -0.15, -0.05, 0.0, 0.05, 0.15, 0.3, 1.0]))

    print("\n-- Chips by hero preflop posture (avg per hand) --")
    def avg(d, n):
        return f"{d/n:+.0f} over {n}" if n else "n/a"
    print(f"  pf-raise hands  : {avg(T.delta_pf_raise, T.n_pf_raise)}")
    print(f"  pf-passive hands: {avg(T.delta_pf_passive, T.n_pf_passive)}")
    print(f"  pf-fold hands   : {avg(T.delta_pf_fold, T.n_pf_fold)}")

    print("\n-- Villain classification (end-of-match archetype counts) --")
    for b, h in sorted(T.arch.items()):
        print(f"  {b:16s}: {dict(h)}")
    print("==========================================================\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", default=str(paths.HERO))
    ap.add_argument("--layout", choices=["table", "duel"], default="table")
    ap.add_argument("--villain", help="duel: reference bot name")
    ap.add_argument("--matches", type=int, default=40)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--base-seed", type=int, default=9000)
    ap.add_argument("--iters", type=int, default=1500)
    args = ap.parse_args(argv)

    if args.layout == "duel":
        name = args.villain or "aggressor"
        vps = [(name, paths.REFERENCE_BOTS[name])]
    else:
        vps = [(n, p) for n, p in paths.REFERENCE_BOTS.items()]

    print(f"hero={args.hero}  layout={args.layout}  matches={args.matches}  "
          f"hands={args.hands}  iters={args.iters}")
    T = diagnose(args.hero, vps, args.matches, args.hands, args.base_seed, args.iters)
    report(T)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
