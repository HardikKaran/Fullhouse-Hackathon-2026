---
name: stage-b-cev-aggression
description: Stage-B (USE_STAGE_B) added multiway fold-equity stabs + thin value vs passive callers; beats prior Tier-2 by +2,146 paired
metadata:
  type: project
---

The qualifier scores on **avg chip delta per match** (cEV, no ICM/survival) — see
`PLAN_maximize_chip_delta.md`. Stage A (`results/STAGE_A_LEAKS.md`) found the field
is 4/5 fold-to-a-bet bots and the leaks were: bot too passive multiway (only bet
made hands; semi-bluff was HU-only), opens too tight, and the pot-odds callers
(mathematician/ref_bot_2) misread as "tag".

**Stage B** (`src/mybot/bot.py`, flag `USE_STAGE_B`, frozen at
`bots_local/stageB/bot.py`) fixed L1+L3:
- multiway fold-equity **stab** gated by `fe` = PRODUCT of per-opponent fold probs
  (`_pfold`) — fires only when the whole live field folds; a station/maniac/unknown
  in the pot drives fe→0 so `_bluff_ok` kills it (self-protecting, not over-fit).
- **passive-field** thin value: when all classified opponents are low-AF, value
  thinner (`value_th≤0.52`) and sized to be called (`value_size≤0.5`).

Paired gates (6-max table, 240 fresh seeds, base 3000, workers 14;
`results/stageB_gate.log`): vs frozen Tier-2 **+2,146** [+186,+4106]; vs Tier-1
**+5,135** [+3093,+7178] — both CIs exclude 0. vs balanced-TAG (HU 200): **+38**
[−417,+493], tied → not self-exploitable. 0 hero errors.

**Stage C** (flag `USE_STAGE_C`, frozen `bots_local/stageC/bot.py`) then fixed L2:
added `pf_fold_freq` (clean preflop-fold signal) and a position-scaled, larger
steal widen (cap 2.5 Chen pts vs 1.0), gated on every live opp being a classified
folder. Gate (base 3000): vs Stage-B **+4,042** [+1968,+6116]; vs Tier-1 **+9,831**
[+7447,+12215]; vs balanced-TAG **+789** [−290,+1869] tied. Open rate 15%→27%,
win-rate 79%→84%, 0 errors. Committed on main.

**Stage D** (cEV push/fold chart, flag `USE_STAGE_D`): attempted, gated, **REVERTED**
(flag left False) — the chart never beat the simpler legacy short-stack heuristic
(ΔΔ −579 vs Stage-C). Lowest-value leak L5. Code kept dormant.

**Stage E** (diverse villain pool: true_lag / calling_station / tight_nit in
`bots_local/`): generalization check. Exploits pay vs a real over-folder (tight_nit
**+3,571** vs Tier-1), non-worse vs LAG/balanced-TAG. **Caught an over-fit**: the
`station_field` logic was tuned for the reference *folders* (which fold to big bets)
and under-extracted vs a *true* never-fold station (−900 vs Tier-1). Fix `USE_STAGE_E`:
a sticky station (fold_freq<0.35) keeps NEUTRAL sizing (not shrunk, not overbet) →
tied (−167) vs Tier-1, ref table unchanged.

**Current best = Stage-E (`bots_local/stageE/bot.py`).** Flags: B=True, C=True,
D=False, E=True (each reverts independently). Ref table ~+20k avg Δ (base 3000),
~+9–10k paired vs Tier-1; non-worse across the diverse pool; 0 hero errors. Stages
A–E committed on main. Remaining: F (package+validate dist/bot.zip + latency).
Supersedes [[tier1-baseline-metric]] as the gate target.
