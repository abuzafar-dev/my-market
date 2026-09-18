#!/usr/bin/env bash
# Produces a shareable archive of the repo containing only tracked files —
# .env, CREDENTIALS.local.md, adhoc.key/.crt, media/, .venv/ etc. are
# excluded because `git archive` only ever includes what's in the index.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

ref="${1:-HEAD}"
out="${2:-my-market-export-$(date +%Y%m%d-%H%M%S).zip}"

git archive --format=zip --output="$out" "$ref"

echo "Wrote $out"
echo "Verify: unzip -l $out | grep -E '\\.env$|CREDENTIALS\\.local\\.md|adhoc\\.(key|crt)'"
echo "(that grep should print nothing)"
