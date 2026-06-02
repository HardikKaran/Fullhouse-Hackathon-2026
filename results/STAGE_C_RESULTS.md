# Stage C — wider late-position steals vs classified folders (results)

> Implements leak **L2** from `results/STAGE_A_LEAKS.md` behind `USE_STAGE_C`
> (one-flag revert). Leak L1's fold-equity c-bets (plan §C.2) were already shipped
> in Stage B (multiway stab). Metric: avg Δ/match.

## What changed in `src/mybot/bot.py`
- **Clean preflop-fold signal.** `_build_model` now tracks `pf_fold` (hands whose
  first logged action is a fold) → `pf_fold_freq`. The overall `fold_freq` is
  diluted by postflop calls and under-reads the folders; `pf_fold_freq` is the true
  "folds to a steal" rate.
- **Harder, position-scaled steal.** `_steal_loosen` (still gated on EVERY live
  opponent being a classified folder — no station/maniac/unknown) widens the open
  threshold by `(pf_fold − 0.45)·6 · (0.4 + 0.6·pos)`, capped at 2.5 Chen pts
  (was capped at 1.0 with a ·3 slope on the diluted fold_freq). A field folding
  ~80% preflop ⇒ ~2 pt widen on the button, tapering to little from early position.

## Behaviour shift (in-process diagnostic, 30 6-max table matches, seed 9000+)
| metric | Tier-2 | Stage-B | Stage-C |
|--------|--------|---------|---------|
| first-in open-raise % | 15% | 15% | **27%** |
| first-in fold % | 49% | 50% | **40%** |

→ ~80% more opens, mostly converting folds (and some limps) into +cEV steals.

## Gate C — paired `compare`, 240 fresh seeds table / 200 duel (base 3000), workers=14
`results/stageC_gate.log`:

| comparison | Stage-C | baseline | paired ΔΔ | 95% CI | verdict |
|------------|---------|----------|-----------|--------|---------|
| **vs Stage-B** (`bots_local/stageB`) | +22,141 | +18,099 | **+4,042** | [+1,968, +6,116] | **A > B** ✅ |
| **vs Tier-1** (`bots_local/tier1_baseline`) | +21,672 | +11,841 | **+9,831** | [+7,447, +12,215] | **A > B** ✅ |
| **vs balanced-TAG** (HU duel) | +5,225 | +4,436 | +789 | [−290, +1,869] | tied/+, not exploitable ✅ |

0 hero errors. Win-rate rose 79%→84% (steals are low-variance). Gate C green.

## Cumulative progress (avg Δ/match, 6-max ref table, base-seed 3000)
- Tier-1 baseline: ~+11.8–13.3k
- shipped Tier-2:  ~+15.6k
- + Stage B:       ~+18.1k  (+2,146 paired vs Tier-2)
- + Stage C:       **~+22.1k**  (+4,042 paired vs Stage-B)
- vs Tier-1 floor: **+9,831 paired**

New baseline to beat = Stage-C (`bots_local/stageC/bot.py`).

## Reproduce
```bash
python -m harness.sim compare --layout table --hero src/mybot/bot.py \
    --hero-b bots_local/stageB/bot.py --matches 240 --base-seed 3000 --workers 14
python -m harness.sim compare --layout duel --villain bots_local/balanced_tag/bot.py \
    --hero src/mybot/bot.py --hero-b bots_local/stageB/bot.py --matches 200 --base-seed 3000 --workers 14
```
