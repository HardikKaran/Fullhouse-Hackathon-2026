"""6-max table: hero vs five reference bots, seat-rotated across matches.

This is the format that actually matters for the qualifier. The hero's seat is
rotated across matches (seat == i % n_seats) to cancel positional bias, and each
match is seeded for reproducible aggregation.
"""

import argparse
import sys
from pathlib import Path

from harness import paths
from harness.metrics import aggregate, bb_per_100, delta_stats


def _unique_id(path, used):
    """Stable, unique bot_id from a bot path (its parent dir name, deduped)."""
    base = Path(path).parent.name or Path(path).stem
    vid = base
    k = 2
    while vid in used:
        vid = f"{base}_{k}"
        k += 1
    return vid


def table(hero_path, villain_paths, matches=100, hands=400, base_seed=0, verbose=False):
    """Seat the hero + villains at one table for `matches` matches and aggregate
    the hero's bb/100. Returns metrics.aggregate(...) extended with match count,
    total hands, hero error count, and the number of seats."""
    hero_path = str(hero_path)
    villain_paths = [str(v) for v in villain_paths]
    n_seats = len(villain_paths) + 1

    # Assign each villain a stable unique id once (their seat order rotates only
    # by where we insert the hero).
    used = {"hero"}
    villain_entries = []
    for vp in villain_paths:
        vid = _unique_id(vp, used)
        used.add(vid)
        villain_entries.append((vid, vp))

    samples = []
    deltas = []
    total_hands = 0
    hero_errors = 0

    for i in range(matches):
        seat = i % n_seats
        entries = list(villain_entries)
        entries.insert(seat, ("hero", hero_path))  # dict order == engine seat order
        bot_paths = dict(entries)

        result = paths.run_match(f"table_{i}", bot_paths, n_hands=hands, seed=base_seed + i)

        n = result["n_hands"]
        delta = result["chip_delta"]["hero"]
        samples.append(bb_per_100(delta, n, paths.BIG_BLIND))
        deltas.append(delta)
        total_hands += n

        h_errs = result["bot_errors"].get("hero") or []
        hero_errors += len(h_errs)
        if h_errs and verbose:
            print(f"  [warn] table match {i}: hero errors: {h_errs[:3]}", file=sys.stderr)

    stats = aggregate(samples)
    stats.update(
        matches=matches,
        total_hands=total_hands,
        hero_errors=hero_errors,
        seats=n_seats,
        delta=delta_stats(deltas),
    )
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="6-max table: hero vs reference bots.")
    ap.add_argument("--hero", default=str(paths.HERO))
    ap.add_argument(
        "--villains",
        nargs="*",
        default=[str(p) for p in paths.REFERENCE_BOTS.values()],
        help="Villain bot paths (default: all five reference bots).",
    )
    ap.add_argument("--matches", type=int, default=100)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    stats = table(args.hero, args.villains, args.matches, args.hands, args.base_seed, args.verbose)

    print(f"hero: {args.hero}")
    print(f"seats={stats['seats']}  matches={stats['matches']}  hands={stats['total_hands']}")
    d = stats["delta"]
    print(
        f"avg Δ/match = {d['mean']:+.0f}   "
        f"95% CI [{d['ci95_low']:+.0f}, {d['ci95_high']:+.0f}]   "
        f"win-rate {d['win_rate']*100:.0f}%   "
        f"(ranking metric)"
    )
    print(
        f"bb/100 = {stats['mean']:+.2f}   "
        f"95% CI [{stats['ci95_low']:+.2f}, {stats['ci95_high']:+.2f}]"
    )
    print(f"hero errors: {stats['hero_errors']}")
    return 0 if stats["hero_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
