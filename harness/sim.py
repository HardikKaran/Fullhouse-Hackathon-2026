"""Parallel match evaluation — the heavy-run workhorse for Tier 2/3 gating.

`harness.duel` / `harness.table` run matches in a single process; that is fine
for a few matches but the plan's gates need **≥80** (Tier 2) and **≥300**
(Tier 3) matches, and the heavy-tailed `avg Δ/match` metric needs even more to
get a tight CI. Each match is independent (its own seed + bot subprocesses), so
we fan them out across a `ProcessPoolExecutor`.

Both seat layouts are supported:
  * **duel**  — hero vs one villain, seat order alternated across matches.
  * **table** — hero vs N villains, hero's seat rotated across matches.

Every comparative run (baseline vs Tier-2, vs the balanced villain) MUST use the
same `--workers` so CPU contention affects the hero's wall-clock MC budget
identically on both sides — the comparison is what matters, not the absolute
iteration count (the real sandbox uses a different CPU cap anyway).

Reported numbers: **avg Δ/match** (mean raw chip delta — the ranking metric)
with a 95% CI and win-rate, plus bb/100 as a lower-variance secondary signal.
"""

import argparse
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import mean, stdev

from harness import paths
from harness.metrics import aggregate, bb_per_100, delta_stats


# --------------------------------------------------------------------------- #
# Worker (must be top-level for ProcessPoolExecutor pickling)
# --------------------------------------------------------------------------- #
def _run_one(job):
    """Run a single match. `job` = (match_id, entries, n_hands, seed) where
    `entries` is an ordered list of (bot_id, path) tuples — dict insertion order
    is the engine's seat order, so the hero's seat is set by where it appears."""
    match_id, entries, n_hands, seed = job
    bot_paths = dict(entries)
    result = paths.run_match(match_id, bot_paths, n_hands=n_hands, seed=seed)
    delta = result["chip_delta"]["hero"]
    n = result["n_hands"]
    h_errs = result["bot_errors"].get("hero") or []
    return delta, n, len(h_errs), h_errs[:3]


def _duel_jobs(hero, villain, matches, hands, base_seed):
    hero, villain = str(hero), str(villain)
    jobs = []
    for i in range(matches):
        if i % 2 == 0:
            entries = [("hero", hero), ("villain", villain)]
        else:
            entries = [("villain", villain), ("hero", hero)]
        jobs.append((f"duel_{i}", entries, hands, base_seed + i))
    return jobs


def _table_jobs(hero, villains, matches, hands, base_seed):
    hero = str(hero)
    villains = [str(v) for v in villains]
    n_seats = len(villains) + 1
    used = {"hero"}
    vent = []
    for vp in villains:
        base = Path(vp).parent.name or Path(vp).stem
        vid, k = base, 2
        while vid in used:
            vid, k = f"{base}_{k}", k + 1
        used.add(vid)
        vent.append((vid, vp))
    jobs = []
    for i in range(matches):
        seat = i % n_seats
        entries = list(vent)
        entries.insert(seat, ("hero", hero))
        jobs.append((f"table_{i}", entries, hands, base_seed + i))
    return jobs


def evaluate(jobs, workers=14, verbose=False):
    """Map `jobs` across a process pool; aggregate the hero's results.

    Returns a dict with `delta` (delta_stats — the ranking metric), top-level
    bb/100 aggregate fields, match/hand counts, and hero error count.
    """
    deltas, samples = [], []
    total_hands = hero_errors = 0
    workers = max(1, min(workers, len(jobs)))

    with ProcessPoolExecutor(max_workers=workers) as ex:
        for delta, n, n_err, sample_errs in ex.map(_run_one, jobs):
            deltas.append(delta)
            samples.append(bb_per_100(delta, n, paths.BIG_BLIND))
            total_hands += n
            hero_errors += n_err
            if n_err and verbose:
                print(f"  [warn] hero errors: {sample_errs}", file=sys.stderr)

    stats = aggregate(samples)
    stats.update(
        matches=len(jobs),
        total_hands=total_hands,
        hero_errors=hero_errors,
        delta=delta_stats(deltas),
        deltas=deltas,
    )
    return stats


def paired_compare(jobs_a, jobs_b, workers=14, verbose=False):
    """Run candidate A and candidate B on **identical seeds/seat layouts** and
    report the paired per-match difference (A − B). Because both bots see the
    same boards, card variance cancels — this detects a real Δ edge with far
    fewer matches than two independent runs. `jobs_a`/`jobs_b` must be aligned
    job lists differing only in the hero path."""
    a = evaluate(jobs_a, workers, verbose)
    b = evaluate(jobs_b, workers, verbose)
    diffs = [x - y for x, y in zip(a["deltas"], b["deltas"])]
    n = len(diffs)
    m = mean(diffs)
    se = (stdev(diffs) / math.sqrt(n)) if n > 1 else 0.0
    return {
        "a": a, "b": b, "n": n,
        "diff_mean": m, "diff_se": se,
        "diff_ci_low": m - 1.96 * se, "diff_ci_high": m + 1.96 * se,
        "a_better_rate": sum(1 for d in diffs if d > 0) / n if n else 0.0,
    }


