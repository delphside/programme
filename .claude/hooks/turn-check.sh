#!/usr/bin/env bash
# turn-check.sh — new GitHub comments from Steve, injected at the start of a turn.
#
# Owner, 2026-08-19: *"When do you notice the 'Not approved' comment?"* Before
# this, the honest answer was: at the next session start, or when told. Nothing
# prompted a look mid-session — the same lazy-sweep failure #166 is about, one
# level up.
#
# A turn is the only moment Claude exists, so this runs on `UserPromptSubmit`:
# waking now implies looking.
#
# **Throttled.** At most one API call every 90 seconds, so a fast exchange does
# not pay for a check per message. State is one timestamp file in .claude/,
# which is gitignored — this is Claude's own bookkeeping, not the project's.
#
# **Silent when there is nothing.** Output is injected into the model's context,
# so anything printed on a quiet turn is noise in every later turn too.
#
# Never fails a turn: every path exits 0.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 0
STATE=".claude/.turn-check-state"

# `--reseed` records the current state without reporting. `--reseed-bodies`
# records only the pull request body hashes and leaves the comment timestamp
# alone — that is what the `Stop` hook runs, so a body Claude edited during a
# turn is recorded at the end of it and never announced back on the next one.
# A full `--reseed` would also swallow comments Steve wrote while the turn ran.
#
# `--print-filter` prints the jq filter and exits, so the part of this script
# that has broken twice can be tested against a fixture without calling GitHub.
RESEED=0
BODIES_ONLY=0
PRINT_FILTER=0
[[ "${1:-}" == "--reseed" ]] && RESEED=1
[[ "${1:-}" == "--reseed-bodies" ]] && { RESEED=1; BODIES_ONLY=1; }
[[ "${1:-}" == "--print-filter" ]] && PRINT_FILTER=1

NOW="$(date -u +%s)"
if [[ -f "$STATE" ]]; then
  LAST_RUN="$(stat -c %Y "$STATE" 2>/dev/null || echo 0)"
  (( ! RESEED && ! PRINT_FILTER && NOW - LAST_RUN < 90 )) && exit 0
  SINCE="$(cat "$STATE" 2>/dev/null)"
else
  SINCE=""
fi
[[ -z "$SINCE" ]] && SINCE="$(date -u -d '20 minutes ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"

command -v gh > /dev/null || exit 0

# Claude's own comments are excluded **by author**. This used to test the body
# for the string "Typed by Claude", written when both of us posted as the same
# GitHub user and a marker in the text was the only thing to go on. Since #206
# Delivery 2 there are two accounts, and on 2026-09-03 a check of the thirty
# most recent comments found the marker on **none** of them: every comment
# Claude had written qualified as Steve's. The author is the fact; the marker
# was a convention nothing enforced.
ME="$(cat .claude/.gh-login 2>/dev/null)"
if [[ -z "$ME" ]]; then
  ME="$(timeout 10 gh api user --jq .login 2>/dev/null)"
  [[ -n "$ME" ]] && printf '%s' "$ME" > .claude/.gh-login
fi

# The `[deploy.sh]` test stays, and is not redundant with the author filter:
# the owner runs production deploys himself now, so those comments are written
# by *his* account and the author filter would let them through.
# `gh api` takes exactly one argument after --jq and has no --arg of its own,
# so the login is substituted into the filter rather than bound as a jq
# variable. Writing `--jq --arg me "$ME"` fails with "accepts 1 arg(s),
# received 4", and because this whole pipeline sends stderr to /dev/null it
# fails *silently*: the check would report nothing, forever, and look calm.
# An empty $ME falls back to a sentinel that matches no login, so a failed
# lookup over-reports rather than going quiet.
FILTER='.[] | select(.user.login != "__ME__")
            | select((.body | test("^\\[deploy.sh\\]")) | not)
            | "#\(.issue_url | split("/") | last)  \(.updated_at[11:16])  \((.body | gsub("\n"; " "))[0:160])"'
FILTER="${FILTER/__ME__/${ME:-__no_such_login__}}"
if (( PRINT_FILTER )); then printf '%s\n' "$FILTER"; exit 0; fi

NEW="$(timeout 15 gh api "repos/{owner}/{repo}/issues/comments?since=$SINCE&sort=updated&direction=asc&per_page=30" \
  --jq "$FILTER" 2>/dev/null)"

# Pull request bodies are a review surface now — Steve writes notes under the
# checklist items rather than in a comment thread (2026-08-19). A body edit
# produces no comment and no event this can poll for, so bodies are hashed and
# compared. `updated_at` would be simpler and wrong: it also moves for labels,
# commits and comments, and would cry wolf on every one.
HASHES=".claude/.body-hashes"
CURRENT="$(timeout 15 gh pr list --state open --limit 30 --json number,body \
  --jq '.[] | "\(.number) \(.body | @base64)"' 2>/dev/null \
  | while read -r num body; do printf '%s %s\n' "$num" "$(printf '%s' "$body" | md5sum | cut -d' ' -f1)"; done)"

EDITED=""
if [[ -f "$HASHES" && -n "$CURRENT" ]]; then
  while read -r num hash; do
    old="$(grep -E "^$num " "$HASHES" 2>/dev/null | awk '{print $2}')"
    [[ -n "$old" && "$old" != "$hash" ]] && EDITED="$EDITED  PR #$num body edited — read the review checklist"$'\n'
  done <<< "$CURRENT"
fi
[[ -n "$CURRENT" ]] && printf '%s\n' "$CURRENT" > "$HASHES"

# --reseed-bodies stops here: the hashes are recorded, the comment clock is not
# touched, and nothing is reported.
(( BODIES_ONLY )) && exit 0

date -u +%Y-%m-%dT%H:%M:%SZ > "$STATE"

(( RESEED )) && exit 0
[[ -z "$NEW" && -z "$EDITED" ]] && exit 0

echo "New on GitHub since the last check (Steve's, not yours) — reply where it was said, not here:"
[[ -n "$NEW" ]] && echo "$NEW"
[[ -n "$EDITED" ]] && printf '%s' "$EDITED"
