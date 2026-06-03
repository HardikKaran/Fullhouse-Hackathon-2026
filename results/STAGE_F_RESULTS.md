# Stage F — package & validate the submission

> PLAN §F. Produce the exact `dist/bot.zip` to upload and prove it passes the
> tournament validator and the latency budget. `dist/` is gitignored (build
> artifact) — rebuilt from `src/mybot/bot.py` (Stage-E, flags B/C/E=True, D=False).

## F.1 — Build + validator PASS
```
dist/bot.zip  ->  contains ONLY bot.py at root (41,369 bytes; limits: bot.py ≤5MB, pkg ≤250MB)
python vendor/fullhouse-engine/sandbox/validator.py dist/bot.zip
  ✅ PASSED — dist/bot.zip
   ✓ preflop_call_or_fold        {'action': 'raise', 'amount': 300}
   ✓ postflop_can_check          {'action': 'raise', 'amount': 150}
   ✓ river_facing_large_bet      {'action': 'fold'}
   ✓ short_stack_all_in_decision {'action': 'all_in'}
```
No forbidden imports/calls (bot uses only `random`, `time`, `eval7`); single file at
zip root; `decide()` present; returns valid dicts; no unhandled exceptions
(defensive try/except in `decide`).

## F.2 — Worst-case latency ≪ 2s
Measured on the heaviest path — **5 live opponents, full 200-entry match log**,
postflop (Monte-Carlo + full model build + all Stage-B/C/E branches active),
40 calls each:

| scenario (n_live=5) | max | p95 | mean |
|---------------------|-----|-----|------|
| flop facing bet  | 52.4 ms | 52.1 ms | 50.7 ms |
| turn facing bet  | 49.8 ms | 49.5 ms | 48.0 ms |
| river checked-to | 48.7 ms | 48.4 ms | 47.1 ms |
| preflop facing raise | 0.1 ms | 0.1 ms | 0.1 ms (no MC preflop) |

The postflop MC is bounded by the `BUDGET_S = 0.30s` **wall-clock** deadline (the
loop breaks at the deadline regardless of CPU speed), so even on the sandbox's
0.5-CPU cap the worst-case decision is bounded ≈ 0.30s + O(200) model overhead
≈ **~0.35s, ≫ 5× under the 2s cap.** A timeout would auto-fold (a cEV disaster), so
this margin matters; it is comfortably safe.

## Gate F — DONE
Validated `dist/bot.zip` rebuilt from the Stage-E bot, validator PASS, worst-case
latency ~50 ms (bounded ~0.35s at 0.5 CPU), 0 hero errors across every gate.
**Ready to upload.** Keep this zip until any future change re-validates — never
ship unvalidated.

## Reproduce
```bash
rm -rf dist/bot.py dist/bot.zip dist/__pycache__
cp src/mybot/bot.py dist/bot.py && ( cd dist && zip -q bot.zip bot.py )
python vendor/fullhouse-engine/sandbox/validator.py dist/bot.zip
```
