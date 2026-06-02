# Memory index

One line per memory file.
- [Equity engine API](equity-engine-api.md) — real names are `mc_equity_vs_*`/`equity_mc` in flat `equity.py`, not the plan's `equity/montecarlo.py`
- [Random overestimates equity](equity-overestimate-random.md) — `mc_equity_vs_random` is optimistic; use weighted ranges for real decisions
- [Bot is self-contained](bot-is-self-contained.md) — submitted bot.py inlines its own equity/hand-eval; editing equity.py/hand_eval.py won't change it
- [Tier-1 baseline metric](tier1-baseline-metric.md) — avg Δ/match=+13,460 over 200 6-max matches; harness/sim.py paired-compare for Tier-2 gating
- [Stage-B cEV aggression](stage-b-cev-aggression.md) — USE_STAGE_B multiway stabs + thin value beat prior Tier-2 by +2,146 paired; new baseline = bots_local/stageB/bot.py
