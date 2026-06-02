#!/usr/bin/env bash
# Stage 2: out-of-sample final confirmation + range-sampling A/B.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
W=14
HERO=src/mybot/bot.py
BASE=bots_local/tier1_baseline/bot.py
SAMP=bots_local/tier2_sampling/bot.py

echo "############ STAGE 2 START $(date) ############"

echo; echo "######## [1/2] FINAL CONFIRMATION (OUT-OF-SAMPLE): Tier-2 vs Tier-1, 6-max, 240 matches, seeds 500-739 ########"
python -m harness.sim compare --layout table --hero "$HERO" --hero-b "$BASE" \
    --matches 240 --hands 400 --workers $W --base-seed 500

echo; echo "######## [2/2] A/B: range-sampling vs haircut (both Tier-2), 6-max, 120 matches, seeds 800-919 ########"
python -m harness.sim compare --layout table --hero "$SAMP" --hero-b "$HERO" \
    --matches 120 --hands 400 --workers $W --base-seed 800

echo "############ STAGE 2 DONE $(date) ############"
