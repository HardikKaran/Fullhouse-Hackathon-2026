# Claude Code Implementation Plan — Tier 2 & Tier 3 (Opponent Model + Robustness)

> **Read this whole file before writing any code.** Tier 1 is shipped, validated,
> and winning (see §1). This file is the scope for the two optional stretch tiers.
> The golden rule from the Tier-1 plan still holds: **a green tier in hand beats an
> unfinished one. Commit after every green gate; if a tier regresses on the metric,
> revert to the last green commit and ship that.**

---

## 0. The metric that shapes everything: **average chip delta per match**

The qualifier ranks on **mean chip delta per match**, *not* win rate. This is the
single most important design constraint and it changes the objective function:

- **Maximise `E[final_stack − 10_000]` per match.** Win rate is a side effect, not
  a target. Our current Tier-1 numbers — **+$8,406 average delta** at a **40% win
  rate over 15 matches** — are the *correct shape*: win big, lose small. A line
  that trades a higher win rate for a lower average delta is a **downgrade**.
- **Variance is not the enemy.** Do **not** add "lock up the win" / survival logic.
  A +EV high-variance line (stack-off with the best of it, thin value that
  occasionally gets raised) is *correct* because expectation is measured in chips,
  not in match wins. Only avoid variance that is **−EV** (spew).
- **Busting opponents is worth the most.** The biggest deltas come from winning
  whole stacks. In the gauntlet the aggressor match ended after ~19 hands because we
  stacked it — that is the ideal outcome. Tier 2's exploits should be oriented to
  **extracting the maximum chips from each opponent type**, especially via thin
  value and correctly-sized value bets, not to folding more or bluffing for its own
  sake.
- **Implication for Tier 2:** the opponent model exists to **size and select value
  bets** (and to know when a bluff actually folds out chips), i.e. to grow `E[delta]`.

### 0.1 First task: measure the real objective (≤20 min, do before Tier 2)

The harness currently reports **bb/100** (`harness/metrics.py`, `duel.py`,
`table.py`). bb/100 is monotonic with avg-delta-per-100-hands but is **not** the
ranking metric, and matches that end early on a bust distort it. Add a direct
readout so we optimise the right number.

- [ ] **M.1** In `harness/metrics.py` add `delta_stats(deltas)` → `{mean, ci95_low,
      ci95_high, win_rate}` over the **raw per-match `chip_delta["hero"]`** values
      (not bb/100). `win_rate = mean(1 for d in deltas if d > 0)`.
- [ ] **M.2** Have `duel.py` / `table.py` collect the raw deltas (they already read
      `result["chip_delta"]["hero"]`) and print an **`avg Δ/match`** line + 95% CI +
      win-rate alongside the existing bb/100 line. Keep bb/100 — it's still a useful
      lower-variance signal — but **rank on `avg Δ/match`.**
- [ ] **Gate M:** re-run the Tier-1 bot to record its baseline `avg Δ/match` with a
      tight CI (use **≥80 matches**; 15 is too few — the metric is dominated by rare
      huge pots, so its CI is wide). This baseline is what Tier 2 must beat.

---

## 1. Where Tier 1 left us (the baseline to beat)

- Self-contained `src/mybot/bot.py`, committed `3d172f2` (`tier1-equity-bot`).
  **Reminder:** the bot **inlines its own** equity + hand-eval — editing
  `src/mybot/equity.py` / `hand_eval.py` does **not** change it. Tier-2 code must be
  **inlined into `bot.py`** the same way (the sandbox loads one file, no `mybot`
  package). See `memory/bot-is-self-contained.md`.
- Verified vs the frozen reference bots: 6-max table **+53.5 bb/100**
  (95% CI [+44.4, +62.6], 0 hero errors / 20k hands); positive vs every archetype.
- Postflop already uses vs-random equity **minus a haircut** that scales with street
  and bet size when facing aggression. **Tier 2 replaces that haircut with a
  data-driven, range-weighted equity** (§3.2).

---

## 2. CRITICAL data note — what `match_action_log` actually contains

The Tier-1 plan over-promised here; verify against the engine before coding.
`match_action_log` is injected by `sandbox/match.py::_inject_match_log` and each
entry is **only**:

```python
{"hand_num": int, "seat": int, "bot_id": str, "action": str, "amount": int|None}
```

Consequences you must design around:

- **No `street`, no `board`, no `pot`** in the entries. You cannot directly read
  "did they fold to a c-bet on the flop." Postflop-specific stats must be
  *reconstructed* and will be approximate.
- **Blinds are NOT in it.** Only *voluntary* bot decisions (fold/check/call/
  raise/all_in) are appended (blinds are auto-posted, never go through `act()`).
