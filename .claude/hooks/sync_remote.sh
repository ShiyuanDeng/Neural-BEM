#!/bin/bash
# SessionStart: fetch every remote branch and report how local branches compare,
# so a restored or stale checkout is never mistaken for the latest work.
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0
git fetch --prune origin >/dev/null 2>&1 || { echo "git fetch origin FAILED: remote state unknown"; exit 0; }
echo "Fetched origin. Local branches versus origin:"
git for-each-ref --format='%(refname:short) %(upstream:short) %(upstream:track)' refs/heads |
  while read -r branch upstream track; do echo "  $branch -> ${upstream:-no upstream} ${track:-[in sync]}"; done
echo "Current branch: $(git branch --show-current)"
exit 0
