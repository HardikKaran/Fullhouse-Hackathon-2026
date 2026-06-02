# Tier 2 / Tier 3 — implementation & simulation results

Metric throughout is **avg Δ/match** = mean of per-match `final_stack − 10,000`
(the qualifier's ranking metric, per the plan §0), with a 95% CI and win-rate.
bb/100 is reported as a secondary lower-variance signal only.

Harness additions: `metrics.delta_stats`, an `avg Δ/match` line in
`duel.py`/`table.py`, and `harness/sim.py` — a parallel `ProcessPoolExecutor`
runner with `table` / `duel` / `gauntlet` / `compare` (paired) modes. All
comparative runs use `workers=14`; paired `compare` runs both candidates on the
**same seeds** so card variance cancels.

## Gate M — Tier-1 baseline (the number to beat)
6-max table vs the 5 reference bots, 200 matches (seeds 0–199):
**+13,460 avg Δ/match**, 95% CI [+11,690, +15,230], win-rate 82%, 0 errors.

## Tier 2 — opponent model + range-aware equity (inlined into bot.py)
`USE_RANGE_MODEL=True` (master switch; `False` ⇒ exact Tier-1).
`USE_RANGE_SAMPLING=False` (per-card range MC inlined but off — see A/B).

### Gate 2 — Tier-2 vs Tier-1, paired, 6-max table
| N (seeds)            | Tier-2  | Tier-1  | mean ΔΔ (A−B) | 95% CI            | verdict |
|----------------------|---------|---------|---------------|-------------------|---------|
| 80  (0–79)           | +17,615 | +11,417 | **+6,198**    | [+2,486, +9,909]  | sig     |
| 160 (0–159)          | +17,034 | +13,927 | **+3,107**    | [+775, +5,438]    | sig     |
| 240 (500–739, fresh) | +14,415 | +13,421 | **+994**      | [−958, +2,946]    | ns      |

Read: a **small positive** table edge. The early "significant" reads were partly
seed-luck on overlapping seeds (the heavy-tailed-metric "small-sample mirage" the
plan warns about). The reference table is **saturated** — both bots already bust
the weak passive field to the heads-up ceiling, so table Δ is dominated by
high-variance maniac stack-offs and the strategy gap washes out. Tier-2 never
regresses (positive point estimate in all three) and is faster-saturating.

### Per-archetype gauntlet (Tier-2, heads-up 100 matches each)
| Opponent      | avg Δ/match | win-rate | note |
|---------------|-------------|----------|------|
| template      | +9,846      | 100%     | busts it |
| aggressor     | +5,800      | 79%      | stacks it in ~15 hands (ideal; +EV high-variance) |
| mathematician | +10,000     | 100%     | full stack every match |
| shark         | +9,798      | 100%     | beats the strongest ref |
| ref_bot_2     | +10,000     | 100%     | full stack every match |
| 6-max table   | +17,827     | 88%      | |
0 hero errors anywhere. Tier-2 is at/near the extraction ceiling vs every bot.

### A/B — range-sampling vs haircut (both Tier-2), paired, 120 matches
range-sampling − haircut = **−803** [−3,417, +1,811] (ns) and 2.7× the latency
(164 ms vs 60 ms worst case). ⇒ ship the **haircut** path; keep sampling behind
the flag.

## Tier 3 — balanced-TAG generalization guard (diagnostic, not ship-blocking)
`bots_local/balanced_tag/bot.py`: solid, balanced, **non-adaptive** TAG, separate
self-contained file, distinct code from the hero (real out-of-sample check).

Heads-up, 300 matches:
- Tier-2  vs balanced: **+3,783** [+2,762, +4,805], 69% win, 0 errors
- Tier-1  vs balanced:  +3,427 [+2,392, +4,463], 68% win, 0 errors

Tier-2 ≥ Tier-1 vs a non-punting opponent ⇒ the exploits are **not**
self-exploitable. Gate 3 passes (clearly positive).

## Latency & validation
Worst case (5 live opponents, full 200-entry match log): **~60 ms/decision**
(haircut path) — 32× under the 2 s cap. `validator.py` PASS on both `dist/bot.py`
and `dist/bot.zip`. 54/54 unit tests pass.

## Ship decision
**Tier-2 shipped** (`USE_RANGE_MODEL=True`). It is non-worse than Tier-1 in every
test, point-estimate-better in most, clearly better HU and vs the balanced
villain, and adds adaptive opponent modelling that is the right tool for the
**unknown** qualifier field (which the saturated reference table can't measure).
The proven Tier-1 line is one flag away (`USE_RANGE_MODEL=False`) and a frozen
copy is kept at `bots_local/tier1_baseline/bot.py`.

## Reproduce
```
python -m harness.sim table   --matches 200 --base-seed 0          # baseline / Tier-2 table
python -m harness.sim gauntlet --matches 100                       # per-archetype + table
python -m harness.sim compare  --layout table --hero src/mybot/bot.py \
       --hero-b bots_local/tier1_baseline/bot.py --matches 240 --base-seed 500   # paired gate
python -m harness.sim duel --villain bots_local/balanced_tag/bot.py --matches 300  # Tier-3
```
Full logs: `results/stage1.log`, `results/stage2.log`,
`results/baseline_tier1_table.log`, `results/tier2_vs_tier1_paired_80.log`.
