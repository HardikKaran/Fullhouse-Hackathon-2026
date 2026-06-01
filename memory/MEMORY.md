# Memory index

One line per memory file.
- [Equity engine API](equity-engine-api.md) — real names are `mc_equity_vs_*`/`equity_mc` in flat `equity.py`, not the plan's `equity/montecarlo.py`
- [Random overestimates equity](equity-overestimate-random.md) — `mc_equity_vs_random` is optimistic; use weighted ranges for real decisions
- [Bot is self-contained](bot-is-self-contained.md) — submitted bot.py inlines its own equity/hand-eval; editing equity.py/hand_eval.py won't change it
