#!/bin/bash
set -euo pipefail

echo ">>> [INITIATING] Holobiontic Earth Swarm..."

# 1. Trigger Autonomous Agents (Morning Briefing)
echo ">>> [SWARM] Running Scout Agents for Daily Digest..."
python3 tools/fetch_digest.py

# 2. Rebuild Site (Static Generation)
echo ">>> [BUILD] Generating static artifact..."
python3 tools/build.py

# 3. Deploy (Git Persistence)
echo ">>> [DEPLOY] Committing to swarm memory..."
git add .
git commit -m "feat(holobiontic): deploy and initiate swarm [skip ci]" || echo "No changes to commit"

# Optional: Push if remote exists
# git push origin main || echo "Remote push skipped (local only)"

echo ">>> [SUCCESS] System Active. Site deployed to site/"
