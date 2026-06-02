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

**New baseline to beat = Stage-B (`bots_local/stageB/bot.py`).** L4 (haircut) was
deferred (smallest leak). Next per plan: Stage C (wider late-position steals vs
classified folders — leak L2), then D (cEV push/fold chart), then E (diverse villain
pool). Supersedes the [[tier1-baseline-metric]] number as the gate target. Not yet
git-committed.
