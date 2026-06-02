#!/usr/bin/env bash
# Sequential Tier-2 evaluation (one pool at a time => no cross-run CPU contention).
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
W=14
HERO=src/mybot/bot.py
BASE=bots_local/tier1_baseline/bot.py
BAL=bots_local/balanced_tag/bot.py

echo "############ STAGE 1 START $(date) ############"

echo; echo "######## [1/4] CONFIRMATION GATE: Tier-2 vs Tier-1 paired, 6-max, 160 matches ########"
python -m harness.sim compare --layout table --hero "$HERO" --hero-b "$BASE" \
    --matches 160 --hands 400 --workers $W --base-seed 0

echo; echo "######## [2/4] PER-ARCHETYPE GAUNTLET: Tier-2 heads-up vs each ref (100) + 6-max (160) ########"
python -m harness.sim gauntlet --hero "$HERO" --matches 100 --hands 400 --workers $W --base-seed 0

echo; echo "######## [3/4] TIER-3 DIAGNOSTIC: Tier-2 vs balanced TAG, HU, 300 matches (both seat orders) ########"
python -m harness.sim duel --hero "$HERO" --villain "$BAL" \
    --matches 300 --hands 400 --workers $W --base-seed 0

echo; echo "######## [4/4] TIER-3 REFERENCE: Tier-1 baseline vs balanced TAG, HU, 300 matches ########"
python -m harness.sim duel --hero "$BASE" --villain "$BAL" \
    --matches 300 --hands 400 --workers $W --base-seed 0

echo "############ STAGE 1 DONE $(date) ############"
