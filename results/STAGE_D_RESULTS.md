# Stage D — cEV short-stack push/fold chart (ATTEMPTED, GATED, REVERTED)

> Leak **L5** from `results/STAGE_A_LEAKS.md` — ranked *lowest* value (deep
> 400-hand matches rarely reach ≤12bb; HU already at the extraction ceiling).
> Implemented behind `USE_STAGE_D`, gated, and **reverted** (flag left `False`)
> because it did not beat the simpler legacy heuristic. Metric: avg Δ/match.

## What was tried
A static, position/stack-keyed chip-EV (not ICM) push/fold chart (`_PF_SHOVE`,
`_pf_shove_th`) replacing the legacy `shove_th = 6.5 + 1.5·(n_opp−1) − 0.4·…`
heuristic at ≤12bb, with a model adjustment (`_shove_adjust`: wider vs a folding
field, tighter vs light callers) and a separate, raiser-range-aware re-shove
threshold facing a raise.

## Gate D — paired `compare` vs Stage-C, 240 fresh seeds (base 3000), workers=14
| version | Stage-D | Stage-C | paired ΔΔ | 95% CI | A-better | verdict |
|---------|---------|---------|-----------|--------|----------|---------|
| first cut (`stageD_gate.log`) | +19,826 | +21,564 | **−1,738** | [−3,998, +522] | 37% | leans worse |
| after reshove fix (`stageD_gate_v2.log`) | +22,146 | +22,725 | **−579** | [−2,819, +1,661] | 44% | wash, leans worse |

Diagnosis of the first cut: the legacy heuristic re-shoved *wide* facing a raise,
which is correct vs the maniac aggressor's ~random raising range (+cEV); the chart
re-shoved only premium and folded those profitable spots. Widening the reshove vs
maniac/unknown raisers (and removing a short-stack SB-limp) recovered most of it
(−1,738 → −579), but the chart still **never beat** the legacy rule.

(Other Stage-D checks, first cut: vs Tier-1 +10,023 [+7861,+12185] — carried by
Stages B/C; vs balanced-TAG +197 [−542,+936] tied.)

## Decision
**Reverted: `USE_STAGE_D = False`.** With the flag off the bot is behaviorally
identical to Stage-C (the proven best). The chart code is kept dormant behind the
flag for the record / future refinement (e.g. a richer chart might help vs an
unknown qualifier field that reaches short stacks more often — but we have no
evidence for that, and on our only measurable proxy it leans negative). A green bot
in hand beats an unproven change (plan §4 guardrail). Shipping state remains
Stage-C (≈ +22k avg Δ on the ref table).

## Reproduce
```bash
python -m harness.sim compare --layout table --hero src/mybot/bot.py \
    --hero-b bots_local/stageC/bot.py --matches 240 --base-seed 3000 --workers 14
```
