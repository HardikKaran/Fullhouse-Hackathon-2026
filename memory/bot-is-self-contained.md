---
name: bot-is-self-contained
description: Submitted src/mybot/bot.py inlines its own equity/hand-eval copy; editing equity.py/hand_eval.py does NOT change the bot
metadata:
  type: project
---

`src/mybot/bot.py` (the tournament submission, commit `3d172f2` "tier1-equity-bot")
is **fully self-contained**: it has its OWN inlined copy of the Monte-Carlo equity
loop and eval7 card primitives and does **not** `import` from `mybot.equity` /
`mybot.hand_eval`. The sandbox loads one file by path with no `mybot` package, so
this is required. See [[equity-engine-api]].

**Consequence:** editing `src/mybot/equity.py` or `src/mybot/hand_eval.py` (which
still back the tests/`bench`) will NOT change the bot's behaviour — the logic must
be re-inlined into `bot.py` by hand. They can drift; keep that in mind.

**Design constants in `bot.py`:** `BUDGET_S=0.30`, `POSTFLOP_ITERS=8000`
(±~1.1%, well under the 2 s/decision cap). Preflop = static Bill Chen score
(`_chen`, no Monte Carlo); position derived from blind markers in `action_log`
(`_button_seat`), BB read from the `big_blind` action amount. Postflop = EV/pot-odds
on `_equity_vs_random` minus a haircut that grows with street + bet size **when
facing a bet** (fixes the [[equity-overestimate-random]] trap, e.g. folds bottom
pair to a pot-sized river bet). Bounded heads-up semi-bluffing only.

**Verified perf (vs frozen reference bots):** 6-max table **+53.5 bb/100**
(95% CI [+44.4, +62.6], 0 hero errors / 20k hands) vs the v0 heuristic's
**+12.7** (CI [-0.2, +25.7]); positive vs every archetype individually.

**Packaging:** validator accepts a plain `.py` OR a `.zip` with `bot.py` at the
archive root. Build via `dist/` (gitignored): `dist/bot.py` and `dist/bot.zip`;
validate with `python vendor/fullhouse-engine/sandbox/validator.py <path>`.
Tier 2 (opponent model) / Tier 3 (balanced-villain diagnostic) were left as the
optional next step — do not start without a green Tier-1 already shipped.
