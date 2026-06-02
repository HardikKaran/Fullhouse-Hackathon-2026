---
name: bot-is-self-contained
description: Submitted src/mybot/bot.py inlines its own equity/hand-eval copy; editing equity.py/hand_eval.py does NOT change the bot
metadata:
  type: project
---

`src/mybot/bot.py` (the tournament submission) is **fully self-contained**: it has
its OWN inlined copy of the Monte-Carlo equity loop and eval7 card primitives and
does **not** `import` from `mybot.equity` / `mybot.hand_eval`. The sandbox loads
one file by path with no `mybot` package, so this is required. See
[[equity-engine-api]].

**Consequence:** editing `src/mybot/equity.py` or `src/mybot/hand_eval.py` (which
still back the tests/`bench`) will NOT change the bot's behaviour — the logic must
be re-inlined into `bot.py` by hand. They can drift; keep that in mind.

**Now Tier 2 (opponent model).** Tier-1 was commit `3d172f2`; a frozen copy lives
at `bots_local/tier1_baseline/bot.py` (the paired-compare baseline). The shipped
bot adds a self-contained per-match opponent model built from
`state["match_action_log"]` (`_build_model`/`_classify`: VPIP/PFR/AF/fold%/all-in%
→ archetype station/maniac/nit/tag, neutral until `MIN_SAMPLE=16` decisions), then
uses it to scale the equity haircut (`_base_hc_mult`, `_facing_hc_mult` — tiny vs a
maniac bettor = trap; large vs a nit) and to drive bounded exploits (`_exploits`:
thin value & sizing vs loose, fold-equity-gated bluffs `_bluff_ok`, wider steals
vs folders). **Master flag `USE_RANGE_MODEL=True`; set it `False` for an exact
Tier-1 revert.** `USE_RANGE_SAMPLING=False` (per-card range MC is inlined but
off — A/B showed it ≈/slightly-worse and 2.7× slower). Constants `BUDGET_S=0.30`,
`POSTFLOP_ITERS=8000`. Worst-case decision (5 opp, full log) ~60 ms.

**Verified perf (avg Δ/match — the qualifier ranking metric, NOT bb/100; see
[[tier1-baseline-metric]]):** vs the 5 reference bots, 6-max table Tier-2 ≈ Tier-1
(both ~+13–17k/match; paired edge +994 to +3,107 depending on seeds, NOT
statistically clean out-of-sample — the ref field is *saturated*, both bust it to
the HU ceiling: 100% win vs math/ref/shark, stacks the aggressor in ~15 hands).
HU gauntlet near-max everywhere, **0 hero errors**. Tier-3 diagnostic vs the
`bots_local/balanced_tag` villain: Tier-2 **+3,783**/match (300 HU) vs Tier-1's
+3,427 — positive, so the exploits are not self-exploitable. Shipped Tier-2 for
the adaptive upside vs the unknown qualifier field; it is non-worse than Tier-1
anywhere measured and one flag from reverting.

**Packaging:** validator accepts a plain `.py` OR a `.zip` with `bot.py` at the
archive root. Build via `dist/` (gitignored): `dist/bot.py` and `dist/bot.zip`;
validate with `python vendor/fullhouse-engine/sandbox/validator.py <path>`. Both
re-validated ✅ for the Tier-2 ship.
