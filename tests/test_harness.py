"""Tests for the harness: bb/100 math (hand-checked) + a short engine smoke run."""

import math

from harness import paths
from harness.metrics import aggregate, bb_per_100


# --- metrics math -----------------------------------------------------------

def test_bb_per_100_basic():
    # +4000 chips over 400 hands at BB=100 -> +40 bb over 400 hands -> +10 bb/100.
    assert bb_per_100(4000, 400, 100) == 10.0


def test_bb_per_100_sign_and_scale():
    assert bb_per_100(-2000, 200, 100) == -10.0
    assert bb_per_100(0, 400, 100) == 0.0
    # blind-size independence of the *definition*: same chips, BB=50 -> double.
    assert bb_per_100(4000, 400, 50) == 20.0


def test_bb_per_100_zero_hands_guard():
    assert bb_per_100(500, 0, 100) == 0.0


def test_aggregate_point_and_ci():
    out = aggregate([10.0, 10.0, 10.0])
    assert out["n"] == 3
    assert out["mean"] == 10.0
    assert out["se"] == 0.0
    assert out["ci95_low"] == 10.0 and out["ci95_high"] == 10.0


def test_aggregate_ci_width():
    out = aggregate([8.0, 12.0])  # mean 10, sample std 2.828..., se 2.0
    assert out["n"] == 2
    assert math.isclose(out["mean"], 10.0)
    assert math.isclose(out["se"], 2.0, rel_tol=1e-9)
    assert math.isclose(out["ci95_low"], 10.0 - 1.96 * 2.0)
    assert math.isclose(out["ci95_high"], 10.0 + 1.96 * 2.0)


def test_aggregate_empty():
    out = aggregate([])
    assert out == {"mean": 0.0, "se": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "n": 0}


# --- engine smoke -----------------------------------------------------------

def test_run_match_smoke():
    """One short real match (hero vs template) must complete with hero alive and
    error-free. This exercises the full subprocess path through runner.py."""
    bot_paths = {"hero": str(paths.HERO), "template": str(paths.REFERENCE_BOTS["template"])}
    result = paths.run_match("smoke", bot_paths, n_hands=15, seed=0)

    assert result["n_hands"] > 0
    assert set(result["chip_delta"]) == {"hero", "template"}
    # Chips are conserved (heads-up, no rake).
    assert result["chip_delta"]["hero"] + result["chip_delta"]["template"] == 0
    # Hero must not crash — a crashing bot silently auto-folds and tanks bb/100.
    assert result["bot_errors"]["hero"] == [], result["bot_errors"]["hero"]
