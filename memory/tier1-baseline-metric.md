---
name: tier1-baseline-metric
description: Tier-1 bot.py baseline on the qualifier's real metric (avg chip delta/match) is +13,460 over 200 6-max matches
metadata:
  type: project
---

The qualifier ranks on **mean chip delta per match** (`final_stack − 10_000`),
NOT bb/100 — see `PLAN_tier2_tier3_next_steps.md` §0. Added `metrics.delta_stats`
and an `avg Δ/match` readout to `duel.py`/`table.py`; built `harness/sim.py`
(parallel `ProcessPoolExecutor` runner with `table`/`duel`/`gauntlet`/`compare`
modes) for the heavy ≥80-match gates.

**Recorded Tier-1 baseline** (frozen at [[bot-is-self-contained]], copied to
`bots_local/tier1_baseline/bot.py`), 6-max table vs the 5 reference bots, 200
matches (seeds 0-199), `workers=14`:

- **avg Δ/match = +13,460**  (95% CI [+11,690, +15,230])
- win-rate 82%, bb/100 +32.66, **0 hero errors**, ~77.9k hands.

This is the number Tier-2 must beat (clearly-better / non-overlapping CI). Use
`python -m harness.sim compare --layout table --hero <new> --hero-b
bots_local/tier1_baseline/bot.py --matches N` for a **paired** test (same seeds →
card variance cancels). Keep `--workers` identical across compared runs (CPU
contention changes the hero's wall-clock MC iteration count). bb/100 here (+32.7)
is lower than the memoryed +53.5 purely because of pool contention — relative
comparison is what matters, not the absolute.
