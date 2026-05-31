---
name: equity-overestimate-random
description: mc_equity_vs_random overestimates hero equity; use weighted ranges for real decisions
metadata:
  type: project
---

`mc_equity_vs_random` assumes uniformly-random opponent hole cards, which **overestimates**
hero equity — real opponents fold trash, so a villain still in the pot holds a
stronger-than-random hand.

**Why:** It's a building block + verification target, not a number strategy should trust raw.

**How to apply:** For actual EV/pot-odds decisions, weight by a range from the opponent model
(e.g. average `mc_equity_vs_hand` over the range) once that exists. See [[equity-engine-api]].
