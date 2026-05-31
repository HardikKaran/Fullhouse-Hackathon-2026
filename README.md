# Fullhouse-Hackathon-2026

Building a poker bot (poker... I barely know her!)

A local dev harness that runs **my bot** against the frozen Fullhouse reference
bots and measures win rate in **bb/100** with 95% confidence intervals — both
heads-up and at a 6-max table. This is Step 1 of the build order: the repeatable
measurement loop every future strategy change regresses against.

We do **not** reimplement the engine — we vendor the official one as a git
submodule and wrap a harness around it.

## Layout

```
vendor/fullhouse-engine/   frozen upstream engine (git submodule)
src/mybot/bot.py           my bot (a simple v0 baseline for now)
harness/
  paths.py                 sys.path bootstrap + engine constants + bot paths
  metrics.py               bb/100 + confidence interval math
  duel.py                  heads-up, seat-rotated, multi-match
  table.py                 6-max: my bot vs 5 reference bots
  gauntlet.py              my bot vs each reference bot -> summary table
scripts/setup_env.sh       one-shot venv + deps + eval7 two-step
tests/test_harness.py      metrics math + a short engine smoke run
```

## Setup

```bash
git submodule update --init --recursive   # if you just cloned
bash scripts/setup_env.sh
source .venv/bin/activate
```

### Why Python 3.10, and how we get it (resolves PLAN §10)

`eval7==0.1.7` ships pre-generated Cython C that references `longintrepr.h`,
removed in CPython 3.11. It only builds on **3.10**, and the tournament sandbox
pins `python:3.10-slim`, so we match it locally.

This machine has no `python3.10` and no passwordless `sudo` to `apt-get` the
CPython build deps (libffi/sqlite/…), so a pyenv/deadsnakes source build isn't
viable (it'd yield an interpreter missing `_ctypes`/`sqlite3`). Instead we use
[**uv**](https://astral.sh/uv), which downloads a *prebuilt standalone* CPython
3.10 with every stdlib C module intact — no compiler, no sudo:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # one-time, installs ~/.local/bin/uv
```

`scripts/setup_env.sh` auto-detects `uv` (or falls back to a system `python3.10`
if you have one), creates `.venv`, then installs `eval7` via its required
two-step: `Cython<3` first, then `eval7 --no-build-isolation`.

## Usage

```bash
# Heads-up: my bot vs one reference bot
python -m harness.duel --villain vendor/fullhouse-engine/bots/aggressor/bot.py \
    --matches 50 --hands 400

# 6-max table: my bot vs all five reference bots
python -m harness.table --matches 50 --hands 400

# Full gauntlet: heads-up vs each reference bot + the 6-max table
python -m harness.gauntlet --matches 100 --hands 400

# Validate my bot against the real submission gate
python vendor/fullhouse-engine/sandbox/validator.py src/mybot/bot.py

# Tests
pytest
```

`bb/100` is per-match-noisy; start at `--matches 100` and bump to 300–500 if a
CI straddles 0 and you need the sign. `n_hands` per match varies (a bot can bust
and end a match early), so the harness always reads it from the result. Trust
the **6-max table** row for ranking (it's the qualifier format); use the
heads-up rows for diagnosis. Any hero error makes `gauntlet`/`duel` exit
non-zero — a crashing bot must fail loudly, not quietly auto-fold.

## Equity engine — verify & benchmark

The Monte-Carlo equity engine is in `src/mybot/equity.py`: `mc_equity_vs_hand`
(hero vs a known hand) and `mc_equity_vs_random` (hero vs N uniformly-random
opponents), both returning `{equity, win, tie, loss, iters, ...}`. The exhaustive
`equity_exact_headsup` is the offline oracle they are checked against.

    source .venv/bin/activate
    pytest tests/test_montecarlo.py -v      # unit tests vs published equities
    python bench/equity_report.py           # verification table + latency table

Expected: all preflop matchups PASS within ±1.0% (AKs vs QQ ~46%, AA vs KK ~82%,
AA vs AKs ~88%, JJ vs AKs ~54%, AKo vs QQ ~43%, AA vs 72o ~88%). The report exits
`0` only if every row passes. If a row **FAILS**, the sampler/deck/counting is
wrong — do **not** widen the tolerance.

Recommended ~50,000 iters/decision keeps `decide()` under the 2 s / 0.5 CPU
tournament budget (see the latency table). `mc_equity_vs_random` also takes an
optional `deadline` (a `time.monotonic()` timestamp) to hard-stop early and
return the estimate so far.

> ⚠️ `mc_equity_vs_random` assumes **uniformly-random** opponents, which
> **overestimates** hero equity — real opponents fold trash, so a villain still
> in the pot holds a stronger-than-random hand. Use it as a building block /
> verification target; switch to a weighted range once the opponent model exists.