def _print(label, stats):
    d = stats["delta"]
    print(f"\n=== {label} ===")
    print(f"matches={stats['matches']}  hands={stats['total_hands']}  "
          f"hero_errors={stats['hero_errors']}")
    print(f"avg Δ/match = {d['mean']:+.0f}   "
          f"95% CI [{d['ci95_low']:+.0f}, {d['ci95_high']:+.0f}]   "
          f"win-rate {d['win_rate']*100:.0f}%   <-- ranking metric")
    print(f"bb/100      = {stats['mean']:+.2f}   "
          f"95% CI [{stats['ci95_low']:+.2f}, {stats['ci95_high']:+.2f}]")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Parallel match evaluation (avg Δ/match).")
    ap.add_argument("mode", choices=["table", "duel", "gauntlet", "compare"])
    ap.add_argument("--hero", default=str(paths.HERO))
    ap.add_argument("--hero-b", help="compare mode: the baseline/other hero path")
    ap.add_argument("--layout", choices=["table", "duel"], default="table",
                    help="compare mode: seat layout to run both heroes in")
    ap.add_argument("--villain", help="duel mode: one villain path")
    ap.add_argument("--villains", nargs="*",
                    default=[str(p) for p in paths.REFERENCE_BOTS.values()],
                    help="table mode: villain paths (default: 5 reference bots)")
    ap.add_argument("--matches", type=int, default=100)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    print(f"hero: {args.hero}   workers={args.workers}")

    if args.mode == "duel":
        if not args.villain:
            ap.error("duel mode needs --villain")
        jobs = _duel_jobs(args.hero, args.villain, args.matches, args.hands, args.base_seed)
        stats = evaluate(jobs, args.workers, args.verbose)
        _print(f"DUEL hero vs {Path(args.villain).parent.name}", stats)

    elif args.mode == "table":
        jobs = _table_jobs(args.hero, args.villains, args.matches, args.hands, args.base_seed)
        stats = evaluate(jobs, args.workers, args.verbose)
        _print(f"6-max TABLE ({len(args.villains)+1} seats)", stats)

    elif args.mode == "gauntlet":  # heads-up vs each reference bot + the 6-max table
        for name, vpath in paths.REFERENCE_BOTS.items():
            jobs = _duel_jobs(args.hero, vpath, args.matches, args.hands, args.base_seed)
            _print(f"DUEL vs {name}", evaluate(jobs, args.workers, args.verbose))
        jobs = _table_jobs(args.hero, list(paths.REFERENCE_BOTS.values()),
                           args.matches, args.hands, args.base_seed)
        _print("6-max TABLE (all refs)", evaluate(jobs, args.workers, args.verbose))

    else:  # compare: hero (A) vs hero-b (B) on identical seeds, paired diff
        if not args.hero_b:
            ap.error("compare mode needs --hero-b")
        if args.layout == "duel":
            if not args.villain:
                ap.error("compare --layout duel needs --villain")
            jobs_a = _duel_jobs(args.hero, args.villain, args.matches, args.hands, args.base_seed)
            jobs_b = _duel_jobs(args.hero_b, args.villain, args.matches, args.hands, args.base_seed)
        else:
            jobs_a = _table_jobs(args.hero, args.villains, args.matches, args.hands, args.base_seed)
            jobs_b = _table_jobs(args.hero_b, args.villains, args.matches, args.hands, args.base_seed)
        r = paired_compare(jobs_a, jobs_b, args.workers, args.verbose)
        _print(f"A = {Path(args.hero).name}", r["a"])
        _print(f"B = {Path(args.hero_b).name}", r["b"])
        print(f"\n=== PAIRED  A − B  (n={r['n']}, same seeds) ===")
        print(f"mean ΔΔ = {r['diff_mean']:+.0f}   "
              f"95% CI [{r['diff_ci_low']:+.0f}, {r['diff_ci_high']:+.0f}]   "
              f"A-better-rate {r['a_better_rate']*100:.0f}%")
        sig = "A > B (CI excludes 0)" if r["diff_ci_low"] > 0 else (
              "B > A (CI excludes 0)" if r["diff_ci_high"] < 0 else "inconclusive (CI spans 0)")
        print(f"verdict: {sig}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