- **It is per-match and rolling (last 200 actions).** It **resets every match**, so
  the model **warms up from a neutral prior each match** and is only rich by
  mid-match. With ~400 hands/match there is plenty of data by then; the first ~20
  hands per opponent should fall back to the Tier-1 (range-by-action) defaults.
- **Segment by `hand_num`.** Within one `hand_num`, a given `bot_id`'s **first**
  logged action is its **preflop** decision (preflop is the first street). That single
  fact is what makes VPIP/PFR computable; everything postflop is fuzzier.

### 2.1 Stats that are robustly computable (lead with these)

Per `bot_id`, over the rolling log:

- **VPIP** ≈ fraction of `hand_num`s where the bot's **first** action ∈
  {call, raise, all_in}. (A BB check is *not* VPIP.)
- **PFR** ≈ fraction of `hand_num`s where the bot's **first** action ∈
  {raise, all_in}.
- **Aggression Factor (AF)** = `(#raise + #all_in) / max(#call, 1)` over all actions.
- **Fold frequency** = `#fold / #decisions`, and **all-in frequency** = `#all_in /
  #decisions` (flags maniacs / shove-bots).
- **Bet-size tells** = distribution of `amount` on raises (some bots have a constant
  size; the aggressor's `min_r * randint(2,4)` is detectable).

### 2.2 Stats that need reconstruction (optional, lower priority)

Fold-to-c-bet, WTSD, etc. require inferring street boundaries from the action
sequence (e.g. a street ends when all live players have matched the bet). This is
brittle without board/pot. **Skip for the first Tier-2 pass.** The §2.1 stats are
enough to classify opponents into the buckets that drive value sizing.

---

## 3. Tier 2 — opponent model + range-weighted equity (inlined into `bot.py`)

> Gate every change on **`avg Δ/match`** (§0.1), not bb/100 or win rate.

### 3.1 `OppStats` accumulator (T2.1)
- [ ] Inline a tiny class/dict builder that scans `state["match_action_log"]` each
      decision and produces per-`bot_id` counts → the §2.1 stats. Keep it O(log size)
      (≤200 entries) — recomputing each decision is cheap; no need to persist state
      across calls (and we **can't** rely on module globals surviving, so recompute).
- [ ] **Small-sample priors:** below ~15–20 decisions for an opponent, return a
      neutral profile so we play the Tier-1 baseline. Never swing hard off 3 hands.
- [ ] Classify each live opponent into a coarse **archetype** used downstream:
      `station` (low fold%, low AF, high VPIP), `maniac` (high AF / all-in freq),
      `nit` (low VPIP, high fold%), `tag`/unknown (default). These four buckets are
      what the sizing/bluffing logic switches on.

### 3.2 Range-weighted equity — replace the haircut (T2.2)
The Tier-1 haircut is a static proxy for "opponents in the pot beat random." Replace
it with a **villain range derived from the model**, and prefer the cheaper of two
implementations:

- **Preferred — range-restricted sampling (one MC loop, ~same cost as vs-random):**
  modify the inlined equity loop so each opponent's hole cards are drawn from a
  **truncated range** instead of uniformly. Build the range once per decision as the
  **top-`X%` of starting hands by Chen score**, where `X` comes from that opponent's
  **VPIP** (station ⇒ wide `X`, nit ⇒ narrow `X`; widen for in-position/aggressor
  archetypes who are betting). Implement by precomputing the list of in-range
  2-card combos consistent with the dead cards, then sampling opponents' hands from
  it each iteration (rejection-sample against already-drawn cards). This is **lower
  variance and faster** than enumerate-and-average and keeps us inside the deadline.
- **Fallback — enumerate-and-average:** inline `mc_equity_vs_hand`, sample K hands
  from each opponent's range, average equity over them. Simpler but K× the cost —
  watch `BUDGET_S`; lower `POSTFLOP_ITERS` to compensate.
- [ ] Keep the **Tier-1 haircut path behind a flag** (`USE_RANGE_MODEL = True`) so a
      one-line revert restores the shipped behaviour if Tier 2 regresses.
- [ ] Multiway: sample **each** opponent from **their own** range. With many live
      opponents, time-budget by lowering iters (the deadline already hard-caps it).

### 3.3 Exploit adjustments — all oriented at **max Δ** (T2.3)
Use the archetype + range to grow expected chips, not to play scared:

- **vs `station`:** **value-bet thinner and bigger** (they call too wide — this is
  the single biggest Δ lever vs the loose reference field). **Bluff ~never.** Lower
  the value threshold and raise the value bet size; consider an overbet on the river
  with strong made hands because they pay it off.
- **vs `nit`:** **bluff/steal more** (high fold equity), **fold to their aggression**
  (their bets are real — pay them off less). Steal blinds wider in position.
- **vs `maniac`:** **trap** — call down lighter and let them barrel into our strong
  hands; **don't bluff-raise** (no fold equity). Widen our calling/stack-off range
  because their range is junk-heavy.
- **vs `tag`/unknown:** Tier-1 behaviour (balanced, equity-driven).
- **Fold equity for bluff/semi-bluff EV:** estimate `fe` from the opponent's fold%
  (or 1−VPIP as a prior) and only fire bluffs where `fe × pot > (1−fe) × cost`. This
  finally makes `ev_raise` data-driven (the Tier-1 plan's §4.5 formula) instead of a
  constant.

### Gate 2 (the real gate)
- [ ] `validator.py` PASS on the inlined Tier-2 `bot.py` (still one file, eval7+stdlib,
      under 2 s/decision — re-check latency with the extra range work).
- [ ] **`avg Δ/match` ≥ Tier-1 baseline** with a non-overlapping or clearly-better CI,
      over **≥80 matches** at the 6-max table (the qualifier format). bb/100 and win
      rate are secondary; **Δ is the ranking metric.**
- [ ] Zero hero errors. **If Δ/match regresses, set `USE_RANGE_MODEL=False` (or
      `git revert` to `3d172f2`) and ship Tier 1.** Do not gamble the submission.
- [ ] Commit as `tier2-opponent-model` only after the gate is green.

---

## 4. Tier 3 — robustness vs a strong, non-exploitative opponent

A diagnostic, **not** a ship-blocker: confirms we are not ourselves exploitable
(which would bleed Δ to a real-field opponent that doesn't punt like the refs do).

### 4.1 Build a balanced benchmark villain (T3.1)
- [ ] Add a new **separate** bot (its own file, like the reference bots), e.g.
      `bots/balanced_tag/bot.py` — **not** inside `src/mybot/bot.py`. It plays a
      solid, *balanced, non-adaptive* TAG strategy: equity-driven, position-aware,
      fixed sensible sizings, **no opponent modelling**. Seed its preflop ranges from
      standard Nash RFI / push-fold charts baked in as static tables. It can reuse the
      same inlined equity approach (copy the engine in — it's a test bot, not a
      submission). This stands in for the "online GTO non-exploitative bot" we can't
      reach over the network.
- [ ] Register it in `harness/paths.py` (or pass via `--villain`) so `duel` can use it.

### 4.2 Run the diagnostic (T3.2)
- [ ] `duel` our bot vs the balanced villain, **both seat orders, ≥300 matches**,
      reporting **`avg Δ/match`** (per §0.1).

### Gate 3 (diagnostic)
- [ ] vs the balanced villain we should be **roughly break-even or positive** on
      `avg Δ/match`. A large negative means our bot is exploitable — investigate
      (likely an over-aggressive Tier-2 exploit firing vs a non-folding balanced
      range). This **informs** Tier 2, it does not block the submission.

---

## 5. Risk register (metric-aware)

- **Optimising the wrong number** → we tune for win rate or bb/100 and lose Δ. Fix:
  do §0.1 first; gate everything on `avg Δ/match`.
- **Over-correcting toward low variance** → folding/checking to "bank a win" lowers
  Δ. Fix: only cut **−EV** variance; keep +EV stack-offs.
- **Over-fitting the reference bots** → great vs refs (esp. stations), bad vs the
  unknown field. Fix: bound the exploits, use the Tier-3 balanced villain as the
  generalisation check, keep priors neutral on small samples.
- **`match_action_log` misuse** → treating it as if it has street/board, or not
  resetting the warm-up each match. Fix: §2; lead with the robust §2.1 stats.
- **Latency blow-up from range work** → re-measure after §3.2; the deadline
  (`BUDGET_S`) already hard-caps MC, but range construction is extra per-decision
  cost — keep it O(deck).
- **Tier-2 regression** → revert to `tier2`-flag-off or `3d172f2` and ship. A green
  Tier-1 at the deadline beats an unfinished Tier-2.
- **Small-sample mirage** → 15 matches can't tell two strategies apart on a
  heavy-tailed metric. Compare on **≥80 matches** with CIs before believing a delta.

---

## 6. Definition of done (Tier 2 / Tier 3)

1. Harness reports **`avg Δ/match`** with a CI and win rate (§0.1), and a Tier-1
   baseline is recorded over ≥80 matches.
2. Tier-2 opponent model + range-weighted equity inlined into the single
   self-contained `bot.py`; `validator.py` PASS; under 2 s/decision.
3. **6-max `avg Δ/match` ≥ Tier-1 baseline** with a clearly-better/non-overlapping
   CI and zero hero errors — else reverted and Tier 1 shipped.
4. (Diagnostic) Tier-3 balanced villain built and the `duel` run understood; not
   ship-blocking.
5. The exact file re-validated and re-packaged (`dist/bot.py` + `dist/bot.zip`,
   `bot.py` at the zip root) before any re-upload.
