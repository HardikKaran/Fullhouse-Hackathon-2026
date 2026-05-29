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
