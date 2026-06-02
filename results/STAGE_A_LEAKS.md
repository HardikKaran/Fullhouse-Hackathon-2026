# Stage A — Measurement & Leak Diagnosis (Gate A artifact)

> Per `PLAN_maximize_chip_delta.md` §A. The metric is **average chip delta per
> match** = `mean(final_stack − 10,000)` — a chip-EV (cEV) environment, no ICM,
> no survival value. This file is the ranked list of measured leaks with the
> planned fix for each. Diagnostic tool: `harness/diagnose.py` (in-process,
> faithful to `sandbox/match.py`'s loop; instruments every hero decision).
> Date: 2026-06-02.

---

## TODO-0 / A.1 — Baseline reconciliation

**The plan's "+$1,497 avg Δ" is not reproducible and appears to be a transcription
error.** Reproduced figures (current shipped Tier-2 `bot.py`, `USE_RANGE_MODEL=True`):

- 6-max table vs the 5 reference bots, **30 matches, seed 9000+**: **+13,266 avg Δ**
  (consistent with the recorded Tier-1 baseline +13,460 and Tier-2 fresh-seed +14,415
  in `results/TIER2_RESULTS.md`).
- Paired Tier-2 − Tier-1, **200 fresh seeds (base 2000, workers 14)**
  (`results/stageA_baseline_paired_200.log`):
  - current **Tier-2 = +17,196** avg Δ (95% CI [+15,172, +19,219], 84% win)
  - **Tier-1 = +14,491** avg Δ (95% CI [+12,663, +16,320], 84% win)
  - **paired ΔΔ = +2,704** (95% CI [+775, +4,633], A-better 64%) → **CI excludes 0,
    Tier-2 is significantly ahead** on this seed set (stronger than the doc's prior
    +994 ns on seeds 500–739 — the edge is seed-set sensitive on this heavy-tailed
    metric, but positive everywhere measured).

Conclusion: the real, reproducible baseline is **≈ +14–17k avg Δ on the 6-max ref
table**. "+$1,497" matches none of our runs (not the +14,491 Tier-1 floor, not the
+2,704 paired ΔΔ, not the +3,783 balanced-TAG duel) — treat it as noise.
**Stage-B target: beat the current Tier-2 (+17,196 on base-seed 2000), never drop
below the Tier-1 floor (+14,491).** Gate every change against BOTH
`bots_local/tier1_baseline` and a frozen copy of the current Tier-2.

---

## The field (verified by reading all 5 reference bots)

**Four of the five reference bots fold to a correctly-sized bet.** This is the
single most important fact for cEV here:

| bot | behaviour | exploit |
|-----|-----------|---------|
| **aggressor** | raises 70% to 2–4× min, **never folds**, calls everything | zero fold-equity → **trap / value-stack, never bluff** |
| **mathematician** | folds to bets > ~½ pot, calls ≤ ½ pot, never raises; folds preflop to opens | bet ≤½ pot for value (it calls); bet >½ pot to fold it out; **steal preflop** |
| **ref_bot_2** | identical pot-odds caller to mathematician | same |
| **shark** | tight preflop value-raiser; folds postflop to bets > 15–25% pot | **steal / c-bet** with modest sizing; fold to its rare bets |
| **template** | folds to bets > 25% pot, calls small, raises only AA/KK | **steal / c-bet**; fold to its rare raises |

→ The dominant chip lever vs this field is **directed aggression**: steal the
folders preflop, c-bet/barrel them off pots, and value-stack the maniac. The bot
is **too passive** to collect this.

---

## Measured leaks, ranked by estimated chip impact

Evidence is from `harness/diagnose.py` over 30 6-max table matches (seed 9000+)
and 40 HU matches vs the aggressor (seed 9100+), unless noted.

### L1 — Postflop passivity in MULTIWAY: the bot only bets made hands; it never stabs a folding field. **(highest EV — Stage B/C)**
- **6,513 postflop check-backs** over 30 table matches (mean raw eq 0.31). The
  semi-bluff / stab paths are **heads-up only** (`n_opp == 1` gate in `_postflop`),
  so in every multiway pot the bot **never bluffs or semi-bluffs** — it checks and
  gives up against 4/5 opponents that fold to a bet.
- Only **33 flop c-bet spots in 30 matches** (hero rarely even reaches the flop as
  the preflop aggressor — a knock-on of L2).
- **Fix:** allow fold-equity-gated stabs / c-bets in multiway (not just HU) when the
  live field is classified as folders; raise c-bet & barrel frequency vs folders.
  The `_bluff_ok` fold-equity gate already prevents firing into stations/maniacs, so
  this is safe to widen. This is the largest pool of unclaimed fold-equity chips.

### L2 — Preflop opens too tight; steal-widening magnitude far too small. **(large, low-variance — Stage C)**
- Hero open-raises only **15%** of first-in (unopened-pot) spots in the table; folds
  49%, limp/checks 35%.
- `_steal_loosen` **does fire 55% of the time** it's evaluated (the maniac often
  busts mid-match, leaving an all-folder field) — but the average widen is only
  **0.47 Chen points** against a hard cap of 1.0. Even on the button vs all-folders
  the open threshold only drops from ~5.5 to ~5.0 (≈ top 40%). Against a field that
  folds ~80% preflop the late-position open range should be far wider.
