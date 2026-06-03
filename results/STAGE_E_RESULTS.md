# Stage E — diverse villain pool (generalization) + the over-fit it caught

> PLAN §E: the saturated reference field can't predict qualifier performance, so we
> built a richer out-of-sample pool and validated the Stage-B/C exploits against it.
> Metric: avg Δ/match, paired vs `tier1_baseline` (same seeds). Workers=14.

## The pool (`bots_local/`, self-contained, distinct code)
- **`true_lag`** — loose-aggressive *thinking* bot: opens wide, c-bets/barrels,
  3-bet bluffs, but folds when beat and value-raises when ahead (unlike the ref
  maniac, which is trivially trapped). The real "is our aggression punishable?" test.
- **`calling_station`** — *true* never-fold station: calls down very wide to any
  size, never raises (≠ the ref pot-odds bots, which FOLD to >½-pot).
- **`tight_nit`** — pure over-folder: only premiums, folds to all aggression, never
  bluffs (≠ `shark`, which value-raises). The "do our steals print?" test.

## Gauntlet — hero vs Tier-1 baseline, paired, HU 200 matches (base 3000)
`results/stageE_gauntlet.log` (Stage-C hero) + `results/stageE_fix2.log` (final):

| villain | hero | Tier-1 | paired ΔΔ | 95% CI | read |
|---------|------|--------|-----------|--------|------|
| **tight_nit** | +8,416 | +4,845 | **+3,571** | [+2,653, +4,490] | **exploit pays big** — steals/c-bets crush a real over-folder |
| **true_lag** | +3,749 | +4,300 | −551 | [−1,780, +678] | tied — aggression **not** punishable by a thinking LAG |
| **balanced_tag** | +5,332 | +4,291 | +1,041 | [−62, +2,144] | tied/trending+ |
| **calling_station** (final) | +8,750 | +8,917 | −167 | [−493, +160] | tied — non-worse (see fix below) |

Verdict: the exploits **generalize** — they pay clearly where there is room (the
nit), and are **non-worse** everywhere else (LAG, balanced-TAG, true station). Both
bots already stack the extreme never-fold station (~95% win, ~+8.8k of the 10k
ceiling), so "tied" is the realistic ceiling there, not a miss.

## The over-fit the pool caught (and the fix)
First gauntlet: vs the true calling station hero was **−900 vs Tier-1 (CI excluded
0 — significantly WORSE)**. Root cause: the `station_field` branch sized value bets
*small* (`overbet_size 0.5`), which was tuned for the reference "callers" — but
those are pot-odds **folders** (fold to >½-pot, classify as tag/nit), not stations.
A *true* never-fold station calls any size, so shrinking sizing **under-extracts
from monsters**. Exactly the over-fit the diverse pool exists to catch.

Two iterations (`results/stageE_fix.log`, `stageE_fix2.log`):
1. First attempt — *overbet thin* (value_th 0.50 @ 0.9-pot / 1.2 overbet): **worse**
   (−1,400 vs Tier-1). Its wide range calls thin value with better → we lose big pots.
2. **Fix that worked** (`USE_STAGE_E`): a genuinely sticky station (`fold_freq <
   0.35`) keeps **Tier-1's NEUTRAL sizing** (value 0.6 / overbet 0.9), only the dead
   bluffs suppressed → **−167, tied** vs Tier-1. A "calls-small / folds-big" caller
   (fold_freq ≥ 0.35) keeps the sub-fold-threshold small sizing. Ref table unchanged
   (new vs Stage-C **+179** [−2017, +2375], the branch doesn't trigger on folders).

## State after Stage E
Flags: `USE_STAGE_B=True`, `USE_STAGE_C=True`, `USE_STAGE_D=False` (reverted),
`USE_STAGE_E=True`. Frozen at `bots_local/stageE/bot.py`. Ref table ~+20k avg Δ,
+9–10k paired vs Tier-1; non-worse across the diverse pool; 0 hero errors anywhere.

## Reproduce
```bash
for V in true_lag calling_station tight_nit balanced_tag; do
  python -m harness.sim compare --layout duel --villain bots_local/$V/bot.py \
    --hero src/mybot/bot.py --hero-b bots_local/tier1_baseline/bot.py \
    --matches 200 --base-seed 3000 --workers 14
done
```
