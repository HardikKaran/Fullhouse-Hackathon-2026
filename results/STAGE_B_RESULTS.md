# Stage B — cEV posture correction (results)

> Implements leaks **L1** (multiway fold-equity stabs) and **L3** (thin, payable
> value into a passive pot-odds-caller field) from `results/STAGE_A_LEAKS.md`,
> behind the `USE_STAGE_B` flag (one-flag revert to the prior Tier-2). L4 (haircut)
> deferred — smallest leak, "tuning by feel" risks spew. Metric: avg Δ/match.

## What changed in `src/mybot/bot.py`
- **L1 — multiway stab.** The heads-up-only semi-bluff is generalised to a stab that
  also fires multiway, gated by a multiway-aware fold equity `fe` = **product** of
  per-opponent fold probabilities (`_pfold`). Any station / maniac / unknown still
  in the pot drives `fe → 0`, so `_bluff_ok(fe, …)` fails and the stab never fires —
  self-protecting, not over-fit. Stab off (`stab_freq=0`) whenever a loose caller is
  in the pot.
- **L3 — passive-field value sizing.** When every *classified* in-pot opponent is
  low-aggression (`af ≤ 0.6`, `allin_freq < 0.08`), value-bet thinner
  (`value_th ≤ 0.52`) and sized to be called (`value_size ≤ 0.5`, `overbet ≤ 0.6`),
  overriding the too-tight 0.58 nit/tag threshold — these bots call ≤½ pot postflop
  even when they fold preflop, so thin payable value out-earns tightening up.

## Behaviour shift (in-process diagnostic, 30 6-max table matches, seed 9000+)
| metric | before (Tier-2) | after (Stage-B) |
|--------|-----------------|-----------------|
| postflop check-backs | 6,513 | **4,901** (−1,612 give-ups) |
| postflop bets/raises | 2,132 | **3,213** (+1,081) |
| mean eq of bets | 0.72 | 0.67 (betting thinner / stabbing) |
| made hands (eq≥0.55) checked back | 382 | **110** (more value-bet) |

→ The bot now collects multiway fold equity it previously left on the table, and
value-bets the pot-odds callers at a size they pay.

## Gate B — paired `compare`, 6-max table, 240 fresh seeds (base 3000), workers=14
`results/stageB_gate.log`:

| comparison | Stage-B avg Δ | baseline avg Δ | paired ΔΔ (A−B) | 95% CI | verdict |
|------------|---------------|----------------|-----------------|--------|---------|
| **vs frozen Tier-2** (`tier2_current`) | +17,769 | +15,622 | **+2,146** | [+186, +4,106] | **A > B** ✅ |
| **vs Tier-1 floor** (`tier1_baseline`) | +18,412 | +13,277 | **+5,135** | [+3,093, +7,178] | **A > B** ✅ |

0 hero errors in all runs. Both CIs **exclude 0** — Stage B is a statistically
significant gain over both the shipped Tier-2 and the Tier-1 floor (exceeds the
plan's Gate-B bar of "point-estimate positive and not worse").

(The frozen Tier-2 reads +15,622 here vs +17,196 on base-seed 2000 — seed-set
variance on a heavy-tailed metric; the **paired** ΔΔ is the variance-cancelling
signal, not the absolute per-run numbers.)

## Generalization guard — vs balanced-TAG (not self-exploitable) ✅
Paired HU duel, Stage-B (A) vs frozen Tier-2 (B) vs `bots_local/balanced_tag`, 200
matches (base 3000), `results/stageB_balanced_tag.log`:

| | avg Δ/match | 95% CI |
|--|-------------|--------|
| Stage-B | +4,147 | [+2,914, +5,381] |
| frozen Tier-2 | +4,109 | [+2,863, +5,355] |
| **paired ΔΔ (A−B)** | **+38** | **[−417, +493]** — tied (CI spans 0) |

**Non-worse vs a competent opponent** → the added multiway/HU aggression is not
self-exploitable. (The +5,135 ref-table gain vs Tier-1 comes purely from punishing
the *folding* field, not from a line a balanced opponent can punish.) Gate B is
fully green: significantly better vs the ref field, tied vs balanced TAG, 0 errors.

## Reproduce
```bash
python -m harness.sim compare --layout table \
    --hero src/mybot/bot.py --hero-b bots_local/tier2_current/bot.py \
    --matches 240 --base-seed 3000 --workers 14
python -m harness.sim compare --layout table \
    --hero src/mybot/bot.py --hero-b bots_local/tier1_baseline/bot.py \
    --matches 240 --base-seed 3000 --workers 14
python -m harness.sim compare --layout duel --villain bots_local/balanced_tag/bot.py \
    --hero src/mybot/bot.py --hero-b bots_local/tier2_current/bot.py \
    --matches 200 --base-seed 3000 --workers 14
```
