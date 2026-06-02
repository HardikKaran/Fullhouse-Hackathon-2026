"""bb/100 win-rate metric + 95% confidence interval over many matches.

The metric is defined in terms of the big blind so it survives a blind-size
change:

    bb_won            = chip_delta / big_blind
    bb_per_100(match) = bb_won * 100 / hands_played_in_match

Across M matches, each match's bb/100 is treated as one sample. Per-match
bb/100 is noisy; tight CIs need many matches. Per-hand bootstrapping is a later
refinement (out of scope for Step 1).
"""

import math
from statistics import mean, stdev


def bb_per_100(chip_delta: float, hands: int, big_blind: int) -> float:
    """Win rate of one match in big blinds per 100 hands."""
    if hands <= 0:
        return 0.0
    bb_won = chip_delta / big_blind
    return bb_won * 100.0 / hands


def aggregate(samples: list) -> dict:
    """Mean bb/100 across matches with a 95% normal CI.

    `se` uses the sample std (ddof=1). Returns mean/se/ci95_low/ci95_high/n.
    Degenerate cases (0 or 1 sample) collapse the CI to the point estimate.
    """
    n = len(samples)
    if n == 0:
        return {"mean": 0.0, "se": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "n": 0}
    m = mean(samples)
    if n == 1:
        return {"mean": m, "se": 0.0, "ci95_low": m, "ci95_high": m, "n": 1}
    se = stdev(samples) / math.sqrt(n)  # statistics.stdev is ddof=1
    half = 1.96 * se
    return {"mean": m, "se": se, "ci95_low": m - half, "ci95_high": m + half, "n": n}


def delta_stats(deltas: list) -> dict:
    """The qualifier's real ranking metric: **mean chip delta per match**.

    `deltas` are the raw per-match `chip_delta["hero"]` values (final stack minus
    the 10,000 starting stack), NOT bb/100. Unlike bb/100 this is exactly what the
    qualifier ranks on, but it is heavy-tailed — a few stacked-opponent matches
    dominate the mean — so its CI is wide; compare strategies over many matches.

    Returns mean / se / ci95_low / ci95_high (95% normal CI on the mean),
    `win_rate` = fraction of matches with a positive delta, and `n`.
    """
    n = len(deltas)
    if n == 0:
        return {"mean": 0.0, "se": 0.0, "ci95_low": 0.0, "ci95_high": 0.0,
                "win_rate": 0.0, "n": 0}
    m = mean(deltas)
    win_rate = sum(1 for d in deltas if d > 0) / n
    if n == 1:
        return {"mean": m, "se": 0.0, "ci95_low": m, "ci95_high": m,
                "win_rate": win_rate, "n": 1}
    se = stdev(deltas) / math.sqrt(n)
    half = 1.96 * se
    return {"mean": m, "se": se, "ci95_low": m - half, "ci95_high": m + half,
            "win_rate": win_rate, "n": n}