- **Fix:** raise the steal magnitude (lift the cap, scale harder by `fold_freq` and
  position); gate on **yet-to-act** opponents rather than all live opponents (a
  maniac already in/behind shouldn't necessarily kill a steal of the nits); convert
  marginal SB limps into raises vs a folding field.

### L3 — Classifier is blind to the dominant field type (pot-odds folders read as "tag"). **(Stage B)**
- mathematician → classified **`tag` 19/30** matches (nit only 11/30); ref_bot_2 →
  **`tag` 27/30**. These are the *most exploitable* bots (fold to >½-pot, call
  ≤½-pot, never raise) yet they receive **neutral Tier-1 treatment**. Their postflop
  calls dilute `fold_freq` below the 0.55 nit gate, and the coarse
  station/maniac/nit/tag scheme has no bucket for "polarised: bet big to fold them,
  bet small for value."
- (shark → nit 28/30 ✓, template → nit 21/30 ✓, aggressor → maniac 25/30 + unknown
  warm-up ✓ — the rest classify correctly.)
- **Fix:** add a "folder" signal that survives postflop calls (e.g. preflop-fold% or
  low-AF + meaningful fold%) so the L1 fold-equity c-bet logic engages vs these bots;
  size value bets just under their calling cap.

### L4 — Facing-bet haircut folds +cEV spots. **(Stage B, smaller volume)**
- **34% of table folds (80/238)** had raw vs-random eq > pot odds; the
  (raw_eq − pot_odds) histogram shows **25 folds at +0.15…+0.30** and 32 at
  +0.05…+0.15 surplus. Raw eq is optimistic, so a haircut is justified — but a chunk
  of the +0.15…+0.30 bucket are likely +cEV calls after only a *bias* correction.
- Volume is modest (~460 facing-bet decisions / 30 matches — the field rarely bets),
  so this is below L1/L2 in impact.
- **Fix:** re-derive the haircut as the *minimum* vs-random bias correction (from the
  equity engine, not by feel) so it stops doubling as a caution knob; keep the
  archetype-scaled `_facing_hc_mult` (maniac 0.15 / nit 1.40) which is correct.

### L5 — Short-stack play is a hand-rolled Chen threshold, not a cEV push/fold chart. **(Stage D, lowest priority)**
- `_preflop` collapses to a single `shove_th = 6.5 + 1.5·(n_opp−1) − 0.4·max(0,10−eff_bb)`
  Chen heuristic at ≤12bb. Deep 400-hand matches reach ≤12bb spots relatively rarely
  and HU is already at the extraction ceiling, so this is the smallest leak.
- **Fix:** bake a static **cEV** (not ICM — cEV ranges are wider) push/fold table
  keyed on effective bb and position.

---

## What is NOT a leak (confirmed — do not "fix")
- **HU vs the maniac is well-tuned.** Vs the aggressor the bot folds only 21% facing
  bets, calls 65% (calling its air down), value-raises 14%; `pf-raise` hands average
  **+848**. The trap logic works — leave it.
- **No survival / lead-protection logic exists** to remove (plan §B.1 confirmed): the
  bot never folds +cEV to "bank" a lead. Good.
- **Low-equity multiway check-backs of trash** (the bulk of the 6,513) are correct;
  L1 targets only the *folding-field* subset where a stab has fold equity.

---

## Ranked fix order (matches plan §5)
1. **L1 + L3** (Stage B): multiway fold-equity stabs + see the pot-odds folders.
2. **L2** (Stage C): widen late-position steals vs classified folders.
3. **L4** (Stage B): minimal-bias haircut.
4. **L5** (Stage D): cEV push/fold table.
5. Validate everything vs a **diverse villain pool + balanced TAG** (Stage E) — the
   honest generalisation check, since the ref field is saturated.

Every change is one-flag reversible (`USE_RANGE_MODEL` + a per-stage flag) and gated
on a paired `compare` vs `bots_local/tier1_baseline` on fresh seeds, workers=14.

## Reproduce
```bash
python -m harness.diagnose --layout table --matches 30 --base-seed 9000
python -m harness.diagnose --layout duel --villain aggressor --matches 40 --base-seed 9100
python -m harness.sim compare --layout table --hero src/mybot/bot.py \
    --hero-b bots_local/tier1_baseline/bot.py --matches 200 --base-seed 2000 --workers 14
```
