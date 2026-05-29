"""Gauntlet: hero vs every reference bot (heads-up) + the 6-max table.

Prints one summary row per opponent plus a 6-max table row. Exits non-zero if
the hero produced any errors anywhere — a crashing bot must fail loudly rather
than quietly auto-fold and look like a strategy problem.

Trust the table row for ranking (it's the qualifier format); use the heads-up
rows for diagnosis against individual opponents.
"""

import argparse

from harness import paths
from harness.duel import duel
from harness.table import table

_HEADER = f"{'Opponent':<20} {'Matches':>7} {'Hands':>7} {'bb/100':>8}   {'95% CI':<20} {'Hero errors':>11}"


def _row(label, stats):
    ci = f"[{stats['ci95_low']:+.1f}, {stats['ci95_high']:+.1f}]"
    return (
        f"{label:<20} {stats['matches']:>7} {stats['total_hands']:>7} "
        f"{stats['mean']:>+8.1f}   {ci:<20} {stats['hero_errors']:>11}"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the hero against the full reference gauntlet.")
    ap.add_argument("--hero", default=str(paths.HERO))
    ap.add_argument("--matches", type=int, default=100)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--base-seed", type=int, default=0)
    args = ap.parse_args(argv)

    print(f"hero: {args.hero}")
    print(f"matches/opponent={args.matches}  hands/match={args.hands}  base_seed={args.base_seed}\n")
    print(_HEADER)
    print("-" * len(_HEADER))

    total_hero_errors = 0

    # Heads-up vs each reference bot.
    for name, vpath in paths.REFERENCE_BOTS.items():
        stats = duel(args.hero, vpath, args.matches, args.hands, args.base_seed)
        total_hero_errors += stats["hero_errors"]
        print(_row(name, stats))

    # 6-max table vs all five at once.
    print("-" * len(_HEADER))
    tstats = table(args.hero, list(paths.REFERENCE_BOTS.values()),
                   args.matches, args.hands, args.base_seed)
    total_hero_errors += tstats["hero_errors"]
    print(_row("6-max table", tstats))

    print()
    if total_hero_errors:
        print(f"FAIL: hero produced {total_hero_errors} error(s) across the gauntlet.")
        return 1
    print("OK: zero hero errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
