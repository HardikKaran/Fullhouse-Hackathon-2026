"""Heads-up, seat-rotated, multi-match duel: hero vs one villain.

Clean 1v1 signal of the hero against a single opponent. Seat order is alternated
across matches to cancel any residual positional/blind bias, and each match uses
a deterministic seed for reproducible aggregation.
"""

import argparse
import sys

from harness import paths
from harness.metrics import aggregate, bb_per_100


def duel(hero_path, villain_path, matches=100, hands=400, base_seed=0, verbose=False):
    """Run `matches` heads-up matches and aggregate the hero's bb/100.

    Returns the dict from metrics.aggregate(...) extended with match count,
    total hands actually played, and per-side error counts.
    """
    hero_path = str(hero_path)
    villain_path = str(villain_path)

    samples = []
    total_hands = 0
    hero_errors = 0
    villain_errors = 0

    for i in range(matches):
        # Alternate seat order across matches. The bot_id keys stay stable
        # ("hero"/"villain") so chip_delta lookups are seat-independent; only the
        # dict insertion order (== seat order in the engine) changes.
        if i % 2 == 0:
            bot_paths = {"hero": hero_path, "villain": villain_path}
        else:
            bot_paths = {"villain": villain_path, "hero": hero_path}

        result = paths.run_match(f"duel_{i}", bot_paths, n_hands=hands, seed=base_seed + i)

        n = result["n_hands"]
        delta = result["chip_delta"]["hero"]
        samples.append(bb_per_100(delta, n, paths.BIG_BLIND))
        total_hands += n

        h_errs = result["bot_errors"].get("hero") or []
        v_errs = result["bot_errors"].get("villain") or []
        hero_errors += len(h_errs)
        villain_errors += len(v_errs)
        if h_errs and verbose:
            print(f"  [warn] duel match {i}: hero errors: {h_errs[:3]}", file=sys.stderr)

    stats = aggregate(samples)
    stats.update(
        matches=matches,
        total_hands=total_hands,
        hero_errors=hero_errors,
        villain_errors=villain_errors,
    )
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Heads-up duel: hero vs one villain.")
    ap.add_argument("--hero", default=str(paths.HERO))
    ap.add_argument("--villain", required=True)
    ap.add_argument("--matches", type=int, default=100)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    stats = duel(args.hero, args.villain, args.matches, args.hands, args.base_seed, args.verbose)

    print(f"hero:    {args.hero}")
    print(f"villain: {args.villain}")
    print(f"matches={stats['matches']}  hands={stats['total_hands']}")
    print(
        f"bb/100 = {stats['mean']:+.2f}   "
        f"95% CI [{stats['ci95_low']:+.2f}, {stats['ci95_high']:+.2f}]"
    )
    print(f"hero errors: {stats['hero_errors']}   villain errors: {stats['villain_errors']}")

    # A crashing hero must fail loudly: silent auto-folds look like bad strategy.
    return 0 if stats["hero_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
