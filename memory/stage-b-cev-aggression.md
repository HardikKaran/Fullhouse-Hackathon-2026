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

**Current best / gate target = Stage-C (`bots_local/stageC/bot.py`), ~+22.1k avg Δ
on the ref table (base 3000), +9,831 paired vs Tier-1.** Flags USE_STAGE_B and
USE_STAGE_C each revert independently. L4 (haircut) deferred (smallest leak).
Remaining per plan: D (cEV push/fold chart — lowest value), E (diverse villain pool
— generalization), F (package+validate dist/bot.zip). Supersedes
[[tier1-baseline-metric]] as the gate target.
